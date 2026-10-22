from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse

import requests

from .render import (
    ARTIFACT_ROOT,
    ArtifactValidationError,
    load_blueprint,
    render_identity,
)


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
OIDC_AUDIENCE = "api://AzureADTokenExchange"
PLAN_SCHEMA_VERSION = "agentid.contoso.bank/plan/v1"
EVIDENCE_SCHEMA_VERSION = "agentid.contoso.bank/evidence/v1"
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40,64}$")
PRINCIPAL_COLLECTIONS = {
    "group": "groups",
    "servicePrincipal": "servicePrincipals",
    "user": "users",
}


class ProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class DesiredState:
    blueprint: dict[str, Any]
    identity: dict[str, Any]

    @property
    def blueprint_name(self) -> str:
        return str(self.blueprint["metadata"]["name"])

    @property
    def identity_name(self) -> str:
        return str(self.identity["metadata"]["name"])

    @property
    def instance_key(self) -> str:
        return str(self.identity["metadata"]["labels"]["instanceKey"])

    @property
    def environment(self) -> str:
        return str(self.identity["spec"]["environment"])


@dataclass(frozen=True)
class PrincipalBinding:
    principal_ref: str
    principal_type: str
    object_id: str
    display_name: str
    group_types: tuple[str, ...] = ()
    is_assignable_to_role: bool = False

    @property
    def odata_url(self) -> str:
        collection = PRINCIPAL_COLLECTIONS[self.principal_type]
        return f"{GRAPH_ROOT}/{collection}/{self.object_id}"

    def as_plan_dict(self) -> dict[str, Any]:
        return {
            "principalType": self.principal_type,
            "objectId": self.object_id,
            "displayName": self.display_name,
        }


class AgentIdGraph(Protocol):
    def get_principal(
        self,
        principal_type: str,
        object_id: str,
    ) -> dict[str, Any]: ...

    def find_blueprints(self, display_name: str) -> list[dict[str, Any]]: ...

    def find_blueprint_principals(
        self,
        app_id: str,
    ) -> list[dict[str, Any]]: ...

    def find_identities(self, display_name: str) -> list[dict[str, Any]]: ...

    def list_blueprint_owner_ids(self, object_id: str) -> list[str]: ...

    def list_blueprint_sponsor_ids(self, object_id: str) -> list[str]: ...

    def list_identity_owner_ids(self, object_id: str) -> list[str]: ...

    def list_identity_sponsor_ids(self, object_id: str) -> list[str]: ...

    def create_blueprint(self, body: dict[str, Any]) -> dict[str, Any]: ...

    def create_blueprint_principal(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]: ...

    def create_identity(self, body: dict[str, Any]) -> dict[str, Any]: ...

    def add_identity_owner(
        self,
        identity_object_id: str,
        owner_object_id: str,
    ) -> None: ...


