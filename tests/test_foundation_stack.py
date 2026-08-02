import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template

from bin.git_helper import GitHubRepositoryReference
from stacks.foundation_stack import FoundationStack

GITHUB_SUB = "token.actions.githubusercontent.com:sub"


@pytest.fixture(autouse=True)
def pinned_repository(monkeypatch):
    """Pin the repository identity so the trust policy is asserted against known values.

    Without this the assertions would depend on whichever checkout the tests run in, and every
    test would shell out to git and the GitHub CLI.
    """
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo-org/octo-repo")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "456789")
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER_ID", "123456")
    monkeypatch.delenv("GITHUB_DEPLOY_ROLE", raising=False)


def assume_role_condition(template: Template) -> dict:
    """Read the trust policy condition off the single deploy role in the template."""
    roles = [
        role
        for role in template.find_resources("AWS::IAM::Role").values()
        if role["Properties"].get("RoleName") == "GitHubActionsServiceRole"
    ]
    assert len(roles) == 1
    return roles[0]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0][
        "Condition"
    ]


def test_stack_trusts_the_immutable_subject_of_its_own_repository():
    template = Template.from_stack(
        FoundationStack(App(), "foundation-test", environment="production")
    )

    # The account's GitHub OIDC provider is imported, not managed by this stack.
    template.resource_count_is("Custom::AWSCDKOpenIdConnectProvider", 0)
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "GitHubActionsServiceRole",
            "MaxSessionDuration": 7200,
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                                },
                                "StringLike": {
                                    GITHUB_SUB: [
                                        "repo:octo-org@123456/octo-repo@456789:environment:production"
                                    ]
                                },
                            },
                        }
                    )
                ]
            },
        },
    )


def test_stack_scopes_the_trust_to_the_given_github_environment():
    template = Template.from_stack(
        FoundationStack(App(), "foundation-test", environment="test")
    )

    assert assume_role_condition(template)["StringLike"][GITHUB_SUB] == [
        "repo:octo-org@123456/octo-repo@456789:environment:test"
    ]


def test_stack_trusts_additional_repositories_by_name_and_numeric_id():
    stack = FoundationStack(
        App(),
        "foundation-test",
        environment="production",
        additional_repositories=[
            GitHubRepositoryReference(name="octo-site", id="111111"),
            GitHubRepositoryReference(name="octo-app", id="222222"),
        ],
    )

    assert assume_role_condition(Template.from_stack(stack))["StringLike"][
        GITHUB_SUB
    ] == [
        "repo:octo-org@123456/octo-repo@456789:environment:production",
        "repo:octo-org@123456/octo-site@111111:environment:production",
        "repo:octo-org@123456/octo-app@222222:environment:production",
    ]


# A malformed ID would otherwise reach an IAM StringLike condition and widen the trust policy.
def test_stack_rejects_an_additional_repository_without_a_numeric_id():
    with pytest.raises(ValueError, match="requires a decimal id"):
        FoundationStack(
            App(),
            "foundation-test",
            environment="production",
            additional_repositories=[
                GitHubRepositoryReference(name="octo-site", id="*")
            ],
        )


def test_stack_includes_the_toolkit_cleaner():
    """The cleaner is what stops the CDK staging bucket growing with every deployment."""
    template = Template.from_stack(
        FoundationStack(App(), "foundation-test", environment="production")
    )

    template.resource_count_is("AWS::Scheduler::Schedule", 1)
