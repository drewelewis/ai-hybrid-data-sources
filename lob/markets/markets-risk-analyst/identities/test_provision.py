from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

from identities.provision import (
    EVIDENCE_SCHEMA_VERSION,
    GRAPH_ROOT,
    GRAPH_SCOPE,
    OIDC_AUDIENCE,
    PLAN_SCHEMA_VERSION,
    MicrosoftGraphApi,
    PrincipalBinding,
    ProvisioningError,
    acquire_graph_token,
    apply_plan,
    build_plan,
    load_desired_state,
    parse_principal_map,
    resolve_principal_bindings,
    token_object_id,
    validate_plan_document,
)
from identities.render import ARTIFACT_ROOT


TENANT_ID = "10000000-0000-4000-8000-000000000001"
SPONSOR_ID = "20000000-0000-4000-8000-000000000002"
OWNER_ID = "30000000-0000-4000-8000-000000000003"
BLUEPRINT_OBJECT_ID = "40000000-0000-4000-8000-000000000004"
BLUEPRINT_APP_ID = "50000000-0000-4000-8000-000000000005"
PRINCIPAL_OBJECT_ID = "60000000-0000-4000-8000-000000000006"
IDENTITY_OBJECT_ID = "70000000-0000-4000-8000-000000000007"
IDENTITY_APP_ID = "80000000-0000-4000-8000-000000000008"
SOURCE_COMMIT = "a" * 40


