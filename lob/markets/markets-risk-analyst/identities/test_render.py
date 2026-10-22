from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from identities.render import (
    ARTIFACT_ROOT,
    ArtifactValidationError,
    discover_instance_keys,
    dump_identity,
    render_all,
    render_identity,
    load_blueprint,
    write_rendered,
)

DEFAULT_INSTANCE_KEYS = ("local", "dev", "tst", "prd")


def test_render_all_produces_unique_instance_identities() -> None:
    identities = render_all()

    assert discover_instance_keys() == DEFAULT_INSTANCE_KEYS
    assert tuple(identities) == DEFAULT_INSTANCE_KEYS
    assert {
        identity["metadata"]["name"] for identity in identities.values()
    } == {
        f"markets-risk-analyst-{instance_key}"
        for instance_key in DEFAULT_INSTANCE_KEYS
    }
    assert identities["prd"]["spec"]["blueprintRef"] == "markets-risk-analyst-prd"
    for instance_key in ("local", "dev", "tst"):
        assert (
            identities[instance_key]["spec"]["blueprintRef"]
            == "markets-risk-analyst-nonprod"
        )
    for instance_key, identity in identities.items():
        assert identity["metadata"]["labels"]["instanceKey"] == instance_key
        assert identity["spec"]["deployment"]["instance"] == instance_key
    assert all(
        not identity["spec"]["lifecycle"]["provisioningEnabled"]
        for identity in identities.values()
    )


