from collections.abc import Sequence
from typing import Any

from projen import github

from .env_helper import EnvironmentConfig, get_task_name

COMMON_RUNS_ON = ["ubuntu-latest"]

# Branches that must never get their own ephemeral stacks: `main` owns the shared environment
# stacks, and the rest are automation branches whose pushes would deploy on every bot commit.
BRANCH_EXCLUSIONS = ["main", "hotfix/*", "github-actions/*", "dependabot/**"]

COMMON_WORKFLOW_PERMISSIONS = {
    "contents": github.workflows.JobPermission.READ,
    "idToken": github.workflows.JobPermission.WRITE,
}
"""Least privilege for a deployment job: read the code, mint an OIDC token, nothing else."""


GIT_IDENTITY_STEP = {
    "name": "Set git identity",
    "run": (
        'git config user.name "github-actions[bot]"\n'
        'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"'
    ),
}


def create_build_workflow(
    gh: github.GitHub, python_version: str
) -> github.GithubWorkflow:
    """Create the workflow that lints, type checks, tests and synthesizes on every pull request.

    Also carries projen's self-mutation pattern: if `projen build` regenerates a file, the diff
    is pushed back onto the pull request branch rather than silently ignored, so a stale
    generated file can never merge.

    Args:
        gh: The projen GitHub component to attach the workflow to.
        python_version: The Python version to set up.

    Returns:
        The created workflow.
    """
    workflow = github.GithubWorkflow(gh, "build")
    workflow.on(pull_request={}, workflow_dispatch={})

    # A fork PR runs contributor-controlled test and build code, so this job holds nothing that
    # can write to the repository. The self-mutation job below does the pushing, and it skips
    # forks entirely.
    build_steps = [
        _checkout_step(
            ref="${{ github.event.pull_request.head.ref }}",
            repository="${{ github.event.pull_request.head.repo.full_name }}",
        ),
        _setup_python_step(python_version),
        _setup_uv_step(),
        # Not --frozen: projen may legitimately update the lockfile, and the self-mutation
        # step below is what surfaces that as a pushed change.
        {"name": "Install dependencies", "run": "uv sync"},
        {"name": "build", "run": "uv run projen build"},
        {
            "name": "Find mutations",
            "id": "self_mutation",
            "run": (
                "git add .\n"
                "git diff --staged --patch --exit-code > repo.patch "
                '|| echo "self_mutation_happened=true" >> $GITHUB_OUTPUT'
            ),
            "shell": "bash",
        },
        {
            "name": "Upload patch",
            "if": "steps.self_mutation.outputs.self_mutation_happened",
            "uses": "actions/upload-artifact@v7",
            "with": {"name": "repo.patch", "path": "repo.patch", "overwrite": True},
        },
        {
            "name": "Fail build on mutation",
            "if": "steps.self_mutation.outputs.self_mutation_happened",
            "run": (
                'echo "::error::Files were changed during build (see build log). '
                'If this was triggered from a fork, you will need to update your branch."\n'
                "cat repo.patch\n"
                "exit 1"
            ),
        },
    ]

    self_mutation_steps = [
        _checkout_step(
            token="${{ secrets.PROJEN_GITHUB_TOKEN }}",
            ref="${{ github.event.pull_request.head.ref }}",
            repository="${{ github.event.pull_request.head.repo.full_name }}",
        ),
        {
            "name": "Download patch",
            "uses": "actions/download-artifact@v8",
            "with": {"name": "repo.patch", "path": "${{ runner.temp }}"},
        },
        {
            "name": "Apply patch",
            "run": (
                "[ -s ${{ runner.temp }}/repo.patch ] && git apply ${{ runner.temp }}/repo.patch "
                '|| echo "Empty patch. Skipping."'
            ),
        },
        GIT_IDENTITY_STEP,
        {
            "name": "Push changes",
            "env": {"PULL_REQUEST_REF": "${{ github.event.pull_request.head.ref }}"},
            "run": (
                'git add .\ngit commit -s -m "chore: self mutation"\ngit push origin "HEAD:$PULL_REQUEST_REF"'
            ),
        },
    ]

    workflow.add_jobs(
        {
            "build": {
                "runsOn": COMMON_RUNS_ON,
                "permissions": {"contents": github.workflows.JobPermission.READ},
                "outputs": {
                    "self_mutation_happened": {
                        "stepId": "self_mutation",
                        "outputName": "self_mutation_happened",
                    }
                },
                "env": {"CI": "true"},
                "steps": build_steps,
            },
            "self-mutation": {
                "needs": ["build"],
                "runsOn": COMMON_RUNS_ON,
                "permissions": {"contents": github.workflows.JobPermission.WRITE},
                # A fork cannot be pushed to, and the token must never reach fork-controlled code.
                "if": (
                    "always() && needs.build.outputs.self_mutation_happened && "
                    "!(github.event.pull_request.head.repo.full_name != github.repository)"
                ),
                "steps": self_mutation_steps,
            },
        }
    )

    return workflow