class FakeGraphApi:
    def __init__(self) -> None:
        self.principals = {
            ("group", SPONSOR_ID): {
                "id": SPONSOR_ID,
                "displayName": "Markets Risk Business Sponsors",
                "groupTypes": ["Unified"],
                "isAssignableToRole": False,
            },
            ("servicePrincipal", OWNER_ID): {
                "id": OWNER_ID,
                "appId": "90000000-0000-4000-8000-000000000009",
                "displayName": "Markets Agent ID Nonproduction Provisioner",
                "servicePrincipalType": "Application",
            },
        }
        self.blueprints: list[dict[str, Any]] = []
        self.blueprint_principals: list[dict[str, Any]] = []
        self.identities: list[dict[str, Any]] = []
        self.blueprint_owners: dict[str, list[str]] = {}
        self.blueprint_sponsors: dict[str, list[str]] = {}
        self.identity_owners: dict[str, list[str]] = {}
        self.identity_sponsors: dict[str, list[str]] = {}
        self.calls: list[str] = []

    def get_principal(
        self,
        principal_type: str,
        object_id: str,
    ) -> dict[str, Any]:
        return self.principals[(principal_type, object_id)]

    def find_blueprints(self, display_name: str) -> list[dict[str, Any]]:
        return [
            value
            for value in self.blueprints
            if value["displayName"] == display_name
        ]

    def find_blueprint_principals(
        self,
        app_id: str,
    ) -> list[dict[str, Any]]:
        return [
            value
            for value in self.blueprint_principals
            if value["appId"] == app_id
        ]

    def find_identities(self, display_name: str) -> list[dict[str, Any]]:
        return [
            value
            for value in self.identities
            if value["displayName"] == display_name
        ]

    def list_blueprint_owner_ids(self, object_id: str) -> list[str]:
        return sorted(self.blueprint_owners[object_id])

    def list_blueprint_sponsor_ids(self, object_id: str) -> list[str]:
        return sorted(self.blueprint_sponsors[object_id])

    def list_identity_owner_ids(self, object_id: str) -> list[str]:
        return sorted(self.identity_owners[object_id])

    def list_identity_sponsor_ids(self, object_id: str) -> list[str]:
        return sorted(self.identity_sponsors[object_id])

    def create_blueprint(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("create-blueprint")
        document = {
            "id": BLUEPRINT_OBJECT_ID,
            "appId": BLUEPRINT_APP_ID,
            "displayName": body["displayName"],
            "description": body["description"],
            "tags": body["tags"],
            "requiredResourceAccess": body["requiredResourceAccess"],
        }
        self.blueprints.append(document)
        self.blueprint_owners[BLUEPRINT_OBJECT_ID] = _ids_from_urls(
            body["owners@odata.bind"]
        )
        self.blueprint_sponsors[BLUEPRINT_OBJECT_ID] = _ids_from_urls(
            body["sponsors@odata.bind"]
        )
        return document

    def create_blueprint_principal(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append("create-blueprint-principal")
        document = {
            "id": PRINCIPAL_OBJECT_ID,
            "appId": body["appId"],
            "displayName": "Markets Risk Analyst Nonproduction",
            "servicePrincipalType": "Application",
            "tags": [],
        }
        self.blueprint_principals.append(document)
        return document

    def create_identity(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("create-identity")
        document = {
            "id": IDENTITY_OBJECT_ID,
            "appId": IDENTITY_APP_ID,
            "displayName": body["displayName"],
            "agentIdentityBlueprintId": body["agentIdentityBlueprintId"],
            "tags": body["tags"],
            "servicePrincipalType": "ServiceIdentity",
        }
        self.identities.append(document)
        self.identity_owners[IDENTITY_OBJECT_ID] = []
        self.identity_sponsors[IDENTITY_OBJECT_ID] = _ids_from_urls(
            body["sponsors@odata.bind"]
        )
        return document

    def add_identity_owner(
        self,
        identity_object_id: str,
        owner_object_id: str,
    ) -> None:
        self.calls.append("add-identity-owner")
        self.identity_owners[identity_object_id].append(owner_object_id)


def test_current_desired_state_produces_blocked_plan() -> None:
    api = FakeGraphApi()
    desired = load_desired_state("dev")
    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )

    plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )

    assert plan["schemaVersion"] == PLAN_SCHEMA_VERSION
    assert plan["status"] == "blocked"
    assert "Blueprint lifecycle state is proposed." in plan["blockers"]
    assert "Agent Identity provisioningEnabled is false." in plan["blockers"]
    assert [action["action"] for action in plan["actions"]] == [
        "create",
        "create",
        "create",
    ]


def test_ready_plan_is_deterministic(tmp_path: Path) -> None:
    artifact_root = _ready_artifact_root(tmp_path)
    api = FakeGraphApi()
    desired = load_desired_state("dev", artifact_root)
    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )

    first = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )
    second = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )

    assert first == second
    assert first["status"] == "applicable"
    validate_plan_document(first, require_applicable=True)


def test_apply_creates_objects_in_dependency_order(tmp_path: Path) -> None:
    artifact_root = _ready_artifact_root(tmp_path)
    api = FakeGraphApi()
    desired = load_desired_state("dev", artifact_root)
    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )
    plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )

    evidence = apply_plan(
        api,
        desired,
        bindings,
        plan,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        caller_object_id=OWNER_ID,
        sleep=lambda _: None,
    )

    assert api.calls == [
        "create-blueprint",
        "create-blueprint-principal",
        "create-identity",
        "add-identity-owner",
    ]
    assert evidence["schemaVersion"] == EVIDENCE_SCHEMA_VERSION
    assert evidence["result"] == "core-agent-id-provisioned"
    assert evidence["objects"]["blueprint"]["id"] == BLUEPRINT_OBJECT_ID
    assert evidence["objects"]["blueprintPrincipal"]["id"] == (
        PRINCIPAL_OBJECT_ID
    )
    assert evidence["objects"]["identity"]["id"] == IDENTITY_OBJECT_ID
    assert evidence["deferredOperations"]


