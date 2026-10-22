# Markets Risk Analyst Agent ID Desired State

## Purpose

This folder contains Contoso Bank's reviewable desired-state artifacts for the
Markets Risk Analyst Agent Identity family. The artifacts translate approved
business and governance intent into inputs for a future controlled
provisioning pipeline.

They are **not** raw Microsoft Graph request bodies, generated tenant exports,
or evidence that a blueprint, Agent Identity, Agent 365 registration, APIM
product, permission, or credential exists.

All included artifacts have `provisioningEnabled: false`.

## Layout

```text
identities/
|-- blueprints/
|   |-- nonprod.yaml
|   `-- prd.yaml
|-- instances/
|   |-- local.yaml
|   |-- dev.yaml
|   |-- tst.yaml
|   `-- prd.yaml
|-- schemas/
|   |-- agent-identity-blueprint.schema.json
|   |-- agent-identity.schema.json
|   `-- instance-overlay.schema.json
|-- identity.base.yaml
|-- provision.py
|-- render.py
|-- requirements.txt
|-- test_provision.py
|-- test_render.py
`-- README.md
```

| Artifact | Intended trust boundary |
|---|---|
| [Nonproduction blueprint](./blueprints/nonprod.yaml) | Shared family boundary for `local`, `dev`, and `tst` while their credentials, inherited permissions, ownership, and kill-switch remain compatible |
| [Production blueprint](./blueprints/prd.yaml) | Separate production credential, permission, ownership, and kill-switch boundary |
| [Identity base](./identity.base.yaml) | Common hosting, default sponsor, tags, security attributes, empty direct-permission baseline, and registration intent |
| [Local instance](./instances/local.yaml) | Primary on-premises `local` instance and its independent lifecycle |
| [Development instance](./instances/dev.yaml) | Shared on-premises `dev` instance and its independent lifecycle |
| [Test instance](./instances/tst.yaml) | Independently controlled on-premises `tst` instance and lifecycle |
| [Production instance](./instances/prd.yaml) | Initial on-premises `prd` instance; region and legal entity remain unapproved |
| [Blueprint schema](./schemas/agent-identity-blueprint.schema.json) | Closed schema for credential, permission, ownership, governance, and lifecycle boundaries |
| [Rendered identity schema](./schemas/agent-identity.schema.json) | Closed schema for the deterministic Agent Identity output |
| [Instance schema](./schemas/instance-overlay.schema.json) | Closed schema for independently promoted instance inputs |

Additional production regions or legal entities require additional identity
instance overlays, such as `prd-emea.yaml` with
`instanceKey: prd-emea`. The renderer then derives
`markets-risk-analyst-prd-emea`. An instance can override `sponsorRefs` when
the accountable sponsor differs. A new blueprint is also required when the
instance cannot safely share the production credential, inherited
permissions, publisher, ownership, or family-wide kill-switch.

## Internal schema

`apiVersion: agentid.contoso.bank/v1alpha1` identifies an internal
desired-state contract. It is not a Microsoft API version.

The checked-in source is a typed base plus independently promoted instance
overlays. `environment` remains the stage policy attribute, while
`instanceKey` is the unique deployment key and may include an approved
regional or legal-entity suffix. The [renderer](./render.py) discovers the
instance overlays and derives the identity name, instance and environment
labels, deployment instance, APIM product reference, and tags. It validates
both blueprints and rendered identities against closed JSON Schemas and then
applies cross-artifact policy. This is a structured merge, not unvalidated
text replacement.

An identity can enable provisioning only when:

- its own lifecycle is `approved` or `provisioned`;
- its referenced blueprint is `approved` or `provisioned` and has
  provisioning enabled;
- the blueprint permits its environment; and
- required governance values are no longer pending.

Lifecycle state belongs to each instance overlay, so approving `dev` cannot
implicitly approve `local`, `tst`, or `prd`.

The provisioning layer is responsible for:

1. Resolving each `principalRef` to an approved tenant object ID.
2. Resolving `blueprintRef` to the provisioned blueprint application ID.
3. Converting the desired fields into currently supported Microsoft Graph
   calls after verifying the API version and request shape.
4. Keeping permission declaration separate from administrator consent.
5. Creating the Agent 365 registration when
   `agent365Registration.desired` is `true`.
6. Reading the resulting objects back independently and recording sanitized
   IDs and evidence.

