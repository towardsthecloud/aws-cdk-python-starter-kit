import os

# Avoid re-running uv's environment bootstrap during synth if the venv already exists.
# `uv venv` errors when the target directory is already present.
if os.path.isdir(".venv"):
    os.environ["PROJEN_DISABLE_POST"] = "true"

from projen import JsonFile, YamlFile
from projen.awscdk import AwsCdkPythonApp

from src.bin.cicd_helper import (
    create_build_workflow,
    create_cdk_deployment_workflows,
    create_cdk_diff_pr_workflow,
    create_release_workflow,
)
from src.bin.env_helper import (
    DEFAULT_GITHUB_DEPLOY_ROLE_NAME,
    EnvironmentConfig,
    add_cdk_action_task,
)

# Define the python module name and set the python version
project_name = "aws-cdk-python-starter-kit"
python_module_name = "src"
python_version = "3.13"
python_major, python_minor = map(int, python_version.split("."))
python_requires = f">={python_version},<{python_major}.{python_minor + 1}"

# Pin the CDK CLI so local runs, CI and the lockfile agree on one version. The PyPI package
# ships the same CLI as the npm one, so no workflow needs Node.js installed separately.
cdk_cli_version = "2.1134.0"  # Find the latest CDK CLI version here: https://pypi.org/project/aws-cdk-cli/

# Packages whose versions this file pins. Dependabot ignores them because the next synth would
# revert its bump, and the minimum-release-age gate exempts them because the pin is deliberate.
PINNED_PACKAGES = ["aws-cdk-lib", "aws-cdk-cli", "projen", "pytest"]

# Ignore releases younger than this when resolving. Matches the TypeScript kit's pnpm setting.
MINIMUM_RELEASE_AGE_DAYS = 7

# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

# Name of the GitHub deploy role created by the FoundationStack. Set as an environment variable
# for the projen tasks so the CDK app and the workflows agree on one name. Sourced from
# env_helper rather than retyped, because the construct falls back to the same constant.
github_role = DEFAULT_GITHUB_DEPLOY_ROLE_NAME

project = AwsCdkPythonApp(
    author_email="danny@towardsthecloud.com",
    author_name="Danny Steenman",
    cdk_version_pinning=True,
    cdk_version="2.263.0",  # Find the latest CDK version here: https://pypi.org/project/aws-cdk-lib
    cdk_cli_version=cdk_cli_version,
    module_name=python_module_name,
    name=project_name,
    projen_command="uv run projen",
    description="Create and deploy an AWS CDK app on your AWS account in less than 5 minutes using GitHub actions!",
    version="2.101.0",
    app_entrypoint=f"{python_module_name}/app.py",
    deps=["cloudstructs"],  # Runtime dependencies of this module
    dev_deps=[
        "projen@0.101.23",
        "ruff",
        "ty",
        f"aws-cdk-cli@{cdk_cli_version}",
    ],  # Find the latest projen version here: https://pypi.org/project/projen/
    pytest_options={
        "version": "9.1.1"
    },  # Find the latest pytest version here: https://pypi.org/project/pytest/
    context={
        "cli-telemetry": False,  # Disable AWS CDK CLI telemetry, see: https://github.com/aws/aws-cdk/issues/34892
    },
    uv=True,
    uv_options={
        "python_exec": f"python{python_version}",
        "project": {
            "name": project_name,
            "requires_python": python_requires,
        },
    },
    github_options={
        "mergify": False,
        "pull_request_lint_options": {
            "semantic_title_options": {
                "types": [
                    "feat",
                    "fix",
                    "chore",
                    "refactor",
                    "perf",
                    "docs",
                    "style",
                    "test",
                    "build",
                    "ci",
                ],
            },
        },
    },
    git_ignore_options={
        "ignore_patterns": [
            "__pycache__",
            "__pycache__/",
            ".python-version",
            ".DS_Store",
            ".env",
            ".mypy_cache",
            ".pytest_cache",
            ".Python",
            ".ruff_cache",
            ".venv/",
            "*.pyc",
            "venv/",
        ],
    },
)

# Set the CDK_DEFAULT_REGION environment variable for the projen tasks,
# so the CDK CLI knows which region to use
project.tasks.add_environment("CDK_DEFAULT_REGION", aws_region)

# Add a lint task and wire both linters into `test`, so CI fails on a lint or type error
# instead of only on a failing assertion.
lint_task = project.add_task(
    "lint",
    description="Lint and auto-fix the codebase using Ruff",
    receive_args=True,
)
lint_task.exec("ruff check --fix")
lint_task.exec("ruff format")