def test_apply_rejects_tenant_change_after_plan(tmp_path: Path) -> None:
    artifact_root = _ready_artifact_root(tmp_path)
    api = FakeGraphApi()
    desired = load_desired_state("dev", artifact_root)
    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )
    plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )
    api.create_blueprint(
        {
            "displayName": desired.blueprint["spec"]["displayName"],
            "description": desired.blueprint["spec"]["description"],
            "tags": desired.blueprint["spec"]["tags"],
            "requiredResourceAccess": [],
            "owners@odata.bind": [f"https://graph.microsoft.com/v1.0/servicePrincipals/{OWNER_ID}"],
            "sponsors@odata.bind": [f"https://graph.microsoft.com/v1.0/groups/{SPONSOR_ID}"],
        }
    )

    with pytest.raises(
        ProvisioningError,
        match="changed after planning",
    ):
        apply_plan(
            api,
            desired,
            bindings,
            plan,
            tenant_id=TENANT_ID,
            source_commit=SOURCE_COMMIT,
            caller_object_id=OWNER_ID,
            sleep=lambda _: None,
        )


def test_assigned_security_group_cannot_be_sponsor(
    tmp_path: Path,
) -> None:
    artifact_root = _ready_artifact_root(tmp_path)
    api = FakeGraphApi()
    api.principals[("group", SPONSOR_ID)]["groupTypes"] = []
    api.principals[("group", SPONSOR_ID)]["securityEnabled"] = True
    desired = load_desired_state("dev", artifact_root)

    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )

    assert "markets-risk-analyst-business-sponsors" not in bindings
    assert blockers == [
        "Sponsor group markets-risk-analyst-business-sponsors is not a "
        "supported dynamic membership or Microsoft 365 group."
    ]


def test_plan_digest_detects_tampering(tmp_path: Path) -> None:
    artifact_root = _ready_artifact_root(tmp_path)
    api = FakeGraphApi()
    desired = load_desired_state("dev", artifact_root)
    bindings, blockers = resolve_principal_bindings(
        api,
        desired,
        _principal_map(),
    )
    plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=TENANT_ID,
        source_commit=SOURCE_COMMIT,
        binding_blockers=blockers,
    )
    plan["instanceKey"] = "tst"

    with pytest.raises(ProvisioningError, match="digest"):
        validate_plan_document(plan, require_applicable=True)


def test_principal_map_rejects_unexpected_fields() -> None:
    with pytest.raises(ProvisioningError, match="contain only"):
        parse_principal_map(
            json.dumps(
                {
                    "principal": {
                        "principalType": "user",
                        "objectId": SPONSOR_ID,
                        "displayName": "Untrusted override",
                    }
                }
            )
        )


