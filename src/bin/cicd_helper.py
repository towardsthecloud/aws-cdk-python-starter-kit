from projen import github

# Pinned GitHub Actions used by every workflow in this repo. `.projenrc.py` registers these
# with projen's actions provider so projen-managed workflows (auto-approve, pull-request-lint)
# render the same versions as the workflows built here.
GITHUB_ACTIONS = {
    "checkout": "actions/checkout@v7",
    "configure_aws_credentials": "aws-actions/configure-aws-credentials@v6",
    "semantic_pull_request": "amannn/action-semantic-pull-request@v6",
    "setup_python": "actions/setup-python@v7",
    "setup_uv": "astral-sh/setup-uv@v10.0.1",  # setup-uv publishes no floating v10 tag
}


def pin_github_actions(gh):
    """Register GITHUB_ACTIONS with projen's actions provider so every workflow uses the same versions."""
    for action in GITHUB_ACTIONS.values():
        gh.actions.set(action.split("@")[0], action)


def cdk_environment_steps(python_version, cdk_cli_version):
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
        {
            "name": "Install dependencies",
            "run": "uv sync",
        },
        {
            "name": "Install cdk cli",
            "run": f"npm install -g aws-cdk@{cdk_cli_version}",
        },
    ]


def cdk_validate_workflow(gh, python_version, cdk_cli_version):
    """Validate the CDK app offline on pull requests, without AWS credentials."""
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
                    {
                        "name": "Validate CDK app against the default rule set",
                        "run": "uv run projen validate",
                    },
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
                    *cdk_environment_steps(python_version, cdk_cli_version),
                    {
                        "name": "Configure AWS credentials",
                        "uses": GITHUB_ACTIONS["configure_aws_credentials"],
                        "with": {
                            "role-to-assume": f"arn:aws:iam::{account}:role/GitHubDeployRole",
                            "aws-region": aws_region,
                        },
                    },
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
