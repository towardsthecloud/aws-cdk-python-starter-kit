import os
import re
from dataclasses import dataclass
from typing import Literal

from projen.awscdk import AwsCdkPythonApp

Environment = Literal["sandbox", "development", "test", "staging", "production"]
"""The deployment environments this project supports."""

SUPPORTED_CDK_ACTIONS = ("synth", "diff", "deploy", "deploy:hotswap", "destroy", "ls")
"""CDK actions that get a generated projen task."""

# A resource name longer than this breaks the strictest AWS naming constraints.
MAX_RESOURCE_NAME_LENGTH = 64
# Longer branch names push the resource name over the limit once a base name is prepended.
MAX_BRANCH_NAME_LENGTH = 25

GIT_TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+$")
NON_RESOURCE_NAME_CHARACTERS = re.compile(r"[^a-zA-Z0-9-]")
TRAILING_HYPHENS = re.compile(r"-+$")
TRAILING_NON_ALPHANUMERIC = re.compile(r"[^a-zA-Z0-9]+$")

# Deploying a branch stack from one of these would collide with the shared environment stacks.
LONG_LIVED_BRANCHES = frozenset({"main", "develop", "development"})


@dataclass(frozen=True)
class EnvironmentConfig:
    """Configuration for a single deployment environment.

    Attributes:
        name: The environment name, which also names the projen tasks and the GitHub environment.
        account_id: The AWS account this environment deploys to.
        enable_branch_deploy: Whether feature branches get their own ephemeral stacks in this
            environment. Keep this off for production.
    """

    name: Environment
    account_id: str
    enable_branch_deploy: bool = False


def get_task_name(
    environment: str, action: str, is_branch: bool = False, task_type: str | None = None
) -> str:
    """Build a projen task name following the project's naming convention.

    Args:
        environment: The environment name, for example `test` or `production`.
        action: The CDK action, for example `synth`, `deploy`, or `destroy`.
        is_branch: Whether the task targets a branch deployment.
        task_type: Either `all` or `stack`. Ignored for `synth` and `ls`, which always
            operate on every stack.

    Returns:
        The task name.

    Examples:
        >>> get_task_name("test", "synth")
        'test:synth'
        >>> get_task_name("test", "deploy", is_branch=True, task_type="all")
        'test:branch:deploy:all'
    """
    task_name = (
        f"{environment}:branch:{action}" if is_branch else f"{environment}:{action}"
    )

    if task_type and action not in ("synth", "ls"):
        task_name += f":{task_type}"

    return task_name


def add_cdk_action_task(
    project: AwsCdkPythonApp, target_account: dict[str, str]
) -> None:
    """Add `uv run projen` tasks for every CDK action in one environment.

    Creates a single task for `synth` and `ls`, which always cover every stack, and `:all` plus
    `:stack` variants for the actions where targeting one stack is useful. `deploy:hotswap` is
    only generated for branch deployments, where a fast inner loop matters and drift does not.

    Branch deployments to the `test` environment use CDK express mode, which is considerably
    faster and safe for ephemeral stacks.

    Args:
        project: The projen project to add the tasks to.
        target_account: Environment variables for the tasks. Must include `ENVIRONMENT`, and
            carries `GIT_BRANCH_REF` for branch deployments.
    """
    is_branch = bool(target_account.get("GIT_BRANCH_REF"))
    use_express_mode = target_account["ENVIRONMENT"] == "test" and is_branch
    express_mode_arg = " --express" if use_express_mode else ""

    command_map = {
        "synth": "cdk synth",
        "destroy": f"cdk destroy{express_mode_arg} --force",
        "deploy": f"cdk deploy{express_mode_arg} --require-approval never",
        "deploy:hotswap": "cdk deploy --hotswap --require-approval never",
        "diff": "cdk diff",
        "ls": "cdk ls",
    }

    def describe(action: str, target: str) -> str:
        return f"{action.capitalize()} {target} on the {target_account['ENVIRONMENT'].upper()} account"

    for action in SUPPORTED_CDK_ACTIONS:
        # Hotswap only makes sense for the ephemeral stacks of a branch deployment.
        if action == "deploy:hotswap" and not is_branch:
            continue

        exec_command = command_map[action]

        if action in ("synth", "ls"):
            project.add_task(
                get_task_name(
                    target_account["ENVIRONMENT"], action, is_branch=is_branch
                ),
                description=describe(action, "the stacks"),
                env=target_account,
                exec=exec_command,
            )
            continue

        action_label = "hotswap deploy" if action == "deploy:hotswap" else action

        project.add_task(
            get_task_name(
                target_account["ENVIRONMENT"],
                action,
                is_branch=is_branch,
                task_type="all",
            ),
            description=describe(action_label, "all stacks"),
            env=target_account,
            exec=f"{exec_command} --all",
        )

        project.add_task(
            get_task_name(
                target_account["ENVIRONMENT"],
                action,
                is_branch=is_branch,
                task_type="stack",
            ),
            description=describe(action_label, "specific stack(s)"),
            env=target_account,
            exec=exec_command,
            receive_args=True,
        )


def extract_cleaned_branch_name(git_branch_ref: str | None) -> str | None:
    """Reduce a Git ref to the suffix used in branch-deployed resource names.

    Args:
        git_branch_ref: The Git ref, for example `feature/add-api` or `refs/heads/fix-1`.

    Returns:
        The cleaned branch name, or `None` when the ref should not get its own stacks: a
        version tag, or one of the long-lived branches that own the shared environment stacks.
    """
    if not git_branch_ref:
        return None

    if GIT_TAG_PATTERN.search(git_branch_ref):
        return None

    last_part = git_branch_ref.lower().split("/")[-1]

    if last_part in LONG_LIVED_BRANCHES:
        return None

    cleaned = TRAILING_HYPHENS.sub("", NON_RESOURCE_NAME_CHARACTERS.sub("", last_part))
    return cleaned[:MAX_BRANCH_NAME_LENGTH]


def create_env_resource_name(base_name: str) -> str:
    """Suffix a resource name with the branch or environment it belongs to.

    Args:
        base_name: The base resource name, for example `StarterStack`.

    Returns:
        The suffixed name, truncated to 64 characters to satisfy AWS naming constraints.

    Raises:
        ValueError: If `GIT_BRANCH_REF` is `main`. A branch deployment from `main` would
            collide with the shared environment stacks.
    """
    branch_name = os.environ.get("GIT_BRANCH_REF")
    environment = os.environ.get("ENVIRONMENT", "dev")

    if branch_name and branch_name.lower() == "main":
        raise ValueError(
            'Invalid branch-based deployment: GIT_BRANCH_REF cannot be "main"'
        )

    cleaned_branch_name = extract_cleaned_branch_name(branch_name)
    suffix = cleaned_branch_name or environment
    resource_name = f"{base_name}-{suffix}"

    if len(resource_name) <= MAX_RESOURCE_NAME_LENGTH:
        return resource_name

    # Truncating can leave a trailing hyphen, which most AWS resource names reject.
    return TRAILING_NON_ALPHANUMERIC.sub("", resource_name[:MAX_RESOURCE_NAME_LENGTH])