def test_token_object_id_reads_oid_claim() -> None:
    payload = base64.urlsafe_b64encode(
        json.dumps({"oid": OWNER_ID}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    token = f"header.{payload}.signature"

    assert token_object_id(token) == OWNER_ID


def test_github_oidc_is_exchanged_for_app_only_graph_token() -> None:
    session = TokenSession()

    token = acquire_graph_token(
        TENANT_ID,
        OWNER_ID,
        env={
            "ACTIONS_ID_TOKEN_REQUEST_URL": (
                "https://token.actions.githubusercontent.test/oidc"
            ),
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "synthetic-runner-token",
        },
        session=session,
    )

    assert token == "synthetic-graph-token"
    assert session.oidc_audience == OIDC_AUDIENCE
    assert session.token_request == {
        "client_id": OWNER_ID,
        "scope": GRAPH_SCOPE,
        "client_assertion_type": (
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        ),
        "client_assertion": "synthetic-github-oidc-token",
        "grant_type": "client_credentials",
    }


def test_graph_client_uses_typed_v1_endpoints() -> None:
    session = RecordingSession()
    api = MicrosoftGraphApi(
        "synthetic-graph-token",
        session=session,
        allow_writes=True,
    )

    api.create_blueprint({"displayName": "Blueprint"})
    api.create_blueprint_principal({"appId": BLUEPRINT_APP_ID})
    api.create_identity({"displayName": "Identity"})
    api.add_identity_owner(IDENTITY_OBJECT_ID, OWNER_ID)

    assert [
        (call["method"], call["url"], call["status"])
        for call in session.calls
    ] == [
        (
            "POST",
            f"{GRAPH_ROOT}/applications/"
            "microsoft.graph.agentIdentityBlueprint",
            201,
        ),
        (
            "POST",
            f"{GRAPH_ROOT}/servicePrincipals/"
            "microsoft.graph.agentIdentityBlueprintPrincipal",
            201,
        ),
        (
            "POST",
            f"{GRAPH_ROOT}/servicePrincipals/"
            "microsoft.graph.agentIdentity",
            201,
        ),
        (
            "POST",
            f"{GRAPH_ROOT}/servicePrincipals/{IDENTITY_OBJECT_ID}/"
            "microsoft.graph.agentIdentity/owners/$ref",
            204,
        ),
    ]
    assert all(
        call["headers"]["OData-Version"] == "4.0"
        for call in session.calls
    )


def test_planner_graph_client_rejects_writes() -> None:
    api = MicrosoftGraphApi(
        "synthetic-graph-token",
        session=RecordingSession(),
    )

    with pytest.raises(ProvisioningError, match="GET-only"):
        api.create_blueprint({"displayName": "Blocked"})


def _ready_artifact_root(tmp_path: Path) -> Path:
    target = tmp_path / "identities"
    shutil.copytree(
        ARTIFACT_ROOT,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "rendered"),
    )
    base_path = target / "identity.base.yaml"
    base = _load_yaml(base_path)
    base["spec"]["customSecurityAttributes"]["RiskTier"] = "Tier2"
    _write_yaml(base_path, base)

    blueprint_path = target / "blueprints" / "nonprod.yaml"
    blueprint = _load_yaml(blueprint_path)
    blueprint["spec"]["lifecycle"] = {
        "state": "approved",
        "provisioningEnabled": True,
    }
    _write_yaml(blueprint_path, blueprint)

    instance_path = target / "instances" / "dev.yaml"
    instance = _load_yaml(instance_path)
    instance["lifecycle"] = {
        "state": "approved",
        "provisioningEnabled": True,
    }
    _write_yaml(instance_path, instance)
    return target


def _principal_map() -> dict[str, dict[str, str]]:
    return {
        "markets-risk-analyst-business-sponsors": {
            "principalType": "group",
            "objectId": SPONSOR_ID,
        },
        "markets-agent-identity-nonprod-provisioner": {
            "principalType": "servicePrincipal",
            "objectId": OWNER_ID,
        },
    }


def _ids_from_urls(urls: list[str]) -> list[str]:
    return [url.rsplit("/", 1)[-1] for url in urls]


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


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class TokenSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.oidc_audience = ""
        self.token_request: dict[str, str] = {}

    def get(
        self,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        assert url == "https://token.actions.githubusercontent.test/oidc"
        assert kwargs["headers"] == {
            "Authorization": "Bearer synthetic-runner-token"
        }
        self.oidc_audience = kwargs["params"]["audience"]
        return FakeResponse(
            200,
            {"value": "synthetic-github-oidc-token"},
        )

    def post(
        self,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        assert url == (
            f"https://login.microsoftonline.com/{TENANT_ID}/"
            "oauth2/v2.0/token"
        )
        self.token_request = kwargs["data"]
        return FakeResponse(
            200,
            {"access_token": "synthetic-graph-token"},
        )


class RecordingSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, Any]] = []
        self._statuses = [201, 201, 201, 204]

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        status = self._statuses.pop(0)
        self.calls.append(
            {
                "method": method,
                "url": url,
                "status": status,
                "headers": kwargs["headers"],
            }
        )
        return FakeResponse(
            status,
            {
                "id": IDENTITY_OBJECT_ID,
                "appId": BLUEPRINT_APP_ID,
            },
        )