typecheck_task = project.add_task(
    "typecheck",
    description="Type check the codebase using ty",
    exec="ty check src tests",
)

project.test_task.spawn(lint_task)
project.test_task.spawn(typecheck_task)

# The CDK app entrypoint lives in `src`, so Python puts that directory on sys.path and the
# modules import each other as `stacks.x` and `bin.y`. pytest collects from the repository
# root instead, so give it the same import root or every test module fails to collect.
pyproject = project.try_find_object_file("pyproject.toml")
if pyproject:
    pyproject.add_override("tool.pytest.ini_options.pythonpath", [python_module_name])
    # Ignore anything published in the last 7 days when resolving, so a compromised or broken
    # release has time to be caught and yanked before it can reach this project. The uv
    # equivalent of the TypeScript kit's pnpm minimumReleaseAge. It takes a rolling duration,
    # so it needs no maintenance. Resolution only happens on `uv lock`; `uv sync --frozen`
    # installs exactly what the lockfile pins and is unaffected.
    pyproject.add_override("tool.uv.exclude-newer", f"{MINIMUM_RELEASE_AGE_DAYS} days")
    # The versions pinned above are a deliberate choice, so the age gate must not veto them:
    # pin a CDK release on its publication day and resolution would otherwise fail outright.
    # "0 days" means no age restriction for that package.
    pyproject.add_override(
        "tool.uv.exclude-newer-package",
        {name: "0 days" for name in PINNED_PACKAGES},
    )

# Add VSCode extensions recommendation
JsonFile(
    project,
    ".vscode/extensions.json",
    obj={"recommendations": ["dannysteenman.aws-cdk-extension-pack"]},
    marker=False,
)

gh = project.github

# Add Dependabot configuration for uv
YamlFile(
    project,
    ".github/dependabot.yml",
    obj={
        "version": 2,
        "updates": [
            {
                "package-ecosystem": "uv",
                "directory": "/",
                "schedule": {"interval": "weekly"},
                # projen pins these in this file, so a Dependabot bump would be
                # reverted by the next synth.
                "ignore": [{"dependency-name": name} for name in PINNED_PACKAGES],
                "labels": ["dependencies"],
                "groups": {
                    "default": {
                        "patterns": ["*"],
                        "exclude-patterns": PINNED_PACKAGES,
                    }
                },
            }
        ],
    },
)

# Defines the environment configurations for the CDK application.
# The order of this list is the deployment order in the pipeline: each environment's workflow
# is chained onto the completion of the previous one, so `production` only runs after `test`
# succeeded. Enable branch deployments on the lower environments only.
environment_configs = [
    EnvironmentConfig(
        name="test", account_id="987654321012", enable_branch_deploy=True
    ),
    EnvironmentConfig(
        name="production", account_id="123456789012", enable_branch_deploy=False
    ),
]

if gh:
    ordered_environments = [config.name for config in environment_configs]

    # Lint, type check, test and synth on every pull request
    create_build_workflow(gh, python_version)

    # Tag and publish a GitHub release when the project version changes on main
    create_release_workflow(gh, python_version)

    for config in environment_configs:
        task_environment = {
            "CDK_DEFAULT_ACCOUNT": config.account_id,
            "CDK_DEFAULT_REGION": aws_region,
            "ENVIRONMENT": config.name,
            "GITHUB_DEPLOY_ROLE": github_role,
        }

        # Adds `uv run projen` commands for executing cdk synth, diff, deploy, destroy and ls
        add_cdk_action_task(project, task_environment)

        # If branch deployment is enabled for this environment, add the GIT_BRANCH_REF tasks
        if config.enable_branch_deploy:
            add_cdk_action_task(
                project,
                {
                    **task_environment,
                    "GIT_BRANCH_REF": "$(echo ${GIT_BRANCH_REF:-$(git rev-parse --abbrev-ref HEAD)})",
                },
            )

        # Adds GitHub action workflows for deploying the CDK stacks to the target AWS account
        create_cdk_deployment_workflows(
            gh,
            config,
            aws_region,
            github_role,
            python_version,
            ordered_environments,
        )

    # Create the CDK diff PR workflow once, against the environment deployed last
    create_cdk_diff_pr_workflow(
        gh,
        environment_configs[-1].account_id,
        aws_region,
        github_role,
        python_version,
        ordered_environments,
    )

project.synth()
