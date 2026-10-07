from projen import github

# Pinned GitHub Actions used by every workflow in this repo. `.projenrc.py` registers these
# with projen's actions provider so projen-managed workflows (pull-request-lint)
# render the same versions as the workflows built here.
GITHUB_ACTIONS = {
    "checkout": "actions/checkout@v7",
    "cache_restore": "actions/cache/restore@v6",
    "cache_save": "actions/cache/save@v6",
    "configure_aws_credentials": "aws-actions/configure-aws-credentials@v6",
    "semantic_pull_request": "amannn/action-semantic-pull-request@v6",
    "setup_python": "actions/setup-python@v7",
    "setup_uv": "astral-sh/setup-uv@v10.0.1",  # setup-uv publishes no floating v10 tag
}


def pin_github_actions(gh):
    """Register GITHUB_ACTIONS with projen's actions provider so every workflow uses the same versions."""
    for action in GITHUB_ACTIONS.values():
        gh.actions.set(action.split("@")[0], action)


def cdk_environment_steps(python_version, cdk_cli_version, aws_credentials=None):
    """Checkout, Python, uv, project dependencies and the CDK CLI."""
    return [
        {
            "name": "Checkout repository",
            "uses": GITHUB_ACTIONS["checkout"],
            # No job built here pushes to git, so keep the token out of .git/config
            "with": {"persist-credentials": False},
        },
        {
            "name": "Setup python environment",
            "uses": GITHUB_ACTIONS["setup_python"],
            "with": {
                "python-version": python_version,
            },
        },
        {
            "name": "Setup uv",
            "uses": GITHUB_ACTIONS["setup_uv"],
        },
        *([aws_credentials] if aws_credentials else []),
        {
            "name": "Install dependencies",
            "run": "uv sync --frozen",
        },
        {
            "name": "Install cdk cli",
            "run": f"npm install -g aws-cdk@{cdk_cli_version}",
        },
        *(
            [
                {
                    "name": "Wait for AWS authentication",
                    "wait": ["configure_aws_credentials"],
                }
            ]
            if aws_credentials
            else []
        ),
    ]


def docker_asset_cache_steps():
    """Restore content-addressed bundling images; skip uploads for apps without Docker assets."""
    cache_path = "${{ runner.temp }}/docker-assets"
    cache_prefix = "docker-assets-v2-${{ runner.os }}-${{ runner.arch }}-${{ steps.docker_cache_epoch.outputs.week }}-"
    restore = [
        {
            "name": "Choose Docker cache refresh week",
            "id": "docker_cache_epoch",
            "run": 'echo "week=$(date -u +%G-%V)" >> "$GITHUB_OUTPUT"\necho "source=$(git rev-parse "HEAD^{tree}")" >> "$GITHUB_OUTPUT"',
        },
        {
            "name": "Restore Docker asset images",
            "id": "docker_cache",
            "uses": GITHUB_ACTIONS["cache_restore"],
            "with": {
                "path": cache_path,
                "key": cache_prefix + "${{ steps.docker_cache_epoch.outputs.source }}",
                "restore-keys": cache_prefix,
            },
        },
        {
            "name": "Load Docker asset images",
            "run": 'if [ -f "$RUNNER_TEMP/docker-assets/images.tar" ]; then docker load --input "$RUNNER_TEMP/docker-assets/images.tar"; fi',
        },
    ]
    save = [
        {
            "name": "Export Docker asset images",
            "id": "export_docker_images",
            "if": "steps.docker_cache.outputs.cache-hit != 'true'",
            "shell": "bash",
            "run": (
                "images=()\n"
                'while IFS= read -r image; do images+=("$image"); done < <(docker image ls --filter "reference=cdk-*" --format "{{.Repository}}:{{.Tag}}")\n'
                'if [ "${#images[@]}" -gt 0 ]; then\n'
                '  mkdir -p "$RUNNER_TEMP/docker-assets"\n'
                '  docker save --output "$RUNNER_TEMP/docker-assets/images.tar" "${images[@]}"\n'
                '  echo "has-images=true" >> "$GITHUB_OUTPUT"\n'
                "fi"
            ),
        },
        {
            "name": "Save Docker asset images",
            "if": "steps.export_docker_images.outputs.has-images == 'true'",
            "uses": GITHUB_ACTIONS["cache_save"],
            "with": {
                "path": cache_path,
                "key": "${{ steps.docker_cache.outputs.cache-primary-key }}",
            },
        },
    ]
    return restore, save


def cdk_validate_workflow(gh, python_version, cdk_cli_version, environments):
    """Validate the CDK app offline on pull requests, without AWS credentials."""
    restore_cache, save_cache = docker_asset_cache_steps()
    workflow = github.GithubWorkflow(gh, "cdk-validate")
    workflow.on(pull_request={}, workflow_dispatch={})
    workflow.add_jobs(
        {
            "validate": {
                "name": "Validate CDK app offline",
                "runsOn": ["ubuntu-latest"],
                "permissions": {
                    "contents": github.workflows.JobPermission.READ,
                },
                "steps": [
                    *cdk_environment_steps(python_version, cdk_cli_version),
                    *restore_cache,
                    *[
                        {
                            "id": f"validate_{env}",
                            "name": f"Validate {env} offline",
                            "background": True,
                            "run": f'uv run projen {env}:validate --no-online --output "${{{{ runner.temp }}}}/cdk-assemblies/{env}"',
                        }
                        for env in environments
                    ],
                    {
                        "id": "unit_tests",
                        "name": "Run tests",
                        "background": True,
                        "run": "uv run projen test",
                    },
                    {
                        "name": "Wait for validation and tests",
                        "wait": [
                            *[f"validate_{env}" for env in environments],
                            "unit_tests",
                        ],
                    },
                    *save_cache,
                ],
            },
        }
    )
    return workflow


def github_cicd(gh, account, env, python_version, aws_region, cdk_cli_version):
    # Add a GitHub workflow for deploying the CDK stacks to the AWS account
    cdk_deployment_workflow = github.GithubWorkflow(gh, f"cdk-deploy-{env}")
    cdk_deployment_workflow.on(
        push={"branches": ["main"]} if env != "production" else None,
        workflow_dispatch={},
    )

    cdk_deployment_workflow.add_jobs(
        {
            "deploy": {
                "name": f"Deploy CDK stacks to {env} AWS account",
                "runsOn": ["ubuntu-latest"],
                "permissions": {
                    "actions": github.workflows.JobPermission.WRITE,
                    "contents": github.workflows.JobPermission.READ,
                    "idToken": github.workflows.JobPermission.WRITE,
                },
                "steps": [
                    *cdk_environment_steps(
                        python_version,
                        cdk_cli_version,
                        aws_credentials={
                            "id": "configure_aws_credentials",
                            "name": "Configure AWS credentials",
                            "background": True,
                            "uses": GITHUB_ACTIONS["configure_aws_credentials"],
                            "with": {
                                "role-to-assume": f"arn:aws:iam::{account}:role/GitHubDeployRole",
                                "aws-region": aws_region,
                            },
                        },
                    ),
                    {
                        "name": f"Validate CDK for the {env.upper()} environment",
                        "run": f"uv run projen {env}:validate",
                    },
                    {
                        "name": f"Deploy CDK to the {env.upper()} environment on AWS account {account}",
                        "run": f"uv run projen {env}:deploy",
                    },
                ],
            },
        }
    )
