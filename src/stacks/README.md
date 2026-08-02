# AWS CDK Stacks: StarterStack and FoundationStack

Two stacks ship with this kit. `FoundationStack` holds the account-level plumbing your pipeline needs, and `StarterStack` is where your own infrastructure goes.

Both are instantiated in [`app.py`](../app.py) with a name from `create_env_resource_name`, so a `test` deployment produces `StarterStack-test` and a branch deployment produces `StarterStack-add-api`.

## StarterStack

The starting point for your own resources. Add constructs in the constructor, and add another stack next to this one once a group of resources grows its own lifecycle.

### Properties

- `environment`: Optional. The deployment stage (`test`, `production`, and so on).

### Example Usage

```python
from aws_cdk import aws_s3 as s3

# In the constructor:
s3.Bucket(
    self,
    "MyBucket",
    versioned=True,
    encryption=s3.BucketEncryption.S3_MANAGED,
)
```

## FoundationStack

Account-level infrastructure that everything else depends on. Deploy it once per AWS account.

`app.py` skips it during branch deployments: a feature branch has no business recreating the role its own pipeline assumes.

### Features

- **GitHub Actions OIDC provider**: imports the account's provider for `token.actions.githubusercontent.com`, the trust anchor between GitHub and AWS. AWS allows one provider per issuer URL per account, so the stack references it rather than creating it.
- **GitHub deploy role**: an IAM role with the AdministratorAccess managed policy, assumable from GitHub Actions through OIDC.
- **CDK toolkit cleaner**: deletes CDK asset objects and images no deployed stack references any more. Without it the staging bucket and ECR repository grow with every deployment.

### Properties

- `environment`: Required. The deployment stage, which also names the GitHub environment the deploy role trusts.
- `additional_repositories`: Optional. Other repositories under the same owner allowed to assume the role. Each needs its name and numeric GitHub ID, read with `gh api repos/OWNER/NAME --jq .id`. The ID is checked in rather than looked up during synth, because a lookup would hand every synthesizing CI job a token able to read the other repository.
- `max_session_duration`: Optional. How long an assumed session lasts. Defaults to 2 hours.
- `role_name`: Optional. Defaults to `GITHUB_DEPLOY_ROLE`, then `GitHubActionsServiceRole`.

### GitHub immutable OIDC subjects

The deploy role trusts GitHub's immutable subject claim:

```text
repo:OWNER@OWNER-ID/REPOSITORY@REPOSITORY-ID:environment:ENVIRONMENT
```

The numeric IDs pin the trust to one repository. Rename it, delete and recreate it, or transfer it to another owner, and the old trust no longer matches.

The `environment:` segment means a workflow job must declare a matching `environment:` to get a credential. The generated deploy workflows already do.

Your repository has to emit the immutable claim. Opt in through the API, then check it took:

```bash
gh api -X PUT repos/OWNER/REPOSITORY/actions/oidc/customization/sub -F use_default=true -F use_immutable_subject=true
gh api repos/OWNER/REPOSITORY/actions/oidc/customization/sub --jq .use_immutable_subject
```

Deploy the stack first, then flip the setting. There's no fallback to the legacy `repo:OWNER/REPOSITORY:*` subject, so a repository that still emits the old claim can't assume the role.

Synthesis resolves your repository's IDs on its own. GitHub Actions passes them in `GITHUB_REPOSITORY_ID` and `GITHUB_REPOSITORY_OWNER_ID`, so no workflow needs a token. Local synth reads the `origin` remote and calls `gh api`, so run `gh auth login` once.

### Example Usage

```python
import os

import aws_cdk as cdk
from bin.env_helper import create_env_resource_name
from bin.git_helper import GitHubRepositoryReference
from stacks.foundation_stack import FoundationStack

environment = os.environ.get("ENVIRONMENT", "dev")
aws_environment = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))

app = cdk.App()

FoundationStack(
    app,
    create_env_resource_name("FoundationStack"),
    environment=environment,
    env=aws_environment,
    additional_repositories=[GitHubRepositoryReference(name="my-cdk-app", id="123456789")],
)
```