def create_release_workflow(
    gh: github.GitHub, python_version: str
) -> github.GithubWorkflow:
    """Create the workflow that tags a release when the project version changes.

    This differs from the TypeScript starter kit, which uses projen's release component to
    derive the next version from conventional commits. projen has no equivalent for Python
    projects, so the version in `.projenrc.py` is the trigger: bump it, merge to main, and
    this workflow tags the commit and publishes a GitHub release with generated notes.

    Args:
        gh: The projen GitHub component to attach the workflow to.
        python_version: The Python version to set up.

    Returns:
        The created workflow.
    """
    workflow = github.GithubWorkflow(
        gh,
        "release",
        limit_concurrency=True,
        concurrency_options={
            "group": "${{ github.workflow }}",
            "cancel_in_progress": False,
        },
    )
    workflow.on(push={"branches": ["main"]}, workflow_dispatch={})

    workflow.add_jobs(
        {
            "release": {
                "name": "Tag and publish a GitHub release",
                "runsOn": COMMON_RUNS_ON,
                "permissions": {"contents": github.workflows.JobPermission.WRITE},
                "steps": [
                    # Full history so the generated release notes can reach the previous tag.
                    _checkout_step(fetch_depth=0),
                    _setup_python_step(python_version),
                    _setup_uv_step(),
                    {"name": "Install dependencies", "run": "uv sync --frozen"},
                    {
                        "name": "Read project version",
                        "id": "version",
                        "run": (
                            'VERSION=$(uv run python -c "'
                            "import tomllib, pathlib; "
                            "print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])"
                            '")\n'
                            'echo "tag=v$VERSION" >> $GITHUB_OUTPUT'
                        ),
                    },
                    {
                        "name": "Check if version has already been tagged",
                        "id": "check_tag_exists",
                        "run": (
                            "git ls-remote -q --exit-code --tags origin "
                            "${{ steps.version.outputs.tag }} > /dev/null "
                            '&& echo "exists=true" >> $GITHUB_OUTPUT '
                            '|| echo "exists=false" >> $GITHUB_OUTPUT'
                        ),
                    },
                    GIT_IDENTITY_STEP,
                    {
                        "name": "Release",
                        "if": "steps.check_tag_exists.outputs.exists != 'true'",
                        "env": {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"},
                        "run": (
                            "gh release create ${{ steps.version.outputs.tag }} "
                            "-R $GITHUB_REPOSITORY -t ${{ steps.version.outputs.tag }} "
                            "--target $GITHUB_SHA --generate-notes"
                        ),
                    },
                ],
            }
        }
    )

    return workflow


def _branch_filter() -> list[str]:
    """Build the push branch filter that excludes the long-lived and automation branches."""
    return ["**", *[f"!{branch}" for branch in BRANCH_EXCLUSIONS]]


def _excluded_branch_expression(ref: str) -> str:
    """Build a GitHub expression that is true when `ref` is not an excluded branch.

    Triggers that support a `branches` filter get `_branch_filter()`. The `delete` event does
    not support one, so it needs the same exclusions expressed as a job condition.

    Args:
        ref: The GitHub expression holding the branch name, for example `github.event.ref`.

    Returns:
        The condition, without the surrounding `${{ }}`.
    """
    clauses = []

    for branch in BRANCH_EXCLUSIONS:
        if "*" in branch:
            prefix = branch.split("*", 1)[0]
            clauses.append(f"!startsWith({ref}, '{prefix}')")
        else:
            clauses.append(f"{ref} != '{branch}'")

    return " && ".join(clauses)


def _checkout_step(**with_options: Any) -> dict[str, Any]:
    """Build the repository checkout step.

    Args:
        **with_options: Entries for the step's `with` block, such as `ref`, `repository`,
            `token`, or `fetch_depth`. Underscores become hyphens, so `fetch_depth=0` renders
            as `fetch-depth: 0`. Falsy values other than `0` are dropped, which lets callers
            pass an optional ref without branching.

    Returns:
        The checkout step.
    """
    step: dict[str, Any] = {
        "name": "Checkout repository",
        "uses": "actions/checkout@v6",
    }
    options = {
        key.replace("_", "-"): value
        for key, value in with_options.items()
        if value or value == 0
    }

    if options:
        step["with"] = options

    return step


def _setup_python_step(python_version: str) -> dict[str, Any]:
    """Build the Python setup step."""
    return {
        "name": "Setup python environment",
        "uses": "actions/setup-python@v6",
        "with": {"python-version": python_version},
    }


def _setup_uv_step() -> dict[str, Any]:
    """Build the uv setup step, with caching keyed on the lockfile."""
    return {
        "name": "Setup uv",
        "uses": "astral-sh/setup-uv@v7",
        "with": {"enable-cache": True, "cache-dependency-glob": "uv.lock"},
    }


def _aws_credentials_step(account: str, region: str, role_name: str) -> dict[str, Any]:
    """Build the OIDC credential step for the deploy role in one account."""
    return {
        "name": "Configure AWS credentials",
        "uses": "aws-actions/configure-aws-credentials@v6",
        "with": {
            "role-to-assume": f"arn:aws:iam::{account}:role/{role_name}",
            "aws-region": region,
        },
    }


def _install_deps_step() -> dict[str, Any]:
    """Build the dependency install step.

    `--frozen` fails rather than silently resolving a different dependency set than the
    lockfile pins, which is what makes a CI run reproducible.
    """
    return {"name": "Install dependencies", "run": "uv sync --frozen"}


def common_workflow_steps(
    python_version: str,
    account: str | None = None,
    region: str | None = None,
    github_deploy_role: str | None = None,
    checkout_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Build the steps every workflow starts with.

    AWS credentials are only requested when an account, region, and role are all supplied, so
    the same helper serves workflows that never touch AWS.

    Args:
        python_version: The Python version to set up.
        account: The AWS account to assume the deploy role in.
        region: The AWS region to operate in.
        github_deploy_role: The name of the deploy role to assume.
        checkout_ref: A specific git ref to check out, for example a pull request head SHA.

    Returns:
        The ordered list of workflow steps.
    """
    steps = [
        _checkout_step(ref=checkout_ref),
        _setup_python_step(python_version),
        _setup_uv_step(),
    ]

    if github_deploy_role and region and account:
        steps.append(_aws_credentials_step(account, region, github_deploy_role))

    steps.append(_install_deps_step())

    return steps


def create_cdk_diff_pr_workflow(
    gh: github.GitHub,
    account: str,
    region: str,
    github_deploy_role: str,
    python_version: str,
    ordered_environments: Sequence[str],
) -> github.GithubWorkflow:
    """Create the workflow that posts a CDK diff as a pull request comment.

    The diff runs against the last environment in the deployment order, which is the one a
    reviewer most needs to see the impact on.

    Args:
        gh: The projen GitHub component to attach the workflow to.
        account: The AWS account to diff against.
        region: The AWS region to diff in.
        github_deploy_role: The name of the deploy role to assume.
        python_version: The Python version to set up.
        ordered_environments: Environment names in deployment order.

    Returns:
        The created workflow.
    """
    workflow = github.GithubWorkflow(gh, "cdk-diff-pr-comment")
    highest_env = ordered_environments[-1] if ordered_environments else "production"

    # pull_request_target runs the workflow definition from the base branch, so a fork PR cannot
    # rewrite it to steal the deploy credential. The checkout below is pinned to the PR head SHA,
    # so the diff still reflects the proposed change.
    workflow.on(pull_request_target={"branches": ["main"]})

    steps = common_workflow_steps(
        python_version,
        account,
        region,
        github_deploy_role,
        "${{ github.event.pull_request.head.sha }}",
    )

    steps += [
        {
            "name": "CDK diff and notify PR",
            # A non-zero exit here means the diff itself failed; the commenter still posts the
            # captured output, which is more useful to a reviewer than a red X with no detail.
            "run": (
                f"uv run projen {get_task_name(highest_env, 'diff', task_type='all')} "
                "> cdk-diff-output.txt 2>&1 || true"
            ),
        },
        {
            "name": "Post CDK Diff Comment in PR",
            "uses": "towardsthecloud/aws-cdk-diff-pr-commenter@v1",
            "with": {
                "diff-file": "cdk-diff-output.txt",
                "aws-region": region,
                "header": f"CDK Diff for {highest_env} in {region}",
            },
        },
    ]

    workflow.add_jobs(
        {
            "diff": {
                "name": f"CDK diff PR branch with {highest_env} environment (via main)",
                "runsOn": COMMON_RUNS_ON,
                "permissions": {
                    **COMMON_WORKFLOW_PERMISSIONS,
                    "pullRequests": github.workflows.JobPermission.WRITE,
                },
                "env": {"AWS_REGION": region},
                "steps": steps,
            }
        }
    )

    return workflow


def create_cdk_deployment_workflows(
    gh: github.GitHub,
    config: EnvironmentConfig,
    region: str,
    github_deploy_role: str,
    python_version: str,
    ordered_environments: Sequence[str],
) -> None:
    """Create every deployment workflow for one environment.

    Always creates the shared environment workflow. When the environment enables branch
    deployments, also creates the branch deploy and branch destroy workflows.

    Args:
        gh: The projen GitHub component to attach the workflows to.
        config: The environment to generate workflows for.
        region: The AWS region to deploy to.
        github_deploy_role: The name of the deploy role to assume.
        python_version: The Python version to set up.
        ordered_environments: Environment names in deployment order.
    """
    _create_cdk_deployment_workflow(
        gh,
        config,
        region,
        github_deploy_role,
        python_version,
        False,
        ordered_environments,
    )

    if config.enable_branch_deploy:
        _create_cdk_deployment_workflow(
            gh, config, region, github_deploy_role, python_version, True, []
        )
        _create_cdk_destroy_workflow(
            gh, config, region, github_deploy_role, python_version
        )


def _create_cdk_deployment_workflow(
    gh: github.GitHub,
    config: EnvironmentConfig,
    region: str,
    github_deploy_role: str,
    python_version: str,
    deploy_for_branch: bool,
    ordered_environments: Sequence[str],
) -> github.GithubWorkflow:
    """Create a single deployment workflow, for either the shared environment or a branch."""
    env = config.name
    workflow_name = (
        f"cdk-deploy-{env}-branch" if deploy_for_branch else f"cdk-deploy-{env}"
    )

    workflow = github.GithubWorkflow(
        gh,
        workflow_name,
        limit_concurrency=True,
        concurrency_options={
            "group": "${{ github.workflow }}-${{ github.ref_name }}",
            # Cancelling a deploy mid-flight leaves the stack in UPDATE_IN_PROGRESS, so queue instead.
            "cancel_in_progress": False,
        },
    )

    triggers: dict[str, Any] = {"workflow_dispatch": {}}
    chained_on_previous_environment = False

    if deploy_for_branch:
        triggers["push"] = {"branches": _branch_filter()}
    else:
        current_index = (
            ordered_environments.index(env) if env in ordered_environments else -1
        )
        if current_index == 0:
            triggers["push"] = {"branches": ["main"]}
        elif current_index > 0:
            # Chain onto the previous environment so production only runs once test has passed.
            previous_env = ordered_environments[current_index - 1]
            triggers["workflow_run"] = {
                "workflows": [f"cdk-deploy-{previous_env}"],
                "types": ["completed"],
            }
            chained_on_previous_environment = True

    workflow.on(**triggers)

    steps = common_workflow_steps(
        python_version, config.account_id, region, github_deploy_role
    )
    steps += [
        {
            "name": f"Run CDK synth for the {env.upper()} environment",
            "run": f"uv run projen {get_task_name(env, 'synth', is_branch=deploy_for_branch)}",
        },
        {
            "name": f"Deploy CDK to the {env.upper()} environment on AWS account {config.account_id}",
            "run": f"uv run projen {get_task_name(env, 'deploy', is_branch=deploy_for_branch, task_type='all')}",
        },
    ]

    job: dict[str, Any] = {
        "name": f"Deploy CDK stacks to {env} AWS account{' (Branch)' if deploy_for_branch else ''}",
        "runsOn": COMMON_RUNS_ON,
        "environment": env,
        "permissions": COMMON_WORKFLOW_PERMISSIONS,
        "steps": steps,
    }

    if chained_on_previous_environment:
        # workflow_run fires on completion regardless of outcome, so a failed test deploy would
        # otherwise promote straight to production.
        job["if"] = "github.event.workflow_run.conclusion == 'success'"

    workflow.add_jobs({"deploy": job})

    return workflow


def _create_cdk_destroy_workflow(
    gh: github.GitHub,
    config: EnvironmentConfig,
    region: str,
    github_deploy_role: str,
    python_version: str,
) -> github.GithubWorkflow:
    """Create the workflow that tears down a branch's ephemeral stacks.

    Runs on branch deletion, which covers the merged pull request case when the repository has
    "Automatically delete head branches" enabled, and on manual dispatch.
    """
    env = config.name
    workflow = github.GithubWorkflow(gh, f"cdk-destroy-{env}-branch")

    # GitHub does not support a `branches` filter on `delete` events, so the automation and
    # long-lived branches are excluded by the job condition below instead of by the trigger.
    workflow.on(workflow_dispatch={}, delete={})

    steps = common_workflow_steps(
        python_version, config.account_id, region, github_deploy_role
    )
    destroy_task = get_task_name(env, "destroy", is_branch=True, task_type="all")
    deleted_branch_condition = (
        "github.event.ref_type == 'branch' && github.event_name == 'delete'"
    )
    job_condition = (
        "github.event_name == 'workflow_dispatch' || "
        f"({deleted_branch_condition} && {_excluded_branch_expression('github.event.ref')})"
    )

    steps += [
        {
            "name": "Fetch Deleted Branch Name",
            "id": "destroy-branch",
            "if": deleted_branch_condition,
            # The deleted branch no longer exists to check out, so read its name from the event payload.
            "run": (
                "BRANCH=$(cat ${{ github.event_path }} | jq --raw-output '.ref'); "
                'echo "${{ github.repository }} has ${BRANCH} branch"; '
                'echo "DESTROY_BRANCH_NAME=$BRANCH" >> $GITHUB_OUTPUT'
            ),
        },
        {
            "name": "Destroy Branch Stack (Workflow Dispatch)",
            "if": "github.event_name == 'workflow_dispatch'",
            "run": f"uv run projen {destroy_task}",
            "env": {"GIT_BRANCH_REF": "${{ github.ref_name }}"},
        },
        {
            "name": "Destroy Branch Stack (Branch Deletion)",
            "if": deleted_branch_condition,
            "run": f"uv run projen {destroy_task}",
            "env": {
                "GIT_BRANCH_REF": "${{ steps.destroy-branch.outputs.DESTROY_BRANCH_NAME }}"
            },
        },
    ]

    workflow.add_jobs(
        {
            "destroy": {
                "name": "Remove deployment of feature branch",
                "if": job_condition,
                "runsOn": COMMON_RUNS_ON,
                "environment": env,
                "permissions": COMMON_WORKFLOW_PERMISSIONS,
                "steps": steps,
            }
        }
    )

    return workflow
