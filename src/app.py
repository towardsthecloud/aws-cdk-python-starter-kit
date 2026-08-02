import os

import aws_cdk as cdk

from bin.env_helper import (
    DEFAULT_ENVIRONMENT,
    create_env_resource_name,
    extract_cleaned_branch_name,
)
from stacks.foundation_stack import FoundationStack
from stacks.starter_stack import StarterStack

# Inherit environment variables from the `uv run projen` commands (see .projen/tasks.json)
environment = os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT)
aws_environment = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

# Instantiate the CDK app
app = cdk.App()

# The FoundationStack holds account-level infrastructure: the GitHub Actions deploy role and
# the CDK toolkit cleaner. Deploy it once per account, and never from a feature branch, which
# would otherwise recreate the very role its own pipeline assumes.
if not os.environ.get("GIT_BRANCH_REF"):
    FoundationStack(
        app,
        create_env_resource_name("FoundationStack"),
        environment=environment,
        env=aws_environment,
    )

# Create a new stack with your resources
StarterStack(
    app,
    create_env_resource_name("StarterStack"),
    environment=environment,
    env=aws_environment,
)

# Tag all resources in CloudFormation with the environment name
cdk.Tags.of(app).add("environment", environment)

# Tag branch based deploys with the branch name to easily identify the branch in the AWS console
branch_name = extract_cleaned_branch_name(os.environ.get("GIT_BRANCH_REF"))
if branch_name:
    cdk.Tags.of(app).add("branch", branch_name)

# Synthesize the CDK app
app.synth()
