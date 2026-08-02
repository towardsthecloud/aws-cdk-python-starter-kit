import os
from typing import Any

from aws_cdk import Duration, Stack
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
DEFAULT_ROLE_NAME = "GitHubActionsServiceRole"


class GitHubActionsOidcConstruct(Construct):
    """Create the IAM role that GitHub Actions workflows assume to deploy.

    The role trusts GitHub's immutable subject claim,
    `repo:OWNER@OWNER-ID/REPOSITORY@REPOSITORY-ID:CONTEXT`, so renaming, recreating, or
    transferring a repository cannot hand its trust to a different one. A repository still
    emitting legacy subjects must be opted into immutable subjects after this construct is
    deployed; there is no fallback to the legacy subject form.

    The account's OIDC provider for `token.actions.githubusercontent.com` is imported rather
    than created, because AWS allows one provider per issuer URL per account.

    Attributes:
        provider: The imported GitHub Actions OIDC identity provider.
        role: The IAM role GitHub Actions workflows assume.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        environment: str,
        additional_repositories: list[GitHubRepositoryReference] | None = None,
        max_session_duration: Duration | None = None,
        role_name: str | None = None,
    ) -> None:
        """
        Args:
            scope: The scope in which to define this construct.
            id: The scoped construct ID.
            environment: The GitHub environment allowed to assume the role. The trust policy
                is scoped to `environment:<environment>`, so a workflow job must declare the
                matching `environment:` to get a credential.
            additional_repositories: Other repositories under the same owner allowed to assume
                the role. Each needs its numeric GitHub ID, read with
                `gh api repos/OWNER/NAME --jq .id`. The ID is checked in rather than resolved
                during synthesis: a lookup would force every synthesizing CI job to hold a
                token able to read the other repository.
            max_session_duration: How long an assumed session lasts. Defaults to 2 hours.
            role_name: Name of the IAM role. Defaults to `GITHUB_DEPLOY_ROLE`, then
                `GitHubActionsServiceRole`.
        """
        super().__init__(scope, id)

        repository = get_git_repository_identity()

        stack = Stack.of(self)
        self.provider = OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GithubProvider",
            f"arn:{stack.partition}:iam::{stack.account}:oidc-provider/{GITHUB_DOMAIN}",
        )

        context = f"environment:{environment}"
        subjects = [build_github_actions_oidc_subject(repository, context)] + [
            build_github_actions_oidc_subject(
                resolve_repository_reference(repository, reference), context
            )
            for reference in additional_repositories or []
        ]

        conditions: dict[str, Any] = {
            "StringLike": {f"{GITHUB_DOMAIN}:sub": subjects},
            "StringEquals": {f"{GITHUB_DOMAIN}:aud": "sts.amazonaws.com"},
        }

        self.role = Role(
            self,
            "GitHubActionsServiceRole",
            # ty reads IPrincipal structurally and every jsii-generated PrincipalBase subclass
            # names its parameter `_statement` where the protocol says `statement`, so no CDK
            # principal satisfies the check. The runtime type is correct.
            assumed_by=WebIdentityPrincipal(  # ty: ignore[invalid-argument-type]
                self.provider.open_id_connect_provider_arn, conditions
            ),
            description=(
                "This role is used via GitHub Actions to deploy with AWS CDK on the target AWS account"
            ),
            managed_policies=[
                ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
            max_session_duration=max_session_duration or Duration.hours(2),
            role_name=role_name
            or os.environ.get("GITHUB_DEPLOY_ROLE", DEFAULT_ROLE_NAME),
        )
