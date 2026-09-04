import os

# Avoid re-running uv's environment bootstrap during synth if the venv already exists.
# `uv venv` errors when the target directory is already present.
if os.path.isdir(".venv"):
    os.environ["PROJEN_DISABLE_POST"] = "true"

from projen import YamlFile
from projen.awscdk import AwsCdkPythonApp

from src.bin.cicd_helper import (
    GITHUB_ACTIONS,
    cdk_validate_workflow,
    github_cicd,
    pin_github_actions,
)
from src.bin.env_helper import CDK_VALIDATE_COMMAND, cdk_action_task

# Define the python module name and set the python version
project_name = "aws-cdk-python-starter-kit"
python_module_name = "src"
python_version = "3.13"
python_major, python_minor = map(int, python_version.split("."))
python_requires = f">={python_version},<{python_major}.{python_minor + 1}"
cdk_version = "2.267.0"
cdk_cli_version = "2.1139.0"

# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

project = AwsCdkPythonApp(
    author_email="danny@towardsthecloud.com",
    author_name="Danny Steenman",
    cdk_version_pinning=True,
    cdk_version=cdk_version,  # Find the latest CDK version here: https://pypi.org/project/aws-cdk-lib
    cdk_cli_version=cdk_cli_version,  # Find the latest CDK CLI version https://pypi.org/project/aws-cdk-cli/
    context={
        "@aws-cdk/core:annotationsInValidationReport": True,
        "@aws-cdk/core:validateAgainstDefaultRules": True,
        "cli-telemetry": False,
    },
    module_name=python_module_name,
    name=project_name,
    projen_command="uv run projen",
    description="Create and deploy an AWS CDK app on your AWS account in less than 5 minutes using GitHub actions!",
    version="2.101.0",
    app_entrypoint=f"{python_module_name}/app.py",
    deps=["aws-cdk-github-oidc"],
    dev_deps=[
        "projen@0.103.7",
        "ruff",
        "ty",
    ],  # Find the latest projen version here: https://pypi.org/project/projen/
    pytest_options={"version": "9.1.1"},
    uv=True,
    uv_options={
        "python_exec": f"python{python_version}",
        "project": {
            "name": project_name,
            "requires_python": python_requires,
        },
    },
    github_options={
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
    auto_approve_options={
        "allowed_usernames": ["dependabot", "dependabot[bot]"],
    },
    git_ignore_options={
        "ignore_patterns": [
            "__pycache__",
            "__pycache__/",
            ".python-version",
            ".DS_Store",
            ".mypy_cache",
            ".pytest_cache",
            ".Python",
            ".venv/",
            "*.pyc",
            "venv/",
        ],
    },
)

# Set the CDK_DEFAULT_REGION environment variable for the projen tasks,
# so the CDK CLI knows which region to use
project.tasks.add_environment("CDK_DEFAULT_REGION", aws_region)

# Tests import the stacks the same way src/app.py does, so put src on the module path
project.test_task.env("PYTHONPATH", python_module_name)

project.add_task(
    "validate",
    description="Validate the CDK app offline against the default CloudFormation rules",
    exec=f"{CDK_VALIDATE_COMMAND} --no-online",
    receive_args=True,
)

# Define the target AWS accounts for the different environments
target_accounts = {
    "dev": "987654321012",
    "test": "123456789012",
    "staging": None,
    "production": None,
}

gh = project.github

# Keep projen-managed workflows (auto-approve, pull-request-lint) on the same action versions
pin_github_actions(gh)

# Validate the CDK app offline on every pull request (no AWS credentials required)
cdk_validate_workflow(gh, python_version, cdk_cli_version)

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
                "ignore": [
                    {"dependency-name": "aws-cdk-lib"},
                    {"dependency-name": "aws-cdk"},
                    {"dependency-name": "projen"},
                ],
                "labels": ["dependencies", "auto-approve"],
                "groups": {
                    "default": {
                        "patterns": ["*"],
                        "exclude-patterns": ["aws-cdk*", "projen"],
                    }
                },
            }
        ],
    },
)

# Add auto-merge step to the auto-approve workflow
auto_approve_workflow = project.try_find_object_file(
    ".github/workflows/auto-approve.yml"
)
if auto_approve_workflow:
    auto_approve_workflow.add_override("jobs.approve.permissions.contents", "write")
    # Add checkout step before the merge step
    auto_approve_workflow.add_override(
        "jobs.approve.steps.1",
        {
            "name": "Checkout",
            "uses": GITHUB_ACTIONS["checkout"],
            "with": {"persist-credentials": False},
        },
    )
    auto_approve_workflow.add_override(
        "jobs.approve.steps.2",
        {
            "name": "Enable Pull Request Automerge",
            "run": 'gh pr merge --merge --auto "${{ github.event.pull_request.number }}"',
            "env": {"GH_TOKEN": "${{ secrets.PROJEN_GITHUB_TOKEN }}"},
        },
    )

# Loop through each environment in target_accounts
for env, account in target_accounts.items():
    if account:  # Check if account is not None
        # Adds customized projen tasks for executing cdk actions for each environment
        cdk_action_task(
            project,
            {
                "CDK_DEFAULT_ACCOUNT": account,
                "ENVIRONMENT": env,
            },
        )

        # Adds GitHub action workflows for deploying the CDK stacks to the target AWS account
        github_cicd(gh, account, env, python_version, aws_region, cdk_cli_version)

project.synth()