def test_instance_lifecycle_is_independent(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    dev_path = artifact_root / "instances" / "dev.yaml"
    dev = _load_yaml(dev_path)
    dev["lifecycle"]["state"] = "approved"
    _write_yaml(dev_path, dev)

    identities = render_all(artifact_root)

    assert identities["dev"]["spec"]["lifecycle"] == {
        "state": "approved",
        "provisioningEnabled": False,
    }
    for instance_key in ("local", "tst", "prd"):
        assert identities[instance_key]["spec"]["lifecycle"]["state"] == "proposed"


def test_regional_instance_and_sponsor_override_are_supported(
    tmp_path: Path,
) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    source_path = artifact_root / "instances" / "prd.yaml"
    regional = _load_yaml(source_path)
    regional["instanceKey"] = "prd-emea"
    regional["displayName"] = "Markets Risk Analyst Production EMEA"
    regional["sponsorRefs"] = [
        {
            "principalType": "group",
            "principalRef": "markets-risk-analyst-emea-business-sponsors",
        }
    ]
    regional["deployment"] = {
        "region": "emea",
        "legalEntity": "contoso-bank-europe",
    }
    _write_yaml(artifact_root / "instances" / "prd-emea.yaml", regional)

    identity = render_identity("prd-emea", artifact_root)

    assert identity["metadata"]["name"] == "markets-risk-analyst-prd-emea"
    assert identity["metadata"]["labels"]["environment"] == "prd"
    assert identity["metadata"]["labels"]["instanceKey"] == "prd-emea"
    assert identity["spec"]["deployment"]["instance"] == "prd-emea"
    assert identity["spec"]["apim"]["productRef"] == "markets-risk-analyst-prd-emea"
    assert identity["spec"]["sponsorRefs"] == regional["sponsorRefs"]
    assert tuple(render_all(artifact_root)) == (
        "local",
        "dev",
        "tst",
        "prd",
        "prd-emea",
    )


def test_rendering_is_deterministic() -> None:
    first = {name: dump_identity(value) for name, value in render_all().items()}
    second = {name: dump_identity(value) for name, value in render_all().items()}

    assert first == second


def test_blueprint_and_identity_owners_are_graph_supported() -> None:
    identities = render_all()

    for blueprint_name in (
        "markets-risk-analyst-nonprod",
        "markets-risk-analyst-prd",
    ):
        blueprint = load_blueprint(blueprint_name)
        assert {
            reference["principalType"]
            for reference in blueprint["spec"]["ownerRefs"]
        } <= {"servicePrincipal", "user"}

    for identity in identities.values():
        assert {
            reference["principalType"]
            for reference in identity["spec"]["ownerRefs"]
        } <= {"servicePrincipal", "user"}


def test_write_rendered_creates_only_instance_outputs(tmp_path: Path) -> None:
    output_directory = tmp_path / "rendered"

    write_rendered(render_all(), output_directory)

    assert sorted(path.name for path in output_directory.iterdir()) == [
        "dev.yaml",
        "local.yaml",
        "prd.yaml",
        "tst.yaml",
    ]
    for instance_key in DEFAULT_INSTANCE_KEYS:
        document = yaml.safe_load(
            (output_directory / f"{instance_key}.yaml").read_text(encoding="utf-8")
        )
        assert document["metadata"]["labels"]["instanceKey"] == instance_key


def test_write_rendered_rejects_stale_output(tmp_path: Path) -> None:
    output_directory = tmp_path / "rendered"
    output_directory.mkdir()
    (output_directory / "prd-emea.yaml").write_text(
        "stale: true\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ArtifactValidationError,
        match="stale or unexpected entries: prd-emea.yaml",
    ):
        write_rendered(render_all(), output_directory)


def test_production_cannot_reference_nonproduction_blueprint(
    tmp_path: Path,
) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    overlay_path = artifact_root / "instances" / "prd.yaml"
    overlay = _load_yaml(overlay_path)
    overlay["blueprintRef"] = "markets-risk-analyst-nonprod"
    _write_yaml(overlay_path, overlay)

    with pytest.raises(
        ArtifactValidationError,
        match="prd must reference blueprint markets-risk-analyst-prd",
    ):
        render_identity("prd", artifact_root)


def test_enabled_identity_requires_ready_blueprint(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    overlay_path = artifact_root / "instances" / "dev.yaml"
    overlay = _load_yaml(overlay_path)
    overlay["lifecycle"] = {
        "state": "approved",
        "provisioningEnabled": True,
    }
    _write_yaml(overlay_path, overlay)

    with pytest.raises(
        ArtifactValidationError,
        match=(
            "dev cannot enable provisioning while blueprint "
            "markets-risk-analyst-nonprod is not approved and "
            "provisioning-enabled"
        ),
    ):
        render_identity("dev", artifact_root)


def test_enabled_production_rejects_unresolved_governance(
    tmp_path: Path,
) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    overlay_path = artifact_root / "instances" / "prd.yaml"
    overlay = _load_yaml(overlay_path)
    overlay["lifecycle"] = {
        "state": "approved",
        "provisioningEnabled": True,
    }
    _write_yaml(overlay_path, overlay)
    _approve_blueprint(artifact_root / "blueprints" / "prd.yaml")

    with pytest.raises(
        ArtifactValidationError,
        match="prd has unresolved governance values",
    ):
        render_identity("prd", artifact_root)


def test_blueprint_schema_rejects_unknown_fields(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    blueprint_path = artifact_root / "blueprints" / "prd.yaml"
    blueprint = _load_yaml(blueprint_path)
    blueprint["metadata"]["tenantObjectId"] = "not-desired-state"
    _write_yaml(blueprint_path, blueprint)

    with pytest.raises(
        ArtifactValidationError,
        match="prd blueprint failed schema validation",
    ):
        render_identity("prd", artifact_root)


def test_production_blueprint_rejects_client_secrets(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    blueprint_path = artifact_root / "blueprints" / "prd.yaml"
    blueprint = _load_yaml(blueprint_path)
    credential_policy = blueprint["spec"]["credentialPolicy"]
    credential_policy["allowedTypes"].append("clientSecret")
    credential_policy["clientSecret"] = {
        "allowed": True,
        "allowedEnvironments": ["prd"],
        "maximumLifetimeDays": 30,
    }
    _write_yaml(blueprint_path, blueprint)

    with pytest.raises(
        ArtifactValidationError,
        match="Production blueprint markets-risk-analyst-prd cannot allow client secrets",
    ):
        render_identity("prd", artifact_root)


def test_blueprint_rejects_group_owner(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    blueprint_path = artifact_root / "blueprints" / "nonprod.yaml"
    blueprint = _load_yaml(blueprint_path)
    blueprint["spec"]["ownerRefs"] = [
        {
            "principalType": "group",
            "principalRef": "unsupported-owner-group",
        }
    ]
    _write_yaml(blueprint_path, blueprint)

    with pytest.raises(
        ArtifactValidationError,
        match="owners must be users or service principals",
    ):
        render_identity("local", artifact_root)


def test_identity_rejects_service_principal_sponsor(tmp_path: Path) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    overlay_path = artifact_root / "instances" / "dev.yaml"
    overlay = _load_yaml(overlay_path)
    overlay["sponsorRefs"] = [
        {
            "principalType": "servicePrincipal",
            "principalRef": "unsupported-sponsor-service",
        }
    ]
    _write_yaml(overlay_path, overlay)

    with pytest.raises(
        ArtifactValidationError,
        match="sponsors must be users or supported groups",
    ):
        render_identity("dev", artifact_root)


def test_invalid_schema_is_reported_as_artifact_validation_error(
    tmp_path: Path,
) -> None:
    artifact_root = _copy_artifacts(tmp_path)
    schema_path = artifact_root / "schemas" / "instance-overlay.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["type"] = "not-a-json-schema-type"
    schema_path.write_text(
        json.dumps(schema, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ArtifactValidationError,
        match="Invalid JSON schema",
    ):
        render_identity("local", artifact_root)


def _load_yaml(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _write_yaml(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def _approve_blueprint(path: Path) -> None:
    blueprint = _load_yaml(path)
    blueprint["spec"]["lifecycle"] = {
        "state": "approved",
        "provisioningEnabled": True,
    }
    _write_yaml(path, blueprint)


def _copy_artifacts(tmp_path: Path) -> Path:
    target = tmp_path / "identities"
    shutil.copytree(
        ARTIFACT_ROOT,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "rendered"),
    )
    return target
