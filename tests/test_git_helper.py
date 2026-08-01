import json
import subprocess

import pytest

from bin.git_helper import (
    GitHubRepositoryIdentity,
    GitHubRepositoryReference,
    build_github_actions_oidc_subject,
    get_git_repository_identity,
    resolve_repository_reference,
)

REPOSITORY = GitHubRepositoryIdentity(
    owner="octo-org", owner_id="123456", name="octo-repo", id="456789"
)


@pytest.fixture(autouse=True)
def clear_actions_metadata(monkeypatch):
    for variable in (
        "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_ID",
        "GITHUB_REPOSITORY_OWNER_ID",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_identity_uses_actions_metadata_without_invoking_gh(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo-org/octo-repo")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "456789")
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER_ID", "123456")

    def fail(*args, **kwargs):
        raise AssertionError(
            "no subprocess should run when Actions supplies the identity"
        )

    monkeypatch.setattr(subprocess, "check_output", fail)

    assert get_git_repository_identity() == REPOSITORY


def test_identity_resolves_a_normal_git_checkout_through_gh(monkeypatch):
    commands = []

    def fake_check_output(command, **kwargs):
        commands.append(command)
        if command[0] == "git":
            return "git@github.com:octo-org/octo-repo.git\n"
        return json.dumps(
            {
                "owner": "octo-org",
                "ownerId": "123456",
                "name": "octo-repo",
                "id": "456789",
            }
        )

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert get_git_repository_identity() == REPOSITORY
    assert commands[1][:3] == ["gh", "api", "repos/octo-org/octo-repo"]


def test_identity_explains_how_to_authenticate_when_gh_is_missing(monkeypatch):
    def fake_check_output(command, **kwargs):
        if command[0] == "git":
            return "https://github.com/octo-org/octo-repo.git\n"
        raise FileNotFoundError("gh")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    with pytest.raises(ValueError, match="gh auth login"):
        get_git_repository_identity()


def test_subject_renders_the_immutable_repository_claim():
    assert (
        build_github_actions_oidc_subject(REPOSITORY, "environment:production")
        == "repo:octo-org@123456/octo-repo@456789:environment:production"
    )


# The subject lands in an IAM StringLike condition, so a wildcard that slips through
# widens the trust policy rather than merely failing.
@pytest.mark.parametrize("field", ["owner_id", "id"])
@pytest.mark.parametrize("value", ["", "*", "12*", "abc"])
def test_subject_rejects_a_non_decimal_id(field, value):
    repository = GitHubRepositoryIdentity(**{**vars(REPOSITORY), field: value})

    with pytest.raises(ValueError, match=f"requires a decimal {field}"):
        build_github_actions_oidc_subject(repository, "environment:production")


@pytest.mark.parametrize("field", ["owner", "name"])
@pytest.mark.parametrize("value", ["", "*", "octo*", "octo/repo"])
def test_subject_rejects_a_wildcard_name(field, value):
    repository = GitHubRepositoryIdentity(**{**vars(REPOSITORY), field: value})

    with pytest.raises(ValueError, match=f"requires a {field} of letters"):
        build_github_actions_oidc_subject(repository, "environment:production")


def test_subject_rejects_a_wildcard_inside_a_context():
    with pytest.raises(ValueError, match="must not contain a wildcard"):
        build_github_actions_oidc_subject(REPOSITORY, "environment:prod*")

    # The deploy role trusts every context of a trusted repository deliberately.
    assert (
        build_github_actions_oidc_subject(REPOSITORY, "*")
        == "repo:octo-org@123456/octo-repo@456789:*"
    )


def test_reference_keeps_the_owner_and_replaces_the_repository():
    reference = GitHubRepositoryReference(name="octo-site", id="111111")

    assert resolve_repository_reference(
        REPOSITORY, reference
    ) == GitHubRepositoryIdentity(
        owner="octo-org", owner_id="123456", name="octo-site", id="111111"
    )