The checked-in [Markets Risk Agent ID workflow](../../../../.github/workflows/markets-risk-agent-id.yml)
and [Graph adapter](./provision.py) implement the first controlled slice of
that layer. They create or verify the selected blueprint,
BlueprintPrincipal, and Agent Identity through Microsoft Graph v1.0. Agent
365 inventory registration, APIM/runtime binding, blueprint credentials,
custom security attributes, and manager-application configuration remain
separate deferred operations and are listed in every plan and evidence
artifact.

The [Agent 365 DevOps and GitOps guide](../../../../A365/devops.md) defines the
required plan/apply, approval, tool-selection, evidence, drift, and promotion
controls for that provisioning layer.

The contracts are based on the Microsoft Graph
[`agentIdentityBlueprint`](https://learn.microsoft.com/en-us/graph/api/resources/agentidentityblueprint?view=graph-rest-1.0)
and
[`agentIdentity`](https://learn.microsoft.com/en-us/graph/api/resources/agentidentity?view=graph-rest-1.0)
resource types.

| Desired-state field | Microsoft surface |
|---|---|
| `metadata.name` and `spec.displayName` | Blueprint or Agent Identity display name and stable bank key |
| `sponsorRefs` and `ownerRefs` | Graph sponsor and owner relationships |
| `permissions.requiredResourceAccess` | Blueprint permission declaration, subject to separate review and consent |
| `tags` | Blueprint or Agent Identity tags |
| `customSecurityAttributes` | Agent Identity custom security attributes |
| `blueprintRef` | Resolved to `agentIdentityBlueprintId` during provisioning |
| `managerApplications.mode` | Requires supported Agent 365 platform handling; arbitrary application IDs are prohibited |
| `agent365Registration` | Separate Agent 365 inventory operation, not implicit in Agent Identity creation |

Server-generated values such as object IDs, application IDs,
`createdByAppId`, and `servicePrincipalType` do not belong in the desired
specification. A sanitized provisioning result can record non-secret IDs in
the approved evidence store.

## Render and validate

Install only the desired-state tooling dependencies:

```powershell
py -m pip install -r .\requirements.txt
```

Render all discovered instances to standard output without writing files:

```powershell
py .\render.py --all
```

Render one instance:

```powershell
py .\render.py --instance dev
```

Write all rendered plans to the ignored `rendered/` folder:

```powershell
py .\render.py --all --output-directory .\rendered
```

Run the renderer tests from the Markets Risk Analyst folder:

```powershell
py -m pytest .\identities\test_render.py .\identities\test_provision.py -q
```

Rendered plans are review and pipeline artifacts. Do not commit them or treat
them as observed tenant state. The output directory must contain only the
expected files for the current render. The renderer rejects unexpected or
stale entries rather than leaving an obsolete identity plan behind.

## GitHub Actions rollout

The [Markets Risk Agent ID rollout workflow](../../../../.github/workflows/markets-risk-agent-id.yml)
supports:

- pull-request schema, policy, renderer, provisioner, and deterministic-output
  validation without a tenant token;
- manual tenant-aware `plan` for `local`, `dev`, `tst`, or `prd`;
- manual `apply` from `main` after an applicable plan, explicit
  `APPLY <instance>` confirmation, and protected-environment approval;
- GitHub OIDC token exchange without a stored client secret;
- create-or-verify behavior with no update, delete, permission-consent, or
  credential operation;
- stale-plan and duplicate-name rejection; and
- sanitized plan and read-back evidence artifacts, including a
  `failed-or-partial` warning that requires tenant inspection before retry
  when apply stops after mutation might have begun.

The workflow uses these GitHub environments:

| Environment | Purpose | Workload permission posture |
|---|---|---|
| `markets-risk-agent-id-plan` | Read current tenant state and resolve approved principals | Main-only environment with required reviewers; separate planner application; adapter enforces GET-only Graph requests |
| `markets-risk-agent-id-nonprod` | Apply `local`, `dev`, or `tst` core Agent ID objects | Nonproduction provisioner; required reviewers |
| `markets-risk-agent-id-prd` | Apply `prd` core Agent ID objects | Separate production provisioner; stricter required reviewers |

Configure these non-secret environment variables:

| Variable | Purpose |
|---|---|
| `ENTRA_TENANT_ID` | Explicit target tenant UUID |
| `ENTRA_CLIENT_ID` | Planner or provisioner application client UUID for the environment |
| `AGENT_ID_PRINCIPAL_MAP_JSON` | Symbolic desired-state references mapped to reviewed tenant object UUIDs and types |

Example principal map with placeholders:

```json
{
  "markets-risk-analyst-business-sponsors": {
    "principalType": "group",
    "objectId": "00000000-0000-4000-8000-000000000001"
  },
  "markets-agent-identity-nonprod-provisioner": {
    "principalType": "servicePrincipal",
    "objectId": "00000000-0000-4000-8000-000000000002"
  }
}
```

The production environment maps
`markets-agent-identity-production-provisioner` instead of the nonproduction
reference. Sponsor groups must be dynamic-membership or Microsoft 365 groups;
assigned security groups and role-assignable groups are rejected. Agent ID
owners must be users or service principals because Microsoft Graph does not
support groups as owners.

The planner application needs:

- `AgentIdentityBlueprint.Read.All`;
- `AgentIdentityBlueprintPrincipal.Read.All`;
- `AgentIdentity.ReadWrite.All`;
- `Application.Read.All`;
- `Group.Read.All`; and
- `User.Read.All`.

Microsoft Graph v1.0 currently requires `AgentIdentity.ReadWrite.All` even to
list an Agent Identity's sponsors. This is a platform permission limitation,
not permission for the workflow to mutate. The plan command constructs its
Graph client in GET-only mode and rejects every POST request. Keep the planner
application separate from both provisioners and alert on any Graph write
attributed to it.

The provisioner application needs:

- `AgentIdentityBlueprint.ReadWrite.All`;
- `AgentIdentityBlueprintPrincipal.ReadWrite.All`;
- `AgentIdentity.ReadWrite.All`;
- `Application.Read.All`;
- `Group.Read.All`; and
- `User.Read.All`.

An identity administrator must create and consent those applications outside
the application workflow. Each application uses a federated credential for
the exact GitHub environment subject and audience
`api://AzureADTokenExchange`. Do not add a client secret.

Restrict all three GitHub environments to the protected `main` branch and
require named reviewers. This is mandatory for the planner as well as apply:
a workflow selected from an untrusted branch must never receive its
write-capable Graph token. The in-workflow `main` checks are defense in depth,
not a replacement for GitHub environment deployment-branch policies.

The current repository artifacts intentionally cannot apply. Both blueprints
and all instances remain `proposed` with `provisioningEnabled: false`, and
the risk tier and production geography remain unresolved. A reviewed pull
request must resolve those values and approve only the selected blueprint and
instance before `apply` can reach its protected-environment gate.

## Security rules

- Never add client-secret values, private keys, certificates with private key
  material, access tokens, APIM subscription keys, or generated Agent 365
  configuration.
- Keep credential material in the approved HSM or secret-management service.
- A credential policy describes allowed mechanisms; it does not contain a
  credential.
- `requiredResourceAccess` stays empty until each permission has a business
  justification, owner, review date, and revocation plan.
- Production does not permit client-secret authentication.
- Placeholder principal references and the pending production region and
  legal entity must be replaced through an approved pull request before a
  provisioning plan can pass.
- Production overlays must reference the production blueprint, while
  `local`, `dev`, and `tst` must reference the nonproduction blueprint.
- Sponsors must resolve to users or supported groups. Owners must resolve to
  users or service principals.
- The provisioner that creates a blueprint must be one of its declared
  service-principal owners so Microsoft Graph does not introduce an
  unreviewed owner.
- Every blueprint and instance overlay has a closed schema.
- The renderer rejects unknown fields, invalid schema definitions, prohibited
  production client secrets, enabled identities whose blueprints are not
  ready, and enabled provisioning when governance values remain pending.
- Application authors cannot approve their own production identity,
  permissions, consent, data access, or release.

## Lifecycle

An artifact progresses through:

```text
proposed -> approved -> provisioned -> retired
```

Each instance owns its lifecycle. Changing `lifecycle.state` or
`provisioningEnabled` does not itself authorize provisioning. Blueprint
readiness is necessary but is not sufficient authorization. The future
pipeline must also require the applicable IAM, security, LOB, model-risk,
privacy, compliance, and regional approvals from the
[LOB rollout strategy](../../../../A365/lob_rollout_strategy.md).

Before execution:

1. Validate the artifact schema and naming.
2. Reject unresolved placeholders and prohibited credential fields.
3. Compare desired state with Microsoft Entra and Agent 365 observed state.
4. Produce a non-mutating plan.
5. Obtain the required approvals.
6. Execute through the approved Microsoft Graph or Agent 365 provisioning
   identity.
7. Verify owners, sponsors, permissions, attributes, registration, and APIM
   attribution independently.