class MicrosoftGraphApi:
    def __init__(
        self,
        access_token: str,
        session: requests.Session | None = None,
        *,
        allow_writes: bool = False,
    ) -> None:
        if not access_token:
            raise ProvisioningError("Microsoft Graph access token is empty.")
        self._session = session or requests.Session()
        self._allow_writes = allow_writes
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OData-Version": "4.0",
        }

    def get_principal(
        self,
        principal_type: str,
        object_id: str,
    ) -> dict[str, Any]:
        collection = PRINCIPAL_COLLECTIONS[principal_type]
        select = {
            "group": (
                "id,displayName,groupTypes,mailEnabled,securityEnabled,"
                "isAssignableToRole"
            ),
            "servicePrincipal": (
                "id,appId,displayName,servicePrincipalType"
            ),
            "user": "id,displayName,userPrincipalName",
        }[principal_type]
        return self._get(
            f"{collection}/{object_id}",
            params={"$select": select},
        )

    def find_blueprints(self, display_name: str) -> list[dict[str, Any]]:
        return self._collection(
            "applications/microsoft.graph.agentIdentityBlueprint",
            params={
                "$filter": f"displayName eq '{_escape_odata(display_name)}'",
                "$select": (
                    "id,appId,displayName,description,tags,"
                    "requiredResourceAccess"
                ),
            },
        )

    def find_blueprint_principals(
        self,
        app_id: str,
    ) -> list[dict[str, Any]]:
        return self._collection(
            "servicePrincipals/"
            "microsoft.graph.agentIdentityBlueprintPrincipal",
            params={
                "$filter": f"appId eq '{_escape_odata(app_id)}'",
                "$select": "id,appId,displayName,servicePrincipalType,tags",
            },
        )

    def find_identities(self, display_name: str) -> list[dict[str, Any]]:
        return self._collection(
            "servicePrincipals/microsoft.graph.agentIdentity",
            params={
                "$filter": f"displayName eq '{_escape_odata(display_name)}'",
                "$select": (
                    "id,appId,displayName,agentIdentityBlueprintId,tags,"
                    "servicePrincipalType"
                ),
            },
        )

    def list_blueprint_owner_ids(self, object_id: str) -> list[str]:
        return self._relationship_ids(
            "applications/"
            f"{object_id}/microsoft.graph.agentIdentityBlueprint/owners"
        )

    def list_blueprint_sponsor_ids(self, object_id: str) -> list[str]:
        return self._relationship_ids(
            "applications/"
            f"{object_id}/microsoft.graph.agentIdentityBlueprint/sponsors"
        )

    def list_identity_owner_ids(self, object_id: str) -> list[str]:
        return self._relationship_ids(
            "servicePrincipals/"
            f"{object_id}/microsoft.graph.agentIdentity/owners"
        )

    def list_identity_sponsor_ids(self, object_id: str) -> list[str]:
        return self._relationship_ids(
            "servicePrincipals/"
            f"{object_id}/microsoft.graph.agentIdentity/sponsors"
        )

    def create_blueprint(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(
            "applications/microsoft.graph.agentIdentityBlueprint",
            body,
            expected_statuses={201},
        )

    def create_blueprint_principal(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(
            "servicePrincipals/"
            "microsoft.graph.agentIdentityBlueprintPrincipal",
            body,
            expected_statuses={201},
        )

    def create_identity(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(
            "servicePrincipals/microsoft.graph.agentIdentity",
            body,
            expected_statuses={201},
        )

    def add_identity_owner(
        self,
        identity_object_id: str,
        owner_object_id: str,
    ) -> None:
        self._post(
            "servicePrincipals/"
            f"{identity_object_id}/microsoft.graph.agentIdentity/owners/$ref",
            {
                "@odata.id": (
                    f"{GRAPH_ROOT}/directoryObjects/{owner_object_id}"
                )
            },
            expected_statuses={204},
        )

    def _relationship_ids(self, path: str) -> list[str]:
        return sorted(
            str(item["id"])
            for item in self._collection(
                path,
                params={"$select": "id"},
            )
        )

    def _get(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            "GET",
            path,
            params=params,
            expected_statuses={200},
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProvisioningError(
                f"Microsoft Graph returned a non-object for GET {path}."
            )
        return payload

    def _collection(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_path: str | None = path
        next_params = params
        page_count = 0
        while next_path is not None:
            page_count += 1
            if page_count > 100:
                raise ProvisioningError(
                    f"Microsoft Graph pagination exceeded 100 pages for {path}."
                )
            response = self._request(
                "GET",
                next_path,
                params=next_params,
                expected_statuses={200},
            )
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(
                payload.get("value"),
                list,
            ):
                raise ProvisioningError(
                    f"Microsoft Graph returned an invalid collection for {path}."
                )
            for item in payload["value"]:
                if not isinstance(item, dict):
                    raise ProvisioningError(
                        f"Microsoft Graph returned an invalid item for {path}."
                    )
                items.append(item)
            next_link = payload.get("@odata.nextLink")
            if next_link is not None and not isinstance(next_link, str):
                raise ProvisioningError(
                    f"Microsoft Graph returned an invalid next link for {path}."
                )
            next_path = next_link
            next_params = None
        return items

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        expected_statuses: set[int],
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            path,
            json_body=body,
            expected_statuses=expected_statuses,
        )
        if response.status_code == 204:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProvisioningError(
                f"Microsoft Graph returned a non-object for POST {path}."
            )
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        expected_statuses: set[int],
    ) -> requests.Response:
        url = path if path.startswith("https://") else f"{GRAPH_ROOT}/{path}"
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "graph.microsoft.com"
        ):
            raise ProvisioningError(
                "Microsoft Graph request URL must remain on "
                "https://graph.microsoft.com."
            )
        if method != "GET" and not self._allow_writes:
            raise ProvisioningError(
                "This Microsoft Graph client is configured for GET-only "
                "planning."
            )
        try:
            response = self._session.request(
                method,
                url,
                headers=self._headers,
                params=params,
                json=json_body,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ProvisioningError(
                f"Microsoft Graph {method} {parsed.path} failed: {exc}"
            ) from exc
        if response.status_code not in expected_statuses:
            raise ProvisioningError(
                _graph_error_message(method, parsed.path, response)
            )
        return response


def load_desired_state(
    instance_key: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> DesiredState:
    identity = render_identity(instance_key, artifact_root)
    blueprint = load_blueprint(identity["spec"]["blueprintRef"], artifact_root)
    return DesiredState(blueprint=blueprint, identity=identity)


def parse_principal_map(raw_value: str) -> dict[str, dict[str, str]]:
    if not raw_value.strip():
        raise ProvisioningError(
            "AGENT_ID_PRINCIPAL_MAP_JSON must contain a JSON object."
        )
    try:
        document = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ProvisioningError(
            f"AGENT_ID_PRINCIPAL_MAP_JSON is invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(document, dict):
        raise ProvisioningError(
            "AGENT_ID_PRINCIPAL_MAP_JSON must be a JSON object."
        )

    result: dict[str, dict[str, str]] = {}
    for principal_ref, value in document.items():
        if not isinstance(principal_ref, str) or not principal_ref:
            raise ProvisioningError(
                "Principal-map keys must be nonempty strings."
            )
        if not isinstance(value, dict) or set(value) != {
            "principalType",
            "objectId",
        }:
            raise ProvisioningError(
                f"Principal map entry {principal_ref} must contain only "
                "principalType and objectId."
            )
        principal_type = value.get("principalType")
        object_id = value.get("objectId")
        if principal_type not in PRINCIPAL_COLLECTIONS:
            raise ProvisioningError(
                f"Principal map entry {principal_ref} has an unsupported type."
            )
        if not isinstance(object_id, str) or not UUID_PATTERN.fullmatch(
            object_id
        ):
            raise ProvisioningError(
                f"Principal map entry {principal_ref} has an invalid objectId."
            )
        result[principal_ref] = {
            "principalType": principal_type,
            "objectId": object_id.lower(),
        }
    return result


def resolve_principal_bindings(
    api: AgentIdGraph,
    desired: DesiredState,
    principal_map: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, PrincipalBinding], list[str]]:
    references: dict[str, str] = {}
    for document in (desired.blueprint["spec"], desired.identity["spec"]):
        for field_name in ("sponsorRefs", "ownerRefs"):
            for reference in document[field_name]:
                principal_ref = str(reference["principalRef"])
                principal_type = str(reference["principalType"])
                previous_type = references.setdefault(
                    principal_ref,
                    principal_type,
                )
                if previous_type != principal_type:
                    raise ProvisioningError(
                        f"Principal reference {principal_ref} is used with "
                        "multiple types."
                    )

    blockers: list[str] = []
    bindings: dict[str, PrincipalBinding] = {}
    for principal_ref, expected_type in sorted(references.items()):
        mapped = principal_map.get(principal_ref)
        if mapped is None:
            blockers.append(
                f"Principal reference {principal_ref} is not mapped."
            )
            continue
        if mapped.get("principalType") != expected_type:
            blockers.append(
                f"Principal reference {principal_ref} expects "
                f"{expected_type}, not {mapped.get('principalType')}."
            )
            continue
        object_id = str(mapped["objectId"]).lower()
        principal = api.get_principal(expected_type, object_id)
        if str(principal.get("id", "")).lower() != object_id:
            blockers.append(
                f"Principal reference {principal_ref} did not resolve to "
                f"{object_id}."
            )
            continue
        display_name = str(principal.get("displayName") or "").strip()
        if not display_name:
            blockers.append(
                f"Principal reference {principal_ref} has no display name."
            )
            continue
        binding = PrincipalBinding(
            principal_ref=principal_ref,
            principal_type=expected_type,
            object_id=object_id,
            display_name=display_name,
            group_types=tuple(
                sorted(
                    str(value)
                    for value in (principal.get("groupTypes") or [])
                )
            ),
            is_assignable_to_role=bool(
                principal.get("isAssignableToRole", False)
            ),
        )
        if expected_type == "group" and (
            binding.is_assignable_to_role
            or not (
                {"Unified", "DynamicMembership"}
                & set(binding.group_types)
            )
        ):
            blockers.append(
                f"Sponsor group {principal_ref} is not a supported dynamic "
                "membership or Microsoft 365 group."
            )
            continue
        bindings[principal_ref] = binding
    return bindings, blockers


def build_plan(
    api: AgentIdGraph,
    desired: DesiredState,
    bindings: Mapping[str, PrincipalBinding],
    *,
    tenant_id: str,
    source_commit: str,
    binding_blockers: list[str] | None = None,
) -> dict[str, Any]:
    _validate_uuid(tenant_id, "ENTRA_TENANT_ID")
    _validate_source_commit(source_commit)
    observed = _observe(api, desired)
    blockers = list(binding_blockers or [])
    blockers.extend(_desired_state_blockers(desired))
    blockers.extend(_observed_state_blockers(desired, bindings, observed))

    actions = [
        {
            "resourceType": "agentIdentityBlueprint",
            "key": desired.blueprint_name,
            "action": (
                "create" if observed["blueprint"] is None else "verify"
            ),
            "objectId": _object_id(observed["blueprint"]),
        },
        {
            "resourceType": "agentIdentityBlueprintPrincipal",
            "key": desired.blueprint_name,
            "action": (
                "create"
                if observed["blueprintPrincipal"] is None
                else "verify"
            ),
            "objectId": _object_id(observed["blueprintPrincipal"]),
        },
        {
            "resourceType": "agentIdentity",
            "key": desired.identity_name,
            "action": (
                "create" if observed["identity"] is None else "verify"
            ),
            "objectId": _object_id(observed["identity"]),
        },
    ]
    plan: dict[str, Any] = {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "graphApiVersion": "v1.0",
        "tenantId": tenant_id.lower(),
        "sourceCommit": source_commit.lower(),
        "instanceKey": desired.instance_key,
        "environment": desired.environment,
        "desiredDigest": _digest(
            {
                "blueprint": desired.blueprint,
                "identity": desired.identity,
            }
        ),
        "status": "blocked" if blockers else "applicable",
        "blockers": sorted(set(blockers)),
        "actions": actions,
        "principalBindings": {
            key: value.as_plan_dict()
            for key, value in sorted(bindings.items())
        },
        "observed": observed,
        "deferredOperations": [
            "Agent 365 inventory registration",
            "APIM product and runtime binding",
            "blueprint credential creation or rotation",
            "custom security attribute assignment",
            "manager application configuration",
        ],
    }
    plan["planDigest"] = _plan_digest(plan)
    return plan


def apply_plan(
    api: AgentIdGraph,
    desired: DesiredState,
    bindings: Mapping[str, PrincipalBinding],
    approved_plan: Mapping[str, Any],
    *,
    tenant_id: str,
    source_commit: str,
    caller_object_id: str,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    validate_plan_document(approved_plan, require_applicable=True)
    _validate_uuid(caller_object_id, "provisioner token oid")
    if approved_plan["tenantId"] != tenant_id.lower():
        raise ProvisioningError(
            "Approved plan tenant does not match ENTRA_TENANT_ID."
        )
    if approved_plan["sourceCommit"] != source_commit.lower():
        raise ProvisioningError(
            "Approved plan source commit does not match this workflow run."
        )
    if approved_plan["instanceKey"] != desired.instance_key:
        raise ProvisioningError(
            "Approved plan instance does not match the selected instance."
        )

    current_plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=tenant_id,
        source_commit=source_commit,
    )
    if current_plan["planDigest"] != approved_plan["planDigest"]:
        raise ProvisioningError(
            "Tenant or desired state changed after planning; create and "
            "approve a new plan."
        )

    blueprint_owner_ids = _binding_ids(
        desired.blueprint["spec"]["ownerRefs"],
        bindings,
    )
    if caller_object_id.lower() not in blueprint_owner_ids:
        raise ProvisioningError(
            "The applying workload identity must be a declared blueprint "
            "owner so Graph does not introduce an unreviewed owner."
        )

    applied_actions: list[dict[str, str]] = []
    blueprint = current_plan["observed"]["blueprint"]
    if blueprint is None:
        api.create_blueprint(
            {
                "displayName": desired.blueprint["spec"]["displayName"],
                "description": desired.blueprint["spec"]["description"],
                "tags": desired.blueprint["spec"]["tags"],
                "requiredResourceAccess": desired.blueprint["spec"][
                    "permissions"
                ]["requiredResourceAccess"],
                "sponsors@odata.bind": _binding_urls(
                    desired.blueprint["spec"]["sponsorRefs"],
                    bindings,
                ),
                "owners@odata.bind": _binding_urls(
                    desired.blueprint["spec"]["ownerRefs"],
                    bindings,
                ),
            }
        )
        blueprint = _wait_for_one(
            lambda: api.find_blueprints(desired.blueprint["spec"]["displayName"]),
            "agent identity blueprint",
            sleep,
        )
        applied_actions.append(
            {
                "resourceType": "agentIdentityBlueprint",
                "action": "created",
                "objectId": str(blueprint["id"]),
            }
        )

    blueprint_principal = current_plan["observed"]["blueprintPrincipal"]
    if blueprint_principal is None:
        api.create_blueprint_principal({"appId": str(blueprint["appId"])})
        blueprint_principal = _wait_for_one(
            lambda: api.find_blueprint_principals(str(blueprint["appId"])),
            "agent identity blueprint principal",
            sleep,
        )
        applied_actions.append(
            {
                "resourceType": "agentIdentityBlueprintPrincipal",
                "action": "created",
                "objectId": str(blueprint_principal["id"]),
            }
        )

    identity = current_plan["observed"]["identity"]
    if identity is None:
        created_identity = api.create_identity(
            {
                "displayName": desired.identity["spec"]["displayName"],
                "agentIdentityBlueprintId": str(blueprint["appId"]),
                "tags": desired.identity["spec"]["tags"],
                "sponsors@odata.bind": _binding_urls(
                    desired.identity["spec"]["sponsorRefs"],
                    bindings,
                ),
            }
        )
        identity_object_id = str(created_identity.get("id") or "")
        _validate_uuid(identity_object_id, "created Agent Identity object ID")
        for owner_object_id in _binding_ids(
            desired.identity["spec"]["ownerRefs"],
            bindings,
        ):
            api.add_identity_owner(identity_object_id, owner_object_id)
        identity = _wait_for_one(
            lambda: api.find_identities(desired.identity["spec"]["displayName"]),
            "agent identity",
            sleep,
        )
        applied_actions.append(
            {
                "resourceType": "agentIdentity",
                "action": "created",
                "objectId": str(identity["id"]),
            }
        )

    verified_plan = build_plan(
        api,
        desired,
        bindings,
        tenant_id=tenant_id,
        source_commit=source_commit,
    )
    if verified_plan["blockers"]:
        raise ProvisioningError(
            "Post-apply read-back failed: "
            + "; ".join(verified_plan["blockers"])
        )
    if any(
        action["action"] != "verify"
        for action in verified_plan["actions"]
    ):
        raise ProvisioningError(
            "Post-apply read-back did not find every expected object."
        )

    return {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "result": "core-agent-id-provisioned",
        "tenantId": tenant_id.lower(),
        "sourceCommit": source_commit.lower(),
        "instanceKey": desired.instance_key,
        "environment": desired.environment,
        "approvedPlanDigest": approved_plan["planDigest"],
        "desiredDigest": verified_plan["desiredDigest"],
        "objects": verified_plan["observed"],
        "actionsApplied": applied_actions,
        "deferredOperations": verified_plan["deferredOperations"],
    }


def validate_plan_document(
    plan: Mapping[str, Any],
    *,
    require_applicable: bool,
) -> None:
    required = {
        "schemaVersion",
        "tenantId",
        "sourceCommit",
        "instanceKey",
        "status",
        "blockers",
        "planDigest",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise ProvisioningError(
            "Plan is missing required fields: " + ", ".join(missing)
        )
    if plan["schemaVersion"] != PLAN_SCHEMA_VERSION:
        raise ProvisioningError("Plan schema version is not supported.")
    if plan["planDigest"] != _plan_digest(plan):
        raise ProvisioningError("Plan digest does not match its contents.")
    if require_applicable and (
        plan["status"] != "applicable" or plan["blockers"]
    ):
        raise ProvisioningError(
            "Plan is blocked: " + "; ".join(plan["blockers"])
        )


def acquire_graph_token(
    tenant_id: str,
    client_id: str,
    env: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
) -> str:
    _validate_uuid(tenant_id, "ENTRA_TENANT_ID")
    _validate_uuid(client_id, "ENTRA_CLIENT_ID")
    values = os.environ if env is None else env
    request_url = values.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
    request_token = values.get(
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "",
    ).strip()
    if not request_url or not request_token:
        raise ProvisioningError(
            "GitHub OIDC variables are unavailable. Run this operation in "
            "GitHub Actions with id-token: write."
        )
    client = session or requests.Session()
    try:
        oidc_response = client.get(
            request_url,
            headers={"Authorization": f"Bearer {request_token}"},
            params={"audience": OIDC_AUDIENCE},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ProvisioningError(
            f"GitHub OIDC token request failed: {exc}"
        ) from exc
    if oidc_response.status_code != 200:
        raise ProvisioningError(
            "GitHub OIDC token request failed with HTTP "
            f"{oidc_response.status_code}."
        )
    try:
        oidc_payload = oidc_response.json()
    except ValueError as exc:
        raise ProvisioningError(
            "GitHub OIDC response was not valid JSON."
        ) from exc
    oidc_token = (
        oidc_payload.get("value") if isinstance(oidc_payload, dict) else None
    )
    if not isinstance(oidc_token, str) or not oidc_token:
        raise ProvisioningError("GitHub OIDC response did not contain a token.")

    token_url = (
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )
    try:
        token_response = client.post(
            token_url,
            data={
                "client_id": client_id,
                "scope": GRAPH_SCOPE,
                "client_assertion_type": (
                    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                ),
                "client_assertion": oidc_token,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ProvisioningError(
            f"Microsoft Entra token exchange failed: {exc}"
        ) from exc
    if token_response.status_code != 200:
        raise ProvisioningError(
            "Microsoft Entra token exchange failed with HTTP "
            f"{token_response.status_code}."
        )
    try:
        token_payload = token_response.json()
    except ValueError as exc:
        raise ProvisioningError(
            "Microsoft Entra token response was not valid JSON."
        ) from exc
    access_token = (
        token_payload.get("access_token")
        if isinstance(token_payload, dict)
        else None
    )
    if not isinstance(access_token, str) or not access_token:
        raise ProvisioningError(
            "Microsoft Entra token response did not contain an access token."
        )
    return access_token


def token_object_id(access_token: str) -> str:
    parts = access_token.split(".")
    if len(parts) != 3:
        raise ProvisioningError(
            "Microsoft Graph access token is not a JWT."
        )
    try:
        payload_bytes = base64.urlsafe_b64decode(
            parts[1] + "=" * (-len(parts[1]) % 4)
        )
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProvisioningError(
            "Microsoft Graph access token payload is invalid."
        ) from exc
    object_id = payload.get("oid") if isinstance(payload, dict) else None
    if not isinstance(object_id, str):
        raise ProvisioningError(
            "Microsoft Graph access token has no oid claim."
        )
    _validate_uuid(object_id, "Microsoft Graph token oid")
    return object_id.lower()


def write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvisioningError(f"Cannot read JSON document {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ProvisioningError(f"JSON document must be an object: {path}")
    return document


def _observe(
    api: AgentIdGraph,
    desired: DesiredState,
) -> dict[str, dict[str, Any] | None]:
    blueprint = _one_or_none(
        api.find_blueprints(desired.blueprint["spec"]["displayName"]),
        "agent identity blueprint",
    )
    blueprint_principal: dict[str, Any] | None = None
    if blueprint is not None:
        blueprint_principal = _one_or_none(
            api.find_blueprint_principals(str(blueprint["appId"])),
            "agent identity blueprint principal",
        )
        blueprint = {
            "id": str(blueprint["id"]),
            "appId": str(blueprint["appId"]),
            "displayName": str(blueprint["displayName"]),
            "description": str(blueprint.get("description") or ""),
            "tags": sorted(
                str(value) for value in (blueprint.get("tags") or [])
            ),
            "managedTags": _managed_tags(blueprint.get("tags") or []),
            "requiredResourceAccess": blueprint.get(
                "requiredResourceAccess",
                [],
            ),
            "ownerIds": api.list_blueprint_owner_ids(str(blueprint["id"])),
            "sponsorIds": api.list_blueprint_sponsor_ids(
                str(blueprint["id"])
            ),
        }
    if blueprint_principal is not None:
        blueprint_principal = {
            "id": str(blueprint_principal["id"]),
            "appId": str(blueprint_principal["appId"]),
            "displayName": str(
                blueprint_principal.get("displayName") or ""
            ),
            "servicePrincipalType": str(
                blueprint_principal.get("servicePrincipalType") or ""
            ),
        }

    identity = _one_or_none(
        api.find_identities(desired.identity["spec"]["displayName"]),
        "agent identity",
    )
    if identity is not None:
        identity = {
            "id": str(identity["id"]),
            "appId": str(identity.get("appId") or ""),
            "displayName": str(identity["displayName"]),
            "agentIdentityBlueprintId": str(
                identity.get("agentIdentityBlueprintId") or ""
            ),
            "tags": sorted(
                str(value) for value in (identity.get("tags") or [])
            ),
            "managedTags": _managed_tags(identity.get("tags") or []),
            "servicePrincipalType": str(
                identity.get("servicePrincipalType") or ""
            ),
            "ownerIds": api.list_identity_owner_ids(str(identity["id"])),
            "sponsorIds": api.list_identity_sponsor_ids(str(identity["id"])),
        }
    return {
        "blueprint": blueprint,
        "blueprintPrincipal": blueprint_principal,
        "identity": identity,
    }


def _desired_state_blockers(desired: DesiredState) -> list[str]:
    blockers: list[str] = []
    for resource_type, lifecycle in (
        ("Blueprint", desired.blueprint["spec"]["lifecycle"]),
        ("Agent Identity", desired.identity["spec"]["lifecycle"]),
    ):
        if lifecycle["state"] not in {"approved", "provisioned"}:
            blockers.append(
                f"{resource_type} lifecycle state is {lifecycle['state']}."
            )
        if not lifecycle["provisioningEnabled"]:
            blockers.append(
                f"{resource_type} provisioningEnabled is false."
            )
    required_access = desired.blueprint["spec"]["permissions"][
        "requiredResourceAccess"
    ]
    if required_access:
        blockers.append(
            "Blueprint permissions are nonempty, but this adapter does not "
            "apply or consent permissions."
        )
    direct_assignments = desired.identity["spec"]["permissions"][
        "directAssignments"
    ]
    if direct_assignments:
        blockers.append(
            "Agent Identity direct permissions are nonempty, but this "
            "adapter does not apply or consent permissions."
        )
    return blockers


def _observed_state_blockers(
    desired: DesiredState,
    bindings: Mapping[str, PrincipalBinding],
    observed: Mapping[str, dict[str, Any] | None],
) -> list[str]:
    blockers: list[str] = []
    blueprint = observed["blueprint"]
    blueprint_principal = observed["blueprintPrincipal"]
    identity = observed["identity"]

    if blueprint is None:
        if blueprint_principal is not None:
            blockers.append(
                "A BlueprintPrincipal exists without the expected blueprint."
            )
        if identity is not None:
            blockers.append(
                "An Agent Identity exists without the expected blueprint."
            )
    else:
        blueprint_differences = _differences(
            {
                "displayName": desired.blueprint["spec"]["displayName"],
                "description": desired.blueprint["spec"]["description"],
                "managedTags": _managed_tags(
                    desired.blueprint["spec"]["tags"]
                ),
                "requiredResourceAccess": desired.blueprint["spec"][
                    "permissions"
                ]["requiredResourceAccess"],
                "ownerIds": _binding_ids(
                    desired.blueprint["spec"]["ownerRefs"],
                    bindings,
                ),
                "sponsorIds": _binding_ids(
                    desired.blueprint["spec"]["sponsorRefs"],
                    bindings,
                ),
            },
            blueprint,
        )
        blockers.extend(
            f"Blueprint drift: {difference}"
            for difference in blueprint_differences
        )
        if (
            blueprint_principal is not None
            and blueprint_principal["appId"] != blueprint["appId"]
        ):
            blockers.append(
                "BlueprintPrincipal appId does not match the blueprint."
            )

    if identity is not None:
        if blueprint is None:
            expected_blueprint_id = ""
        else:
            expected_blueprint_id = str(blueprint["appId"])
        identity_differences = _differences(
            {
                "displayName": desired.identity["spec"]["displayName"],
                "agentIdentityBlueprintId": expected_blueprint_id,
                "managedTags": _managed_tags(
                    desired.identity["spec"]["tags"]
                ),
                "ownerIds": _binding_ids(
                    desired.identity["spec"]["ownerRefs"],
                    bindings,
                ),
                "sponsorIds": _binding_ids(
                    desired.identity["spec"]["sponsorRefs"],
                    bindings,
                ),
            },
            identity,
        )
        blockers.extend(
            f"Agent Identity drift: {difference}"
            for difference in identity_differences
        )
    return blockers


def _binding_ids(
    references: list[dict[str, str]],
    bindings: Mapping[str, PrincipalBinding],
) -> list[str]:
    return sorted(
        bindings[reference["principalRef"]].object_id
        for reference in references
        if reference["principalRef"] in bindings
    )


def _binding_urls(
    references: list[dict[str, str]],
    bindings: Mapping[str, PrincipalBinding],
) -> list[str]:
    missing = sorted(
        reference["principalRef"]
        for reference in references
        if reference["principalRef"] not in bindings
    )
    if missing:
        raise ProvisioningError(
            "Cannot apply unresolved principal references: "
            + ", ".join(missing)
        )
    return [
        bindings[reference["principalRef"]].odata_url
        for reference in references
    ]


def _managed_tags(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted(
        str(value)
        for value in values
        if isinstance(value, str) and value.startswith("contoso:")
    )


def _differences(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> list[str]:
    return [
        f"{key} expected {_canonical(expected_value)} but found "
        f"{_canonical(actual.get(key))}"
        for key, expected_value in sorted(expected.items())
        if _canonical(expected_value) != _canonical(actual.get(key))
    ]


def _wait_for_one(
    reader: Callable[[], list[dict[str, Any]]],
    resource_name: str,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    delays = (0.0, 2.0, 4.0, 8.0, 16.0)
    for delay in delays:
        if delay:
            sleep(delay)
        items = reader()
        if len(items) == 1:
            return items[0]
        if len(items) > 1:
            raise ProvisioningError(
                f"Multiple {resource_name} objects appeared after creation."
            )
    raise ProvisioningError(
        f"Timed out waiting for {resource_name} directory propagation."
    )


def _one_or_none(
    items: list[dict[str, Any]],
    resource_name: str,
) -> dict[str, Any] | None:
    if len(items) > 1:
        raise ProvisioningError(
            f"Multiple {resource_name} objects match the desired display name."
        )
    return items[0] if items else None


def _plan_digest(plan: Mapping[str, Any]) -> str:
    return _digest(
        {
            key: value
            for key, value in plan.items()
            if key != "planDigest"
        }
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def _object_id(value: dict[str, Any] | None) -> str | None:
    return None if value is None else str(value["id"])


def _validate_uuid(value: str, name: str) -> None:
    if not UUID_PATTERN.fullmatch(value):
        raise ProvisioningError(f"{name} must be a UUID.")


def _validate_source_commit(value: str) -> None:
    if not COMMIT_PATTERN.fullmatch(value):
        raise ProvisioningError(
            "Source commit must be a 40- to 64-character hexadecimal digest."
        )


def _graph_error_message(
    method: str,
    path: str,
    response: requests.Response,
) -> str:
    code = "unknown"
    message = "No Microsoft Graph error message was returned."
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"]
        code = str(error.get("code") or code)
        message = str(error.get("message") or message)
    return (
        f"Microsoft Graph {method} {path} failed with HTTP "
        f"{response.status_code} ({code}): {message[:1000]}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply the Markets Risk Agent Identity desired state."
        )
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ARTIFACT_ROOT,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--instance", required=True)
    plan_parser.add_argument("--source-commit", required=True)
    plan_parser.add_argument("--output", type=Path, required=True)

    check_parser = subparsers.add_parser("check-plan")
    check_parser.add_argument("--plan", type=Path, required=True)
    check_parser.add_argument(
        "--require-applicable",
        action="store_true",
    )

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--instance", required=True)
    apply_parser.add_argument("--source-commit", required=True)
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--evidence", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "check-plan":
            plan = read_json(args.plan)
            validate_plan_document(
                plan,
                require_applicable=args.require_applicable,
            )
            print(
                f"Plan {plan['planDigest']} is "
                f"{plan['status']} for {plan['instanceKey']}."
            )
            return 0

        tenant_id = _required_env("ENTRA_TENANT_ID")
        client_id = _required_env("ENTRA_CLIENT_ID")
        principal_map = parse_principal_map(
            _required_env("AGENT_ID_PRINCIPAL_MAP_JSON")
        )
        desired = load_desired_state(args.instance, args.artifact_root)
        access_token = acquire_graph_token(tenant_id, client_id)
        api = MicrosoftGraphApi(
            access_token,
            allow_writes=args.command == "apply",
        )
        bindings, binding_blockers = resolve_principal_bindings(
            api,
            desired,
            principal_map,
        )

        if args.command == "plan":
            plan = build_plan(
                api,
                desired,
                bindings,
                tenant_id=tenant_id,
                source_commit=args.source_commit,
                binding_blockers=binding_blockers,
            )
            write_json(args.output, plan)
            print(
                f"Wrote {plan['status']} plan {plan['planDigest']} for "
                f"{plan['instanceKey']}."
            )
            for blocker in plan["blockers"]:
                print(f"BLOCKED: {blocker}")
            return 0

        if binding_blockers:
            raise ProvisioningError(
                "Principal resolution is blocked: "
                + "; ".join(binding_blockers)
            )
        approved_plan = read_json(args.plan)
        try:
            evidence = apply_plan(
                api,
                desired,
                bindings,
                approved_plan,
                tenant_id=tenant_id,
                source_commit=args.source_commit,
                caller_object_id=token_object_id(access_token),
            )
        except ProvisioningError as exc:
            write_json(
                args.evidence,
                {
                    "schemaVersion": EVIDENCE_SCHEMA_VERSION,
                    "result": "failed-or-partial",
                    "tenantId": tenant_id.lower(),
                    "sourceCommit": args.source_commit.lower(),
                    "instanceKey": desired.instance_key,
                    "environment": desired.environment,
                    "approvedPlanDigest": approved_plan.get("planDigest"),
                    "error": str(exc)[:1000],
                    "requiredAction": (
                        "Read tenant state before retrying; one or more "
                        "objects might already exist."
                    ),
                },
            )
            raise
        write_json(args.evidence, evidence)
        print(
            "Applied and verified core Agent ID objects for "
            f"{evidence['instanceKey']} using plan "
            f"{evidence['approvedPlanDigest']}."
        )
        return 0
    except (ArtifactValidationError, ProvisioningError) as exc:
        print(f"Agent ID provisioning failed: {exc}", file=sys.stderr)
        return 1


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProvisioningError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
