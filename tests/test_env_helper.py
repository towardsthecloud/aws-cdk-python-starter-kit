import pytest

from bin.env_helper import (
    create_env_resource_name,
    extract_cleaned_branch_name,
    get_task_name,
)


@pytest.fixture(autouse=True)
def clear_deployment_environment(monkeypatch):
    for variable in ("GIT_BRANCH_REF", "ENVIRONMENT"):
        monkeypatch.delenv(variable, raising=False)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "test:synth"),
        ({"task_type": "all"}, "test:deploy:all"),
        ({"is_branch": True}, "test:branch:deploy"),
        ({"is_branch": True, "task_type": "stack"}, "test:branch:deploy:stack"),
    ],
)
def test_get_task_name_builds_the_expected_variants(kwargs, expected):
    action = "synth" if expected.endswith("synth") else "deploy"
    assert get_task_name("test", action, **kwargs) == expected


def test_get_task_name_ignores_the_task_type_for_whole_app_actions():
    """`synth` and `ls` always cover every stack, so an :all/:stack split would be meaningless."""
    assert get_task_name("test", "synth", task_type="all") == "test:synth"
    assert get_task_name("test", "ls", task_type="stack") == "test:ls"


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("feature/add-api", "add-api"),
        ("refs/heads/FIX-Bug_42", "fix-bug42"),
        ("trailing-hyphen---", "trailing-hyphen"),
        ("a" * 40, "a" * 25),
    ],
)
def test_extract_cleaned_branch_name_normalises_a_ref(ref, expected):
    assert extract_cleaned_branch_name(ref) == expected


# These refs own the shared environment stacks or are releases, so they must not get their own.
@pytest.mark.parametrize(
    "ref", [None, "", "main", "develop", "development", "v1.2.3", "release/v10.0.1"]
)
def test_extract_cleaned_branch_name_rejects_refs_without_their_own_stacks(ref):
    assert extract_cleaned_branch_name(ref) is None


def test_create_env_resource_name_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert create_env_resource_name("StarterStack") == "StarterStack-production"


def test_create_env_resource_name_uses_the_branch_when_deploying_one(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("GIT_BRANCH_REF", "feature/add-api")

    assert create_env_resource_name("StarterStack") == "StarterStack-add-api"


def test_create_env_resource_name_falls_back_when_the_branch_owns_no_stacks(
    monkeypatch,
):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("GIT_BRANCH_REF", "release/v1.2.3")

    assert create_env_resource_name("StarterStack") == "StarterStack-test"


# A branch deployment from main would overwrite the shared environment stacks.
def test_create_env_resource_name_rejects_a_branch_deployment_from_main(monkeypatch):
    monkeypatch.setenv("GIT_BRANCH_REF", "main")

    with pytest.raises(ValueError, match='GIT_BRANCH_REF cannot be "main"'):
        create_env_resource_name("StarterStack")


def test_create_env_resource_name_truncates_without_a_trailing_separator(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    name = create_env_resource_name("A" * 62)

    assert len(name) <= 64
    assert name[-1].isalnum()
