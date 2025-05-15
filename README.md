# [![AWS CDK Python Starterkit header](./icons/github-title-banner.png)](https://towardsthecloud.com)

# AWS CDK Python Starterkit

> The perfect starter kit to create and deploy an AWS CDK App using Python on your AWS account in less than 5 minutes using GitHub actions!

[![Build Status](https://github.com/towardsthecloud/aws-cdk-starterkit/actions/workflows/build.yml/badge.svg)](https://github.com/towardsthecloud/aws-cdk-starterkit/actions/workflows/build.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Intro

Welcome to the starting line of your next AWS CDK project. This repository is crafted to supercharge your project's setup with AWS CDK Python, projen, and GitHub actions, ensuring a smooth and efficient deployment to your AWS account.

> [!TIP]
> **Launch Faster on AWS and Become Fully Secure From Day One!** Our AWS Landing Zone Foundation service helps B2B companies achieve SOC 2 compliance 90% faster,  redirect 30% of engineering time back to product development all while eliminating the six-figure cost of specialized cloud engineers. so you can focus on shipping your product, instead of worrying about managing your infrastructure on AWS.
>
> [Schedule a free introduction call](https://towardsthecloud.com/contact) to discover how we can deliver 10x the value of securing and building your infrastructure on AWS for a fraction of the cost of a full-time cloud engineer.

<details><summary>☁️ <strong>Learn more about our unique AWS Foundation Service</strong></summary>

<br/>

Is AWS complexity draining your engineering resources? Most B2B startups and growing businesses struggle with overwhelming configuration options, time-consuming compliance requirements, and diverting valuable developer talent away from core product development. Without specialized AWS expertise, you risk security vulnerabilities, mounting technical debt, and delayed time-to-market. All while your competitors race ahead.

Traditional AWS consultancies only compound this problem. They're incentivized to bill by the hour, extending projects indefinitely rather than focusing on your business outcomes. We take the opposite approach. Our fixed-price subscription model proves how confident we are in delivering results, not just billable hours. We succeed when you succeed, aligning our incentives with your growth rather than your AWS complexity.

## Our Solution: Enterprise-Grade AWS Foundation

We deliver an enterprise-grade AWS Landing Zone built entirely in AWS CDK coupled with a support and consultacy foundation that grows with your business needs. Here's what we'll deliver to you:

### We deploy a [Secure and Compliant Landing Zone](https://towardsthecloud.com/services/aws-landing-zone)
- Multi-account architecture with proper security boundaries
  - Achieves a **100% score on the industry-standard [CIS AWS Foundation Benchmark](https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html)**
  - **Achieves a 96% rating on AWS's own [foundational security best practices](https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html)**
- Setup entirely using AWS CDK (Infrastructure as Code)
- Budget monitoring and notifications across all accounts
- Deploy changes quickly through GitHub Actions
- We're continuously adding new features as listed on our [Roadmap](https://github.com/towardsthecloud/aws-cdk-landing-zone-roadmap)

### We upskill and accelerate your Developers
- They gain access to our library of ready-to-use, security-hardened AWS CDK components
- They receive guidance on how to utilize AWS best practices for your architecture so you avoid technical debt later on

### We monitor and maintain the multi-account setup & provide ongoing support
- Gain new Landing Zone features once they're released and get free maintenance and security updates
- Get priority support through Slack/Teams whenever you need assistance with infrastructure challenges
- We proactively do quarterly [security](https://towardsthecloud.com/services/aws-security-review) and [cost optimization](https://towardsthecloud.com/services/aws-cost-optimization) assessments to verify AWS account compliance and provide advice to reduce your AWS bill

### What This Means For Your Business
- **30% Lower TCO**: Cut your Total Cost of Ownership (TCO) by up to 30% through right-sized resources and architectural optimization while eliminating the $150K+ annual cost of a specialized AWS hire
- **Close Enterprise Deals Faster**: Win enterprise clients with SOC2 compliance ready in weeks instead of months - our clients report 50% faster sales cycles with security-conscious customers
- **Unleash Your Development Team**: Redirect up to 30% of engineering time from infrastructure back to revenue-generating product features with our pre-built, compliant components
- **Scale Without Infrastructure Headaches**: Grow from startup to enterprise without ever rebuilding your foundation - our architecture scales seamlessly from your first customer to your millionth

We deliver all of this as a [simple subscription service](https://towardsthecloud.com/pricing). No large upfront costs, no lock-in. You'll essentially get a solid and secure landing zone foundation + a decade of AWS expertise without having to hire a full-time Cloud Engineer.

<a href="https://towardsthecloud.com/contact"><img alt="Schedule a free introduction call" src="https://img.shields.io/badge/schedule%20a%20free%20introduction%20call-success.svg?style=for-the-badge"/></a>
</details>

## Features

- ⚡ Rapid Setup: Jumpstart your project within minutes by tweaking a [single configuration file](./.projenrc.py). Spend less time on boilerplate and more on building.
- 🤹‍♂️ Multi-Account Flexibility: Ready for enterprises, this starter kit supports multi-account setups right from the start, enabling scalable and segregated cloud environments.
- 🤖 Automated Deploy Pipelines: Embrace CI/CD with out-of-the-box GitHub Actions workflows, automating your deployment processes for efficiency and reliability.
- 🏗️ Project structure: The [project is structured](#project-structure) in a clean and intuitive way that allows you to easily manage your constructs and stacks for this CDK App.
- 🛡️ Seamless Security: Leverage OpenID Connect for secure AWS deployments. Authenticate your GitHub Actions workflows directly with AWS, eliminating the need for stored credentials or long-lived secrets.
- 📦 Improved Dependency Management: Dependencies and virtualenvs are managed with Poetry.
- 📏 Fast Linting & formatting: Ruff is installed as a dev dependency right out of the box!
- 🚀 Enhanced Pull Requests: Benefit from a built-in, fancy pull request template, making code reviews more structured and informative.

## Setup Guide

All the config that is needed to personalise the CDK App to your environment is defined in the [.projenrc.py file](./.projenrc.py).

**To get started, follow these steps:**

1. Fork / clone this repository.

2. Add a Personal Access Token to the repository settings on GitHub, follow these [instructions for setting up a fine-grained personal access token](https://projen.io/docs/integrations/github/#fine-grained-personal-access-token-beta).

3. Install the AWS CDK CLI and projen: `npm install -g aws-cdk projen`

4. Install the projects dependencies using: `poetry install`

5. Customize the AWS Region and Account IDs in the [.projenrc.py](./.projenrc.py) file to match your AWS setup:

```python
# Define the AWS region for the CDK app and github workflows
# Default to us-east-1 if AWS_REGION is not set in your environment variables
aws_region = os.getenv("AWS_REGION", "us-east-1")

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
```

6. Run `projen` to generate the github actions workflow files.

7. AWS CLI Authentication: Ensure you're logged into an AWS Account (one of the ones you configured in step 4) via the AWS CLI. If you haven't set up the AWS CLI, [then follow this guide](https://towardsthecloud.com/set-up-aws-cli-aws-sso))

8. Deploy the CDK toolkit stack to your AWS environment with `cdk bootstrap` if it's not already set up.

9. Deploy the GitHub OIDC Stack to enable GitHub Actions workflow permissions for AWS deployments. For instance, if you set up a `dev` environment, execute `projen dev:deploy`.

10. Commit and push your changes to the `main` branch to trigger the CDK deploy pipeline in GitHub.

Congratulations 🎉! You've successfully set up your project.

## Project Structure

When working on smaller projects using infrastructure as code, where you deploy single applications that don’t demand extensive maintenance or collaboration from multiple teams, it’s recommended to structure your AWS CDK project in a way that enables you to deploy both the application and infrastructure using a single stack.

However, as projects evolve to encompass multiple microservices and a variety of stateful resources (e.g., databases), the complexity inherently increases.

In such cases, adopting a more sophisticated AWS CDK project organization becomes critical. This ensures not only the ease of extensibility but also the smooth deployment of each component, thereby supporting a more robust development lifecycle and facilitating greater operational efficiency.

To cater to these advanced needs, your AWS CDK project should adopt a modular structure. This is where the **AWS CDK Python Starterkit** shines ✨.

Here’s a closer look at how this structure enhances maintainability and scalability:

```bash
.
├── cdk.json
├── poetry.lock
├── pyproject.toml
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
│  ├── bin
│  │  ├── cicd_helper.py
│  │  ├── env_helper.py
│  │  └── git_helper.py
│  ├── custom_constructs
│  │  ├── __init__.py
│  │  ├── base_construct.py
│  │  ├── network_construct.py
│  │  └── README.md
│  └── stacks
│     ├── __init__.py
│     ├── base_stack.py
│     ├── github_oidc_stack.py
│     └── README.md
└── tests
   ├── __init__.py
   └── test_example.py
```

As you can see in the above tree diagram, the way this project is setup it tries to segment it into logical units, such as **constructs** for reusable infrastructure patterns, **stacks** for deploying groups of resources and **assets** for managing source code of containers and lambda functions.

Here is a brief explanation of what each section does:

- `src/assets`: Organizes the assets for your Lambda functions and ECS services, ensuring that the application code is neatly encapsulated with the infrastructure code.
- `src/bin`: Contains utility scripts (e.g., `cicd_helper.py`, `env_helper.py`, `git_helper.py`) that streamline environment setup and integration with CI/CD pipelines.
- `src/custom_constructs`: Houses the core building blocks of your infrastructure. These constructs can be composed into higher-level abstractions, promoting reusability across different parts of your infrastructure. Check out the [README in the constructs folder](./src/custom_constructs/README.md) to read how you can utilize environment-aware configurations.
- `src/stacks`: Dedicated to defining stacks that represent collections of AWS resources (constructs). This allows for logical grouping of related resources, making it simpler to manage deployments and resource dependencies. Check out the [README in the stacks folder](./src/stacks/README.md) to read how you can instantiate new stacks.
- `src/lib/main.ts`: This is where the CDK app is instantiated.
- `test`: Is the location to store your unit or integration tests (powered by jest)

## AWS CDK Starterkit for TypeScript Users

> **Looking for the TypeScript version of this AWS CDK starter kit?** Check out the [AWS CDK Starterkit](https://github.com/towardsthecloud/aws-cdk-starterkit) for a tailored experience that leverages the full power of AWS CDK with TypeScript.

## Acknowledgements

A heartfelt thank you to the creators of [projen](https://github.com/projen/projen). This starter kit stands on the shoulders of giants, made possible by their pioneering work in simplifying cloud infrastructure projects!

## Author

[Danny Steenman](https://towardsthecloud.com/about)

[![](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/towardsthecloud)
[![](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)](https://twitter.com/dannysteenman)
[![](https://img.shields.io/badge/GitHub-2b3137?style=for-the-badge&logo=github&logoColor=white)](https://github.com/towardsthecloud)
