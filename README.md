# [![AWS CDK Python Starter Kit header](./images/github-title-banner.png)](https://towardsthecloud.com)

## AWS CDK Python Starter Kit

Deploy an AWS CDK app written in Python through GitHub Actions, without storing a single AWS credential. One projen config file generates the workflows, the tasks and the packaging.

### 🚀 Features

- **⚡ One file to configure**: Set your accounts and region in [.projenrc.py](./.projenrc.py), run `uv run projen`, and the workflows, tasks and [pyproject.toml](./pyproject.toml) regenerate to match
  - The CDK CLI is pinned in the lockfile alongside everything else, so your machine and CI run the same version
  - [Ruff](https://github.com/astral-sh/ruff) for linting and formatting, [ty](https://github.com/astral-sh/ty) for type checking, both wired into the build
  - A [project structure](#project-structure) that separates constructs, stacks and aspects instead of piling them into one file
- **🛡️ Keyless deploys**: GitHub Actions assumes an IAM role through OIDC, so there's nothing in your repository secrets to leak. The trust policy pins GitHub's immutable subject claim, so renaming or recreating the repo can't hand its access to a different one
- **🤖 Chained multi-account pipelines**: Push to `main` and `test` deploys. `production` runs only after `test` succeeds
- **💬 CDK diff on every PR**: The [diff commenter](https://github.com/marketplace/actions/aws-cdk-diff-pr-commenter) posts what your change does to production before anyone approves it
- **💻 Per-branch environments**: Push a feature branch and it gets its own stacks in the shared test account. Delete the branch and they go with it. Branch deploys use CDK express mode, [up to 4x faster](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-cloudformation-cdk/) than a normal deploy
- **🧹 Aspects you can switch on**: Four [aspects](./src/aspects/README.md) that catch an IAM role with no permission boundary, an unencrypted bucket, a bucket open to the public, and a VPC on public address space
- **📦 Dependency updates that wait**: Dependabot opens grouped weekly PRs and nothing merges itself. uv skips any release younger than 7 days, so a bad publish has a week to get caught before it can reach your lockfile

<!-- TIP-LIST:START -->
> [!TIP]
> **We eliminate AWS complexity so you ship faster, spend less, and stay compliant.**
>
> Our managed AWS service gives you three things: a production-grade AWS CDK Landing Zone with built-in compliance controls, proactive monitoring that stops cost waste and security drift, and senior AWS expertise that speeds up your team's delivery.
>
> Book a free demo to see where you stand and what we'd fix first:
>
> <a href="https://towardsthecloud.com/services/aws-cdk-landing-zone#cta"><img alt="Book a Free Demo" src="https://img.shields.io/badge/Book%20a%20Free%20Demo-success.svg?style=for-the-badge"/></a>
>
> <details>
> <summary>⚡ <strong>See the symptoms of a missing AWS foundation and how we solve them</strong></summary>
> <br/>
>
> AWS starts simple. Then you scale: production and staging blur together, resources multiply without owners, IAM policies accumulate exceptions, security findings pile up in backlogs, and the bill climbs month after month.
>
> Those are symptoms of a missing AWS foundation. Without one, your developers spend more time fixing problems than shipping features.
>
> **We provide that foundation and own it entirely, so your team focuses on shipping, not firefighting.**
>
> ### Here's what's included:
>
> **1. We Provision a Secure [AWS CDK Landing Zone](https://towardsthecloud.com/services/aws-cdk-landing-zone) That Accelerates Compliance**
>
> - Multi-account architecture with security controls and compliance guardrails from day one
> - Scores 100% on the [CIS AWS Foundations Benchmark](https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html) and 96% on [AWS Foundational Security Best Practices](https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html)
> - Those benchmarks map straight to **SOC 2**, **HIPAA**, and **PCI-DSS** controls, cutting months from your compliance timeline
>
> **2. We Monitor Proactively to Stop Cost Waste and Security Drift**
>
> - Quarterly cost reviews catch unattached volumes, oversized instances, and orphaned resources before they compound. AWS spend drops 20-30% on average, with [outliers hitting 60+%](https://towardsthecloud.com/services/aws-cost-optimization#case-study)
> - Continuous security monitoring across all accounts catches misconfigurations immediately. You get alerts while issues are still fixable, not after they're breaches
>
> **3. We Provide Senior AWS Expertise That Speeds Up Delivery**
>
> - Your developers get production-ready IaC templates for common patterns: multi-AZ applications, event-driven architectures, secure data pipelines. What takes weeks of research ships in hours
> - Architecture guidance on VPC design, IAM policies, disaster recovery, and observability from engineers who've solved these problems at enterprise scale
>
> [*"We achieved a perfect security score in days, not months."*](https://towardsthecloud.com/blog/case-study-accolade)
> *Galen Simmons, CEO of Accolade (Y Combinator startup)*
>
> </details>
<!-- TIP-LIST:END -->

### Setup Guide

Everything you need to change lives in [.projenrc.py](./.projenrc.py).

**To get started, follow these steps:**

1. Click the green ["Use this template"](https://github.com/new?template_name=aws-cdk-python-starter-kit&template_owner=towardsthecloud) button to create a new repository based on this starter kit.

2. Add a Personal Access Token to the repository settings on GitHub, follow these [instructions for setting up a fine-grained personal access token](https://projen.io/docs/integrations/github/#fine-grained-personal-access-token-beta).

3. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run `uv sync`. That pulls in the pinned CDK CLI too, so you don't need a global `npm install -g aws-cdk`.

4. Customize the AWS Region and Account IDs in the [.projenrc.py](./.projenrc.py) file to match your AWS setup:

```python
# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

# Set the CDK_DEFAULT_REGION environment variable for the projen tasks,
# so the CDK CLI knows which region to use
project.tasks.add_environment("CDK_DEFAULT_REGION", aws_region)

# Defines the environment configurations for the CDK application.
# The order of this list is the deployment order in the pipeline: each environment's workflow
# is chained onto the completion of the previous one, so `production` only runs after `test`
# succeeded. Enable branch deployments on the lower environments only.
environment_configs = [
    EnvironmentConfig(name="test", account_id="987654321012", enable_branch_deploy=True),
    EnvironmentConfig(name="production", account_id="123456789012", enable_branch_deploy=False),
]
```

5. Run `uv run projen` to generate the GitHub Actions workflow files.

6. Log into one of the accounts you set in step 4 with the AWS CLI. If you haven't set that up yet, [follow this guide](https://towardsthecloud.com/set-up-aws-cli-aws-sso).

7. Run `uv run cdk bootstrap` if the account doesn't have the CDK toolkit stack yet.

8. Deploy the FoundationStack to create the GitHub Actions deploy role. For the `test` environment that's `uv run projen test:deploy:all`.

   Synthesizing locally reads your repository's numeric GitHub IDs through `gh api`, so run `gh auth login` first.

9. Opt the repository into immutable OIDC subject claims:

   ```bash
   gh api -X PUT repos/OWNER/REPOSITORY/actions/oidc/customization/sub -F use_default=true -F use_immutable_subject=true
   ```

   The deploy role trusts only the immutable claim and there's no fallback to the old one, so do this after step 8, never before. [`src/stacks/README.md`](./src/stacks/README.md#github-immutable-oidc-subjects) explains why.

10. Push to `main`. The pipeline takes it from there.

### Project Structure

One stack is fine while your app is a single service owned by one team. Put it all in `StarterStack` and move on.

That stops working once you have several services and stateful resources on different lifecycles, because every deploy then touches everything, including the database you'd rather nobody touched.

So this kit splits the app along the seams that change independently:

```bash
.
├── cdk.json
├── pyproject.toml
├── uv.lock
├── README.md
├── src
│  ├── __init__.py
│  ├── app.py
│  ├── assets
│  │  ├── ecs
│  │  │  └── hello-world
│  │  │     └── Dockerfile
│  │  └── lambda
│  │     └── hello-world
│  │        └── lambda_function.py
│  ├── aspects
│  │  ├── __init__.py
│  │  ├── permission_boundary_aspect.py
│  │  ├── s3_aspect.py
│  │  ├── vpc_aspect.py
│  │  └── README.md
│  ├── bin
│  │  ├── cicd_helper.py
│  │  ├── env_helper.py
│  │  └── git_helper.py
│  ├── custom_constructs
│  │  ├── __init__.py
│  │  ├── base_construct.py
│  │  ├── github_actions_oidc_construct.py
│  │  ├── network_construct.py
│  │  └── README.md
│  └── stacks
│     ├── __init__.py
│     ├── foundation_stack.py
│     ├── starter_stack.py
│     └── README.md
└── tests
   ├── __init__.py
   ├── test_aspects.py
   ├── test_env_helper.py
   ├── test_foundation_stack.py
   └── test_git_helper.py
```

Each directory has one job:

- `src/aspects`: Rules applied to every construct in a scope, like attaching a permission boundary to each IAM role. The [aspects README](./src/aspects/README.md) covers what each one catches and how to write your own.
- `src/assets`: Lambda handler code and container Dockerfiles, sitting next to the infrastructure that ships them.
- `src/bin`: Helpers shared by the CDK app and `.projenrc.py`: resource naming, workflow generation, and resolving this repository's GitHub identity.
- `src/custom_constructs`: Reusable building blocks you compose into stacks. The [constructs README](./src/custom_constructs/README.md) covers the environment-aware pattern. It's called `custom_constructs` because a directory named `constructs` would shadow the `constructs` package every CDK module imports.
- `src/stacks`: `FoundationStack` holds the account-level pieces (the deploy role and the toolkit cleaner), and `StarterStack` is where your own resources go. See the [stacks README](./src/stacks/README.md).
- `src/app.py`: Where the app gets built and the stacks get their names.
- `tests`: pytest tests. `uv run projen test` runs them together with Ruff and ty.

### Branch-based Deployments

Push a feature branch and the `cdk-deploy-test-branch` workflow deploys its own copy of the stacks, named after the branch: `StarterStack-add-api` rather than `StarterStack-test`. Several developers can work against the same AWS account without stepping on each other.

`FoundationStack` is skipped during branch deployments. A feature branch has no business recreating the role its own pipeline assumes.

Deploys and destroys in the `test` environment use CDK express mode, which is meaningfully faster and safe for stacks that only exist for the life of a branch.

Deleting the branch triggers `cdk-destroy-test-branch`, which tears the stacks down. Turn on **"Automatically delete head branches"** in your repository settings so merging a pull request cleans up after itself. `main` and the automation branches are excluded.

The generated projen tasks mirror this:

```bash
uv run projen test:synth               # synthesize every stack
uv run projen test:deploy:all          # deploy every stack
uv run projen test:deploy:stack -- StarterStack-test
uv run projen test:branch:deploy:all   # deploy this branch's stacks
uv run projen test:branch:deploy:hotswap  # fast inner loop, branch only
uv run projen test:branch:destroy:all
uv run projen test:ls
```

### AWS CDK Starter Kit for TypeScript Users

> Prefer TypeScript? The [AWS CDK Starter Kit](https://github.com/towardsthecloud/aws-cdk-starter-kit) is the same setup, written in TypeScript.

### Acknowledgements

Thanks to the [projen](https://github.com/projen/projen) team. Every workflow, task and config file in this repo is generated, and none of it would exist without their work.

### Author

[Danny Steenman](https://towardsthecloud.com/about)

[![](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/towardsthecloud)
[![](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)](https://twitter.com/dannysteenman)
[![](https://img.shields.io/badge/GitHub-2b3137?style=for-the-badge&logo=github&logoColor=white)](https://github.com/towardsthecloud)
