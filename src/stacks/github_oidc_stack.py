import os
from typing import Any

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk.aws_iam import (
    ManagedPolicy,
    OpenIdConnectProvider,
    Role,
    WebIdentityPrincipal,
)
from constructs import Construct

from bin.git_helper import (
    GitHubRepositoryReference,
    build_github_actions_oidc_subject,
    get_git_repository_identity,
    resolve_repository_reference,
)

GITHUB_DOMAIN = "token.actions.githubusercontent.com"
DEFAULT_ROLE_NAME = "GitHubDeployRole"


class GitHubOIDCStack(Stack):
    """Create the IAM role that GitHub Actions workflows assume to deploy.

    The role trusts GitHub's immutable subject claim,
    `repo:OWNER@OWNER-ID/REPOSITORY@REPOSITORY-ID:CONTEXT`, so renaming, recreating, or
    transferring a repository cannot hand its trust to a different one. A repository still
    emitting legacy subjects must be opted into immutable subjects after this stack is
    deployed; there is no fallback to the legacy subject form.

    Args:
        scope: The scope in which to define this stack.
        id: The scoped construct ID.
        additional_repositories: Other repositories under the same owner allowed to assume
            the role. Each needs its numeric GitHub ID, read with
            `gh api repos/OWNER/NAME --jq .id`.
        subject_context: Subject context after the repository segment. Defaults to `*`, which
            trusts every ref of the trusted repositories. Narrow it to
            `environment:production` once the deploy workflows declare a GitHub environment.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        additional_repositories: list[GitHubRepositoryReference] | None = None,
        subject_context: str = "*",
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        repository = get_git_repository_identity()

        # Import the account's existing GitHub OIDC provider rather than creating one. AWS allows
        # a single provider per issuer URL per account, and this is what the stack did before it
        # dropped the aws-cdk-github-oidc dependency, so redeploying does not fight an existing one.
        provider = OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GithubProvider",
            f"arn:{self.partition}:iam::{self.account}:oidc-provider/{GITHUB_DOMAIN}",
        )

        subjects = [build_github_actions_oidc_subject(repository, subject_context)] + [
            build_github_actions_oidc_subject(
                resolve_repository_reference(repository, reference), subject_context
            )
            for reference in additional_repositories or []
        ]

        conditions: dict[str, Any] = {
            "StringLike": {f"{GITHUB_DOMAIN}:sub": subjects},
            "StringEquals": {f"{GITHUB_DOMAIN}:aud": "sts.amazonaws.com"},
        }

        deploy_role = Role(
            self,
            "GitHubDeployRole",
            # ty reads IPrincipal structurally and every jsii-generated PrincipalBase subclass
            # names its parameter `_statement` where the protocol says `statement`, so no CDK
            # principal satisfies the check. The runtime type is correct.
            assumed_by=WebIdentityPrincipal(  # ty: ignore[invalid-argument-type]
                provider.open_id_connect_provider_arn, conditions
            ),
            description="This role is used via GitHub Actions to deploy your AWS CDK stacks on your AWS account",
            managed_policies=[
                ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
            max_session_duration=Duration.hours(2),
            role_name=os.environ.get("GITHUB_DEPLOY_ROLE", DEFAULT_ROLE_NAME),
        )

        CfnOutput(self, "DeployRole", value=deploy_role.role_arn)
