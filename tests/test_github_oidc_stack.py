import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template

from bin.git_helper import GitHubRepositoryReference
from stacks.github_oidc_stack import GitHubOIDCStack


@pytest.fixture(autouse=True)
def pinned_repository(monkeypatch):
    """Pin the repository identity so the trust policy is asserted against known values.

    Without this the assertions would depend on whichever checkout the tests run in, and
    every test would shell out to git and the GitHub CLI.
    """
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo-org/octo-repo")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "456789")
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER_ID", "123456")
    monkeypatch.delenv("GITHUB_DEPLOY_ROLE", raising=False)


def test_stack_trusts_the_immutable_subject_of_its_own_repository():
    template = Template.from_stack(GitHubOIDCStack(App(), "oidc-test"))

    # The account's GitHub OIDC provider is imported, not managed by this stack.
    template.resource_count_is("Custom::AWSCDKOpenIdConnectProvider", 0)
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "GitHubDeployRole",
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
                                    "token.actions.githubusercontent.com:sub": [
                                        "repo:octo-org@123456/octo-repo@456789:*"
                                    ]
                                },
                            },
                        }
                    )
                ]
            },
        },
    )


def test_stack_trusts_additional_repositories_by_name_and_numeric_id():
    stack = GitHubOIDCStack(
        App(),
        "oidc-test",
        additional_repositories=[
            GitHubRepositoryReference(name="octo-site", id="111111"),
            GitHubRepositoryReference(name="octo-app", id="222222"),
        ],
    )

    Template.from_stack(stack).has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Condition": {
                                "StringLike": {
                                    "token.actions.githubusercontent.com:sub": [
                                        "repo:octo-org@123456/octo-repo@456789:*",
                                        "repo:octo-org@123456/octo-site@111111:*",
                                        "repo:octo-org@123456/octo-app@222222:*",
                                    ]
                                }
                            }
                        }
                    )
                ]
            }
        },
    )


def test_stack_can_narrow_the_subject_to_a_github_environment():
    stack = GitHubOIDCStack(
        App(), "oidc-test", subject_context="environment:production"
    )

    Template.from_stack(stack).has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Condition": {
                                "StringLike": {
                                    "token.actions.githubusercontent.com:sub": [
                                        "repo:octo-org@123456/octo-repo@456789:environment:production"
                                    ]
                                }
                            }
                        }
                    )
                ]
            }
        },
    )


# A malformed ID would otherwise reach an IAM StringLike condition and widen the trust policy.
def test_stack_rejects_an_additional_repository_without_a_numeric_id():
    with pytest.raises(ValueError, match="requires a decimal id"):
        GitHubOIDCStack(
            App(),
            "oidc-test",
            additional_repositories=[
                GitHubRepositoryReference(name="octo-site", id="*")
            ],
        )
