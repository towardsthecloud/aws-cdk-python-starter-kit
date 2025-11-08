import os

from projen import YamlFile
from projen.awscdk import AwsCdkPythonApp

from src.bin.cicd_helper import github_cicd
from src.bin.env_helper import cdk_action_task

# Define the python module name and set the python version
python_module_name = "src"
python_version = "3.13"

# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

project = AwsCdkPythonApp(
    author_email="danny@towardsthecloud.com",
    author_name="Danny Steenman",
    cdk_version_pinning=True,
    cdk_version="2.221.0",  # Find the latest CDK version here: https://pypi.org/project/aws-cdk-lib
    cdk_cli_version="2.1031.0",  # Find the latest CDK CLI version https://pypi.org/project/aws-cdk-cli/
    module_name=python_module_name,
    name="aws-cdk-python-starter-kit",
    description="Create and deploy an AWS CDK app on your AWS account in less than 5 minutes using GitHub actions!",
    version="2.100.0",
    app_entrypoint=f"{python_module_name}/app.py",
    deps=["aws-cdk-github-oidc"],
    dev_deps=["projen@0.98.4", "ruff"],  # Find the latest projen version here: https://pypi.org/project/projen/
    github_options={
        "pull_request_lint_options": {
            "semantic_title_options": {
                "types": ["feat", "fix", "chore", "refactor", "perf", "docs", "style", "test", "build", "ci"],
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

# Define the target AWS accounts for the different environments
target_accounts = {
    "dev": "987654321012",
    "test": "123456789012",
    "staging": None,
    "production": None,
}

gh = project.github

# Add Dependabot configuration for pip
YamlFile(
    project,
    ".github/dependabot.yml",
    obj={
        "version": 2,
        "updates": [
            {
                "package-ecosystem": "pip",
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
auto_approve_workflow = project.try_find_object_file(".github/workflows/auto-approve.yml")
if auto_approve_workflow:
    auto_approve_workflow.add_override("jobs.approve.permissions.contents", "write")
    # Add checkout step before the merge step
    auto_approve_workflow.add_override(
        "jobs.approve.steps.1",
        {"name": "Checkout", "uses": "actions/checkout@v5"},
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
        github_cicd(gh, account, env, python_version)

project.synth()
