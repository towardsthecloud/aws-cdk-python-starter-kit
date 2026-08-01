# AWS CDK Stacks: BaseStack and GitHubOIDCStack

This documentation details the structure and functionality of two pivotal stacks within our AWS CDK TypeScript project: `BaseStack` and `GitHubOIDCStack`. These stacks lay the groundwork for deploying AWS resources with specific configurations and capabilities, tailored to different deployment stages and integration with GitHub Actions for CI/CD processes.

## BaseStack

The `BaseStack` serves as a foundational stack that you can use to start instantiation your custom and cdk-lib constructs.

### Properties

- `environment`: Optional. Specifies the deployment stage (e.g., `dev`, `test`, `staging`, `production`). It's crucial for tailoring the stack configuration to the target environment.

### Example Usage

```python
import os

import aws_cdk as cdk
from stacks.base_stack import BaseStack

# Inherit environment variables from npm run commands (displayed in .projen/tasks.json)
environment = os.environ.get("ENVIRONMENT", "dev")
aws_environment = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))

# Instantiate the CDK app
app = cdk.App()

BaseStack(app, f"BaseStack-{environment}", env=aws_environment)
```

## GitHubOIDCStack

The GitHubOIDCStack is designed to facilitate secure CI/CD workflows by integrating AWS resources with GitHub Actions via OpenID Connect (OIDC). This allows for a more secure and streamlined deployment process directly from GitHub Actions.

### Features

- GitHub Actions OIDC Provider: Imports the account's OIDC provider for `token.actions.githubusercontent.com`, the trust anchor between GitHub and AWS. AWS allows one provider per issuer URL per account, so the stack references it instead of creating it.
- GitHub Deploy Role: Creates an IAM role with AdministratorAccess managed policy. This role is assumable by GitHub Actions workflows, granting them the permissions needed to deploy resources.

### GitHub immutable OIDC subjects

The deploy role trusts GitHub's immutable subject claim:

```text
repo:OWNER@OWNER-ID/REPOSITORY@REPOSITORY-ID:*
```

The numeric IDs pin the trust to one repository. Rename it, delete and recreate it, or transfer it to another owner, and the old trust no longer matches.

Your repository has to emit that claim. Opt in through the API, then check it took:

```bash
gh api -X PUT repos/OWNER/REPOSITORY/actions/oidc/customization/sub -F use_default=true -F use_immutable_subject=true
gh api repos/OWNER/REPOSITORY/actions/oidc/customization/sub --jq .use_immutable_subject
```

Deploy the stack first, then flip the setting. There's no fallback to the legacy `repo:OWNER/REPOSITORY:*` subject, so a repository that still emits the old claim can't assume the role.

Synthesis resolves your repository's IDs on its own. GitHub Actions passes them in `GITHUB_REPOSITORY_ID` and `GITHUB_REPOSITORY_OWNER_ID`, so no workflow needs a token. Local synth reads the `origin` remote and calls `gh api`, so run `gh auth login` once.

### Configuration

Both arguments are optional:

- `additional_repositories`: other repositories under the same owner allowed to assume the role. Each needs its name and numeric GitHub ID, read with `gh api repos/OWNER/NAME --jq .id`. The ID is checked in rather than looked up during synth, because a lookup would hand every synthesizing CI job a token able to read the other repository.
- `subject_context`: the part of the subject after the repository. Defaults to `*`, which trusts every ref. Narrow it to `environment:production` once the deploy workflows declare a GitHub environment.

```python
from bin.git_helper import GitHubRepositoryReference

GitHubOIDCStack(
    app,
    f"GitHubOIDCStack-{environment}",
    env=aws_environment,
    additional_repositories=[GitHubRepositoryReference(name="my-cdk-app", id="123456789")],
)
```

### Example Usage

```python
import os

import aws_cdk as cdk
from stacks.github_oidc_stack import GitHubOIDCStack

# Inherit environment variables from npm run commands (displayed in .projen/tasks.json)
environment = os.environ.get("ENVIRONMENT", "dev")
aws_environment = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))

# Instantiate the CDK app
app = cdk.App()

GitHubOIDCStack(app, f"GitHubOIDCStack-{environment}", env=aws_environment)
```
