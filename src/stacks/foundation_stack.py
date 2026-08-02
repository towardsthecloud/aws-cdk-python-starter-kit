from aws_cdk import CfnOutput, Duration, Stack
from cloudstructs import ToolkitCleaner
from constructs import Construct

from bin.git_helper import GitHubRepositoryReference
from custom_constructs.github_actions_oidc_construct import GitHubActionsOidcConstruct


class FoundationStack(Stack):
    """Account-level infrastructure that every other stack depends on.

    Holds the GitHub Actions deploy role and the CDK toolkit cleaner. Deploy it once per AWS
    account; it is excluded from branch deployments in `app.py`, because a feature branch has
    no business recreating the role its own pipeline assumes.

    Args:
        scope: The scope in which to define this stack.
        id: The scoped construct ID.
        environment: The deployment stage, which also names the GitHub environment the deploy
            role trusts.
        additional_repositories: Other repositories under the same owner allowed to assume the
            deploy role. Each needs its numeric GitHub ID, read with
            `gh api repos/OWNER/NAME --jq .id`.
        max_session_duration: How long an assumed deploy session lasts. Defaults to 2 hours.
        role_name: Name of the deploy role. Defaults to `GITHUB_DEPLOY_ROLE`, then
            `GitHubActionsServiceRole`.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        environment: str,
        additional_repositories: list[GitHubRepositoryReference] | None = None,
        max_session_duration: Duration | None = None,
        role_name: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # ↓↓ Setup GitHub OIDC support ↓↓
        github_actions_oidc = GitHubActionsOidcConstruct(
            self,
            "GitHubActionsOidc",
            environment=environment,
            additional_repositories=additional_repositories,
            max_session_duration=max_session_duration,
            role_name=role_name,
        )

        # ↓↓ Setup CDK Toolkit Cleaner ↓↓
        # Removes CDK asset objects and images that no deployed stack references any more.
        # Without it the staging bucket and ECR repository grow with every deployment.
        ToolkitCleaner(self, "ToolkitCleaner")

        CfnOutput(self, "DeployRole", value=github_actions_oidc.role.role_arn)
