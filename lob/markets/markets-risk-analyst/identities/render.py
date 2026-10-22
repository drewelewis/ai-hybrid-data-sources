from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ARTIFACT_ROOT = Path(__file__).resolve().parent
INSTANCE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENVIRONMENT_ORDER = {"local": 0, "dev": 1, "tst": 2, "prd": 3}


class ArtifactValidationError(ValueError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ArtifactValidationError(f"Cannot read YAML artifact {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError(f"YAML artifact must be an object: {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Cannot read JSON schema {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError(f"JSON schema must be an object: {path}")
    return data


def _validate_schema(
    document: dict[str, Any],
    schema_path: Path,
    artifact_name: str,
) -> None:
    schema = _load_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ArtifactValidationError(
            f"Invalid JSON schema {schema_path}: {exc.message}"
        ) from exc
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ArtifactValidationError(f"{artifact_name} failed schema validation: {details}")


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def discover_instance_keys(
    artifact_root: Path = ARTIFACT_ROOT,
) -> tuple[str, ...]:
    instance_directory = artifact_root / "instances"
    try:
        paths = tuple(instance_directory.glob("*.yaml"))
    except OSError as exc:
        raise ArtifactValidationError(
            f"Cannot discover instance overlays in {instance_directory}: {exc}"
        ) from exc
    if not paths:
        raise ArtifactValidationError("No instance overlays were found")

    instance_keys = tuple(
        path.stem
        for path in sorted(
            paths,
            key=lambda path: (
                ENVIRONMENT_ORDER.get(path.stem.split("-", 1)[0], 99),
                path.stem,
            ),
        )
    )
    invalid_keys = tuple(
        key for key in instance_keys if INSTANCE_KEY_PATTERN.fullmatch(key) is None
    )
    if invalid_keys:
        raise ArtifactValidationError(
            f"Invalid instance overlay file name(s): {', '.join(invalid_keys)}"
        )
    return instance_keys


def _validate_blueprint_policy(blueprint: dict[str, Any]) -> None:
    metadata = blueprint["metadata"]
    spec = blueprint["spec"]
    name = metadata["name"]
    family = metadata["labels"]["applicationFamily"]
    trust_boundary = metadata["labels"]["trustBoundary"]
    environments = set(spec["environments"])
    credential_policy = spec["credentialPolicy"]
    client_secret = credential_policy["clientSecret"]
    allowed_types = set(credential_policy["allowedTypes"])
    client_secret_environments = set(client_secret["allowedEnvironments"])

    _validate_administrative_refs(
        name,
        spec["sponsorRefs"],
        spec["ownerRefs"],
    )

    if trust_boundary == "production":
        expected_name = f"{family}-prd"
        if name != expected_name:
            raise ArtifactValidationError(
                f"Production blueprint name must be {expected_name}"
            )
        if environments != {"prd"}:
            raise ArtifactValidationError(
                f"Production blueprint {name} must allow only prd"
            )
        if client_secret["allowed"] or "clientSecret" in allowed_types:
            raise ArtifactValidationError(
                f"Production blueprint {name} cannot allow client secrets"
            )
        if not spec["governance"].get(
            "independentProductionApprovalRequired", False
        ):
            raise ArtifactValidationError(
                f"Production blueprint {name} requires independent approval"
            )
    else:
        expected_name = f"{family}-nonprod"
        if name != expected_name:
            raise ArtifactValidationError(
                f"Nonproduction blueprint name must be {expected_name}"
            )
        if environments != {"local", "dev", "tst"}:
            raise ArtifactValidationError(
                f"Nonproduction blueprint {name} must allow local, dev, and tst"
            )

    if client_secret["allowed"] != ("clientSecret" in allowed_types):
        raise ArtifactValidationError(
            f"Blueprint {name} has inconsistent client-secret policy"
        )
    if not client_secret_environments.issubset(environments):
        raise ArtifactValidationError(
            f"Blueprint {name} allows client secrets outside its environments"
        )


def _load_blueprints(artifact_root: Path) -> dict[str, dict[str, Any]]:
    blueprints: dict[str, dict[str, Any]] = {}
    schema_path = (
        artifact_root / "schemas" / "agent-identity-blueprint.schema.json"
    )
    for path in sorted((artifact_root / "blueprints").glob("*.yaml")):
        blueprint = _load_yaml(path)
        _validate_schema(blueprint, schema_path, f"{path.stem} blueprint")
        _validate_blueprint_policy(blueprint)
        name = blueprint["metadata"]["name"]
        if name in blueprints:
            raise ArtifactValidationError(f"Duplicate blueprint name: {name}")
        blueprints[name] = blueprint
    if not blueprints:
        raise ArtifactValidationError("No blueprint artifacts were found")
    return blueprints


def _validate_policy(
    identity: dict[str, Any],
    blueprints: dict[str, dict[str, Any]],
) -> None:
    metadata = identity["metadata"]
    spec = identity["spec"]
    environment = spec["environment"]
    instance_key = metadata["labels"]["instanceKey"]
    family = metadata["labels"]["applicationFamily"]
    expected_name = f"{family}-{instance_key}"
    expected_blueprint = f"{family}-prd" if environment == "prd" else f"{family}-nonprod"

    _validate_administrative_refs(
        metadata["name"],
        spec["sponsorRefs"],
        spec["ownerRefs"],
    )

    if instance_key != environment and not instance_key.startswith(
        f"{environment}-"
    ):
        raise ArtifactValidationError(
            f"Instance key {instance_key} must be {environment} or start with "
            f"{environment}-"
        )
    if metadata["name"] != expected_name:
        raise ArtifactValidationError(
            f"{instance_key} identity name must be {expected_name}"
        )
    if spec["blueprintRef"] != expected_blueprint:
        raise ArtifactValidationError(
            f"{instance_key} must reference blueprint {expected_blueprint}"
        )
    blueprint = blueprints.get(spec["blueprintRef"])
    if blueprint is None:
        raise ArtifactValidationError(
            f"Unknown blueprint reference: {spec['blueprintRef']}"
        )
    if environment not in blueprint["spec"].get("environments", []):
        raise ArtifactValidationError(
            f"Blueprint {spec['blueprintRef']} does not allow {environment}"
        )
    if spec["apim"]["productRef"] != expected_name:
        raise ArtifactValidationError(
            f"{instance_key} APIM product must be {expected_name}"
        )

    if spec["lifecycle"]["provisioningEnabled"]:
        blueprint_lifecycle = blueprint["spec"]["lifecycle"]
        if (
            not blueprint_lifecycle["provisioningEnabled"]
            or blueprint_lifecycle["state"] not in {"approved", "provisioned"}
        ):
            raise ArtifactValidationError(
                f"{instance_key} cannot enable provisioning while blueprint "
                f"{spec['blueprintRef']} is not approved and provisioning-enabled"
            )
        unresolved_values = {
            spec["customSecurityAttributes"]["RiskTier"],
            spec["deployment"]["region"],
            spec["deployment"]["legalEntity"],
        }
        if any(
            isinstance(value, str)
            and (value.startswith("pending-") or value == "PendingReview")
            for value in unresolved_values
        ):
            raise ArtifactValidationError(
                f"{instance_key} has unresolved governance values"
            )


def _validate_administrative_refs(
    artifact_name: str,
    sponsor_refs: list[dict[str, str]],
    owner_refs: list[dict[str, str]],
) -> None:
    unsupported_sponsors = sorted(
        reference["principalRef"]
        for reference in sponsor_refs
        if reference["principalType"] not in {"group", "user"}
    )
    if unsupported_sponsors:
        raise ArtifactValidationError(
            f"{artifact_name} sponsors must be users or supported groups: "
            + ", ".join(unsupported_sponsors)
        )

    unsupported_owners = sorted(
        reference["principalRef"]
        for reference in owner_refs
        if reference["principalType"] not in {"servicePrincipal", "user"}
    )
    if unsupported_owners:
        raise ArtifactValidationError(
            f"{artifact_name} owners must be users or service principals: "
            + ", ".join(unsupported_owners)
        )


def render_identity(
    instance_key: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, Any]:
    if INSTANCE_KEY_PATTERN.fullmatch(instance_key) is None:
        raise ArtifactValidationError(f"Invalid instance key: {instance_key}")

    base = _load_yaml(artifact_root / "identity.base.yaml")
    overlay = _load_yaml(artifact_root / "instances" / f"{instance_key}.yaml")
    _validate_schema(
        overlay,
        artifact_root / "schemas" / "instance-overlay.schema.json",
        f"{instance_key} overlay",
    )
    if overlay["instanceKey"] != instance_key:
        raise ArtifactValidationError(
            f"Overlay instance key {overlay['instanceKey']} does not match "
            f"{instance_key}"
        )

    identity = copy.deepcopy(base)
    environment = overlay["environment"]
    family = identity["metadata"]["labels"]["applicationFamily"]
    identity["metadata"]["name"] = f"{family}-{instance_key}"
    identity["metadata"]["labels"]["environment"] = environment
    identity["metadata"]["labels"]["instanceKey"] = instance_key

    spec_overlay = {
        "displayName": overlay["displayName"],
        "blueprintRef": overlay["blueprintRef"],
        "ownerRefs": overlay["ownerRefs"],
        "deployment": overlay["deployment"],
        "lifecycle": overlay["lifecycle"],
    }
    if "sponsorRefs" in overlay:
        spec_overlay["sponsorRefs"] = overlay["sponsorRefs"]
    identity["spec"] = _deep_merge(identity["spec"], spec_overlay)
    identity["spec"]["environment"] = environment
    identity["spec"]["deployment"]["instance"] = instance_key
    identity["spec"]["tags"].append(f"contoso:environment={environment}")
    identity["spec"]["tags"].append(f"contoso:instance={instance_key}")
    identity["spec"]["customSecurityAttributes"]["Environment"] = environment
    identity["spec"]["apim"] = {"productRef": f"{family}-{instance_key}"}

    _validate_schema(
        identity,
        artifact_root / "schemas" / "agent-identity.schema.json",
        f"{instance_key} Agent Identity",
    )
    _validate_policy(identity, _load_blueprints(artifact_root))
    return identity


def load_blueprint(
    blueprint_name: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, Any]:
    blueprints = _load_blueprints(artifact_root)
    try:
        return copy.deepcopy(blueprints[blueprint_name])
    except KeyError as exc:
        raise ArtifactValidationError(
            f"Unknown blueprint: {blueprint_name}"
        ) from exc


def render_all(
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, dict[str, Any]]:
    identities = {
        instance_key: render_identity(instance_key, artifact_root)
        for instance_key in discover_instance_keys(artifact_root)
    }
    names = [identity["metadata"]["name"] for identity in identities.values()]
    if len(names) != len(set(names)):
        raise ArtifactValidationError("Instance overlays produced duplicate names")
    return identities


def dump_identity(identity: dict[str, Any]) -> str:
    return yaml.safe_dump(
        identity,
        allow_unicode=False,
        sort_keys=False,
        width=80,
    )


def write_rendered(
    identities: dict[str, dict[str, Any]],
    output_directory: Path,
) -> None:
    invalid_keys = tuple(
        instance_key
        for instance_key in identities
        if INSTANCE_KEY_PATTERN.fullmatch(instance_key) is None
    )
    if invalid_keys:
        raise ArtifactValidationError(
            f"Cannot write invalid instance key(s): {', '.join(invalid_keys)}"
        )
    expected_files = {f"{instance_key}.yaml" for instance_key in identities}
    rendered_documents = {
        f"{instance_key}.yaml": dump_identity(identity)
        for instance_key, identity in identities.items()
    }
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        unexpected_files = sorted(
            path.name
            for path in output_directory.iterdir()
            if path.name not in expected_files
        )
        if unexpected_files:
            raise ArtifactValidationError(
                "Output directory contains stale or unexpected entries: "
                + ", ".join(unexpected_files)
            )
        for file_name, document in rendered_documents.items():
            (output_directory / file_name).write_text(
                document,
                encoding="utf-8",
                newline="\n",
            )
    except ArtifactValidationError:
        raise
    except OSError as exc:
        raise ArtifactValidationError(
            f"Cannot write rendered identities to {output_directory}: {exc}"
        ) from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and validate Markets Risk Agent Identity artifacts."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--instance", metavar="INSTANCE_KEY")
    selection.add_argument("--environment", help=argparse.SUPPRESS)
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--output-directory", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.all:
            identities = render_all()
        else:
            instance_key = args.instance or args.environment
            if instance_key is None:
                raise ArtifactValidationError("No instance key was selected")
            identities = {instance_key: render_identity(instance_key)}
        if args.output_directory is not None:
            write_rendered(identities, args.output_directory)
        else:
            rendered = [dump_identity(identities[name]).rstrip() for name in identities]
            print("\n---\n".join(rendered))
    except ArtifactValidationError as exc:
        print(f"Identity artifact validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
