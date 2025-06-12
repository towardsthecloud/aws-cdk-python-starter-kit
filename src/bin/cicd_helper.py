import os

from projen import github


def github_cicd(gh, account, env, python_version):
    # Add a GitHub workflow for deploying the CDK stacks to the AWS account
    cdk_deployment_workflow = github.GithubWorkflow(gh, f"cdk-deploy-{env}")
    cdk_deployment_workflow.on(push={"branches": ["main"]} if env != "production" else None, workflow_dispatch={})

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
                    {
                        "name": "Checkout repository",
                        "uses": "actions/checkout@v4",
                    },
                    {
                        "name": "Setup python environment",
                        "uses": "actions/setup-python@v5",
                        "with": {
                            "python-version": python_version,
                        },
                    },
                    {
                        "name": "Configure AWS credentials",
                        "uses": "aws-actions/configure-aws-credentials@v4",
                        "with": {
                            "role-to-assume": f"arn:aws:iam::{account}:role/GitHubDeployRole",
                            "aws-region": os.getenv("CDK_DEFAULT_REGION"),
                        },
                    },
                    {
                        "name": "Install dependencies",
                        "run": "pip install -r requirements.txt -r requirements-dev.txt",
                    },
                    {
                        "name": "Install cdk & projen",
                        "run": "npm install -g aws-cdk projen",
                    },
                    {
                        "name": f"Run CDK synth for the {env.upper()} environment",
                        "run": f"projen {env}:synth",
                    },
                    {
                        "name": f"Deploy CDK to the {env.upper()} environment on AWS account {account}",
                        "run": f"projen {env}:deploy",
                    },
                ],
            },
        }
    )
