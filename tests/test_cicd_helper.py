import os
import re
import subprocess

import pytest
from projen.awscdk import AwsCdkPythonApp

from src.bin.cicd_helper import (
    cdk_validate_workflow,
    docker_asset_cache_steps,
    github_cicd,
)


@pytest.fixture
def project(tmp_path):
    return AwsCdkPythonApp(
        name="fixture",
        module_name="src",
        version="0.0.0",
        cdk_version="2.267.0",
        author_email="test@example.com",
        author_name="Test",
        outdir=str(tmp_path),
    )


def workflow_yaml(workflow, tmp_path):
    # get_job deserializes wait-only steps as the older required run/uses union.
    # Inspect the emitted public workflow contract instead.
    workflow.file.synthesize()
    return (tmp_path / workflow.file.path).read_text()


def test_offline_validation_isolates_environments_and_waits_for_checks(
    project, tmp_path
):
    workflow = cdk_validate_workflow(
        project.github, "3.13", "2.1139.0", ["dev", "test"]
    )
    output = workflow_yaml(workflow, tmp_path)
    checks = [
        block for block in output.split("      - name:") if "background: true" in block
    ]
    assert [re.findall(r"run: (.+)", block)[0] for block in checks] == [
        'uv run projen dev:validate --no-online --output "${{ runner.temp }}/cdk-assemblies/dev"',
        'uv run projen test:validate --no-online --output "${{ runner.temp }}/cdk-assemblies/test"',
        "uv run projen test",
    ]
    ids = [re.findall(r"id: (.+)", block)[0] for block in checks]
    assert len(set(ids)) == 3
    barrier = output.split("        wait:")[-1]
    assert re.findall(r"          - (.+)", barrier) == ids
    assert "continue-on-error: true" not in output


def test_deploy_waits_for_authentication_after_installing_dependencies(
    project, tmp_path
):
    github_cicd(project.github, "123456789012", "dev", "3.13", "us-east-1", "2.1139.0")
    workflow = project.github.try_find_workflow("cdk-deploy-dev")
    output = workflow_yaml(workflow, tmp_path)
    auth = next(
        block
        for block in output.split("      - name:")
        if "Configure AWS credentials" in block
    )
    assert "background: true" in auth
    assert output.index("Configure AWS credentials") < output.index(
        "Install dependencies"
    )
    assert output.index("Install dependencies") < output.index(
        "Wait for AWS authentication"
    )
    assert output.index("Wait for AWS authentication") < output.index(
        "Validate CDK for the DEV"
    )
    assert "          - configure_aws_credentials" in output


def test_root_docker_context_changes_primary_cache_key(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "--quiet")
    (tmp_path / "docker").mkdir()
    restore, _ = docker_asset_cache_steps()
    epoch = next(
        step["run"] for step in restore if step.get("id") == "docker_cache_epoch"
    )
    primary = next(
        step["with"]["key"] for step in restore if step.get("id") == "docker_cache"
    )
    keys = []
    for content in ["FROM scratch\n", "FROM scratch\nLABEL changed=true\n"]:
        (tmp_path / "docker/Dockerfile").write_text(content)
        git("add", "docker/Dockerfile")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        )
        output = tmp_path / "outputs"
        output.write_text("")
        subprocess.run(
            ["bash", "-e", "-c", epoch],
            cwd=tmp_path,
            env={**os.environ, "GITHUB_OUTPUT": str(output)},
            check=True,
        )
        key = primary
        for line in output.read_text().splitlines():
            name, value = line.split("=", 1)
            key = key.replace(
                "${{ steps.docker_cache_epoch.outputs." + name + " }}", value
            )
        keys.append(key)
    assert keys[0] != keys[1]
