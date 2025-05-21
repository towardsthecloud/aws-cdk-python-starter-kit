import os

from projen import github
from projen.awscdk import AwsCdkPythonApp

from src.bin.cicd_helper import github_cicd
from src.bin.env_helper import cdk_action_task

# Define the python module name and set the python version
python_module_name = "src"
python_version = "3.11"

# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

project = AwsCdkPythonApp(
    author_email="danny@towardsthecloud.com",
    author_name="Danny Steenman",
    cdk_version="2.197.0",        # Find the latest CDK version here: https://pypi.org/project/aws-cdk-lib
    cdk_cli_version="2.1016.0", # # Find the latest CDK CLI version https://www.npmjs.com/package/aws-cdk
    cdk_version_pinning=True,
    module_name=python_module_name,
    name="aws-cdk-python-starterkit",
    license="Apache-2.0",
    description="Create and deploy an AWS CDK app on your AWS account in less than 5 minutes using GitHub actions!",
    version="0.1.0",
    app_entrypoint=f"{python_module_name}/app.py",
    deps=["aws-cdk-github-oidc"],
    dev_deps=["projen@0.92.6", "ruff"], # Find the latest projen version here: https://pypi.org/project/projen/
    github_options={
        "pull_request_lint": False,
    },
    git_ignore_options={
        "ignore_patterns": [
            "__pycache__",
            "__pycache__/",
            ".python-version",
            "!.eslintrc.js",
            ".cache",
            ".coverage.*",
            ".coverage",
            ".DS_Store",
            ".env",
            ".mypy_cache",
            ".pytest_cache",
            ".Python",
            ".venv/",
            ".vscode",
            "*.js",
            "*.log",
            "*.manifest",
            "*.pyc",
            "*.spec",
            "*.zip",
            "**/cdk-test-report.xml",
            "*node_modules*",
            "build/",
            "coverage/",
            "dist/",
            "downloads/",
            "env/",
            "ENV/",
            "htmlcov/",
            "sdist/",
            "var/",
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

gh = github.GitHub(project)
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
        github_cicd(gh, account, env, python_version)  # Python 3.11

project.synth()
