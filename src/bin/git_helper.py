import json
import os
import re
import subprocess
from dataclasses import dataclass, replace

# These subjects land in an IAM StringLike condition, so an unvalidated value is a
# trust-boundary defect rather than a cosmetic one: an id of "*" would widen the policy
# to every repository sharing that name. Constrain each field to what GitHub can actually
# issue, which leaves no room for a wildcard.
NUMERIC_ID_PATTERN = re.compile(r"^[0-9]+$")
REPOSITORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
REMOTE_URL_PATTERN = re.compile(
    r"(?:git@|https://)([\w.@:]+)[/:]([\w.-]+)/([\w.-]+?)(\.git)?$"
)


@dataclass(frozen=True)
class GitHubRepositoryIdentity:
    """Immutable GitHub repository metadata used in an Actions OIDC subject.

    GitHub's immutable subject claim identifies a repository by numeric ID as well as by
    name, so a repository that is renamed, deleted and recreated, or transferred cannot
    silently inherit a trust policy written for the old one.
    """

    owner: str
    """GitHub account or organization that owns the repository, for example `towardsthecloud`."""
    owner_id: str
    """Numeric GitHub ID of the owner, as a decimal string."""
    name: str
    """Repository name, for example `aws-cdk-python-starter-kit`."""
    id: str
    """Numeric GitHub ID of the repository, as a decimal string."""


@dataclass(frozen=True)
class GitHubRepositoryReference:
    """A repository other than the one being synthesized that may assume the deploy role.

    The numeric ID is checked in rather than looked up, because a lookup would force every
    synthesizing CI job to hold a token able to read the other repository. Obtain it with
    `gh api repos/OWNER/NAME --jq .id`.
    """

    name: str
    """Repository name under the same owner, for example `my-cdk-app`."""
    id: str
    """Numeric GitHub ID of the repository, as a decimal string."""


def build_github_actions_oidc_subject(
    repository: GitHubRepositoryIdentity, context: str
) -> str:
    """Build an immutable GitHub Actions OIDC subject for a repository and workflow context.

    Args:
        repository: Immutable identity of the repository to trust.
        context: Subject context after the repository segment, such as `environment:production` or `*`.

    Returns:
        The immutable GitHub Actions OIDC subject claim, for example
        `repo:octo-org@123456/octo-repo@456789:*`.

    Raises:
        ValueError: If any identity field is malformed, or the context carries an unintended wildcard.
    """
    for field in ("owner_id", "id"):
        value = getattr(repository, field)
        if not NUMERIC_ID_PATTERN.match(value):
            raise ValueError(
                f'GitHub repository identity requires a decimal {field}, got "{value}"'
            )

    for field in ("owner", "name"):
        value = getattr(repository, field)
        if not REPOSITORY_NAME_PATTERN.match(value):
            raise ValueError(
                f"GitHub repository identity requires a {field} of letters, digits, '.', '_', or '-', got \"{value}\""
            )

    if context != "*" and re.search(r"[*?]", context):
        raise ValueError(
            f'GitHub Actions OIDC subject context must not contain a wildcard, got "{context}"'
        )

    return f"repo:{repository.owner}@{repository.owner_id}/{repository.name}@{repository.id}:{context}"


def resolve_repository_reference(
    repository: GitHubRepositoryIdentity, reference: GitHubRepositoryReference
) -> GitHubRepositoryIdentity:
    """Apply a reference to another repository under the same owner.

    Args:
        repository: Identity of the repository being synthesized, which supplies the owner.
        reference: Name and numeric ID of the other repository.

    Returns:
        The immutable identity of the referenced repository.
    """
    return replace(repository, name=reference.name, id=reference.id)


def get_git_repository_identity() -> GitHubRepositoryIdentity:
    """Resolve the immutable identity of the repository being synthesized.

    In GitHub Actions this reads the default `GITHUB_REPOSITORY`, `GITHUB_REPOSITORY_ID`, and
    `GITHUB_REPOSITORY_OWNER_ID` variables, so no workflow needs a GitHub token. Locally it reads
    the owner and name from the `origin` remote and fetches the numeric IDs with the GitHub CLI.

    Returns:
        The immutable identity of the current repository.

    Raises:
        ValueError: If the `origin` remote cannot be parsed, or the GitHub CLI cannot resolve the IDs.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "").split("/")
    repository_id = os.environ.get("GITHUB_REPOSITORY_ID")
    owner_id = os.environ.get("GITHUB_REPOSITORY_OWNER_ID")

    if len(repository) == 2 and all(repository) and repository_id and owner_id:
        owner, name = repository
        return GitHubRepositoryIdentity(
            owner=owner, owner_id=owner_id, name=name, id=repository_id
        )

    remote_url = subprocess.check_output(
        ["git", "config", "--get", "remote.origin.url"], text=True
    ).strip()
    match = REMOTE_URL_PATTERN.match(remote_url)

    if match is None:
        raise ValueError("Unable to parse git repository URL")

    owner, name = match.group(2), match.group(3)

    try:
        response = subprocess.check_output(
            [
                "gh",
                "api",
                f"repos/{owner}/{name}",
                "--jq",
                "{owner: .owner.login, ownerId: (.owner.id | tostring), name: .name, id: (.id | tostring)}",
            ],
            text=True,
        )
        payload = json.loads(response)
        return GitHubRepositoryIdentity(
            owner=payload["owner"],
            owner_id=payload["ownerId"],
            name=payload["name"],
            id=payload["id"],
        )
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
    ) as error:
        raise ValueError(
            f"Unable to resolve immutable GitHub identity for {owner}/{name}. "
            'Install the GitHub CLI and authenticate with "gh auth login" or GH_TOKEN.'
        ) from error
