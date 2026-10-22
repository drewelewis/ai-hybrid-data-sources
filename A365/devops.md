# Agent 365 DevOps and GitOps Guide

## Purpose

This guide defines how Contoso Bank should validate, approve, provision,
promote, verify, operate, and retire Agent 365 applications at enterprise
scale.

It applies to the on-premises agents in this repository and to future LOB
agents that use:

- Microsoft Entra Agent ID for blueprint and instance identities;
- Agent 365 for inventory, governance, and observability;
- APIM as the only approved model gateway; and
- `local` -> `dev` -> `tst` -> `prd` promotion.

This is an operating model, not an executable pipeline. It does not authorize
tenant changes. Follow the [provisioning runbook](./provisioning_runbook.md)
for an approved execution and the
[verification process](./verification_process.md) for acceptance evidence.

## Outcomes

The DevOps process must:

1. Keep non-secret desired state reviewable in Git.
2. Preserve a separate real Agent Identity for every governed deployment
   instance.
3. Create blueprints before their dependent identities.
4. Separate validation, provisioning, consent, runtime, and audit authority.
5. Produce a non-mutating plan before every tenant mutation.
6. Promote immutable application artifacts rather than copying developer
   workspaces or `.env` files.
7. Read every changed object back from its authoritative service.
8. Detect drift without silently deleting or weakening controls.
9. Retain sanitized evidence without storing credentials or sensitive agent
   content.

## Non-goals

This guide does not:

- make Agent 365 CLI a generic YAML importer;
- treat application deployment as permission to create tenant identities;
- allow application authors to approve their own production release;
- put secrets, tokens, private keys, or generated Agent 365 configuration in
  Git;
- make a successful command exit code sufficient acceptance evidence; or
- imply that proposed `dev`, `tst`, `prd`, regional, or legal-entity instances
  already exist.

## Core principles

### Git records intent, not live tenant state

Git contains approved, non-secret desired state, schemas, policy, tests, and
promotion evidence. Microsoft Entra and Agent 365 remain authoritative for
deployed objects. A protected evidence store records sanitized read-back
results.

Do not commit server-generated object IDs into reusable templates. Resolve
symbolic references during planning and retain the resulting IDs in the
approved environment evidence record.

### Plan and apply are separate operations

Every mutation starts with a reproducible, read-only plan. The plan identifies:

- source commit and immutable application artifact digest;
- target tenant and environment;
- blueprint, BlueprintPrincipal, identity, registration, APIM, and permission
  changes;
- resolved owners and sponsors;
- API versions and tooling versions;
- required approvals;
- rollback or containment actions; and
- unresolved, destructive, or high-risk operations.

The apply stage must consume the reviewed plan. It must not recalculate a
different plan after approval without stopping for review.

### Dependencies are explicit

The required identity order is:

```text
Agent Identity Blueprint application
  -> Agent Identity BlueprintPrincipal
    -> Blueprint credentials, protocol, permissions, and manager configuration
      -> Agent Identity instance
        -> Instance-specific permissions and attributes
          -> Agent 365 registration
```

The pipeline must wait for and verify each parent before creating its child.
Microsoft Entra propagation is asynchronous, so use bounded retries and
read-back checks rather than fixed success assumptions.

### Promotion advances an immutable release

Build the application once, sign it, scan it, and identify it by digest.
Promote that same artifact through approved stages. Bind stage-specific
identity, APIM, network, and secret configuration at deployment time.

Do not reuse the `local` identity in `dev`, the `dev` identity in `tst`, or the
`tst` identity in `prd`.

## Sources of truth

| Concern | Authoritative source | Repository treatment |
|---|---|---|
| Application source and tests | Git | Reviewed source and test results |
| Deployable application | Approved artifact or image registry | Record immutable digest |
| Agent ID desired state | Git | Internal schemas, blueprint specifications, and instance overlays |
| Credentials and private material | Approved secret store or HSM | Metadata and reference only |
| Entra objects and permissions | Microsoft Entra | Read back after apply |
| Agent inventory registration | Agent 365 | Read back after apply |
| APIM product and attribution | APIM | Read back after apply |
| Release and control evidence | Protected evidence store | Sanitized summary or approved link |
| Change history | [Agent 365 ledger](../a365-changes.md) | Planned and actual outcome |

Generated plans are temporary pipeline artifacts. Generated configuration that
contains credentials or sensitive identifiers must use protected storage,
short retention, and access logging.

## Tool selection

No one tool is the control plane. Select the smallest supported tool that
matches the operation.

Microsoft's documented onboarding sequence is a nonproduction single-agent
validation followed by the official bulk scripts for reviewed batches. Use
the [Microsoft-sourced onboarding guide](./onboarding_agents.md) for those
procedures. DevOps adds bank approval, provenance, policy, and evidence; it
does not make custom Graph code the default onboarding mechanism.

| Need | Preferred tool | Why |
|---|---|---|
| Validate a repository change | Schemas, renderer, unit tests, policy checks | Deterministic and no tenant write |
| Onboard one nonproduction pilot | Agent 365 CLI | Fast supported workflow with dry-run and generated diagnostics |
| Check workstation or tenant prerequisites | Agent 365 CLI `setup requirements` | Supported readiness checks |
| Inspect permission inheritance or instance scopes | Agent 365 CLI `query-entra` | Purpose-built diagnostic surface |
| Export redacted CLI diagnostics | Agent 365 CLI `logs export` | Supported redaction behavior |
| Onboard a reviewed wave of agents | Official Agent 365 bulk-onboarding PowerShell | Validated CSV relationships and dependency ordering |
| Reconcile long-lived desired state and detect drift | Bank-owned provisioning adapter using supported Graph APIs | Plan/apply, stable keys, read-back, and lifecycle control |
| Perform exceptional visual verification | Entra or Microsoft 365 admin portal | Human confirmation and break-glass handling |
| Grant tenant-wide consent | Separately authorized administrator workflow | Preserves segregation of duties |

## When Agent 365 CLI is warranted

Use Agent 365 CLI when all of the following are true:

- the installed version supports the required operation;
- the target is one explicitly named agent or blueprint;
- the operator can inspect the proposed target tenant and object names;
- `--dry-run` is used first when available;
- interactive authentication or consent handoff is acceptable;
- generated configuration can be protected outside source control; and
- independent postconditions will verify the result.

Good uses include:

- `a365 setup requirements`;
- a first nonproduction onboarding pilot;
- `a365 setup blueprint` for a reviewed single-agent workflow;
- config-free external-agent onboarding when its derived objects match the
  approved design;
- `query-entra` permission and inheritance checks;
- redacted support-log export; and
- a human-reviewed cleanup dry run during retirement.

Pin or deliberately approve the CLI version. Use explicit tenant and agent
names. Record the command intent and result in the Agent 365 ledger. Never
parse undocumented human-readable output as a stable automation contract.

### When Agent 365 CLI is not warranted

Do not use the CLI as:

- an importer for the bank-owned YAML desired-state contract;
- the authoritative reconciler for many LOBs, stages, regions, or legal
  entities;
- a loop that creates one blueprint for every identity when several identities
  must share a reviewed trust boundary;
- a noninteractive production consent mechanism;
- an application-build identity with standing tenant-write privileges;
- an unreviewed `setup all` or cleanup step;
- a substitute for observed-state read-back or drift detection; or
- a way to bypass lifecycle, risk, privacy, security, or regional approvals.

The CLI consumes its supported command options and `a365.config.json`. The
repository's internal YAML must first be validated and translated by a
controlled adapter.

## When bulk onboarding is warranted

Use Microsoft's separate bulk-onboarding PowerShell workflow for a bounded,
reviewed onboarding wave when:

- the objects can be represented in the published CSV schema;
- a complete CSV can be reviewed before execution;
- `Blueprint`, `AgentIdentity`, and `AgentRegistration` relationships are
  explicit;
- initial creation is the primary goal; and
- the automation application, permissions, consent, report, retry, and
  rollback behavior have been approved.

A deterministic exporter can compile approved repository artifacts into the
official CSV. The CSV is a generated plan or execution input, not the new
source of truth.

Bulk onboarding is not a complete GitOps reconciler. Do not assume it owns
updates, deletions, drift repair, promotion, or retirement unless the current
Microsoft workflow explicitly supports the required behavior.

## When a custom provisioning adapter is warranted

Use a bank-owned adapter only when a demonstrated requirement is not met by
the supported Microsoft workflow. Shared blueprints, multiple identities,
and existing-object anchors are already supported by bulk onboarding; their
presence alone is not a reason to write a replacement. Requirements to
evaluate against supported tooling include:

- one logical blueprint shared by multiple instance identities;
- separate production and nonproduction blueprints;
- stable symbolic references resolved to tenant object IDs;
- repeatable `local`, `dev`, `tst`, `prd`, regional, and legal-entity
  instances;
- non-mutating plans and protected approval gates;
- safe updates and resumable partial failure;
- desired-versus-observed comparisons;
- drift reporting;
- immutable provenance and evidence; or
- policy that is stricter than a vendor onboarding workflow.

The adapter should use supported Microsoft Graph or official automation
surfaces. It must not recreate Agent ID objects as generic app registrations.

## Decision flow

```text
Is this only a prerequisite or read-only diagnostic?
  Yes -> Use Agent 365 CLI.
  No
    |
    v
Is this one reviewed nonproduction pilot?
  Yes -> Use Agent 365 CLI with dry-run and independent verification.
  No
    |
    v
Is this a bounded initial onboarding wave supported by the official CSV?
  Yes -> Export and use bulk-onboarding PowerShell.
  No
    |
    v
Use the controlled Graph provisioning adapter with plan/apply and drift checks.
```

## Desired-state compilation

The [Markets Risk desired-state package](../lob/markets/markets-risk-analyst/identities/README.md)
is the first implementation of this pattern.

Its checked-in artifacts are internal bank contracts, not Graph payloads. The
compiler or adapter must:

1. Validate every JSON Schema.
2. Render all selected instance plans deterministically.
3. Refuse stale generated output.
4. Resolve each `principalRef` to one approved tenant object.
5. Resolve each `blueprintRef` to an existing or planned blueprint.
6. Determine whether the blueprint requires create, update, or no action.
7. Record the blueprint application object ID, application `appId`, and
   BlueprintPrincipal object ID separately.
8. Set `agentIdentityBlueprintId` from the blueprint application `appId`.
9. Keep permission declaration separate from administrator consent.
10. Create Agent 365 registration only when requested.
11. Read the result back independently.

The internal `apiVersion` is not a Microsoft Graph API version. The adapter
must verify the currently supported Graph endpoint and request shape at
execution time. As reviewed on October 16, 2026, Microsoft documentation uses
v1.0 typed API references for blueprint, BlueprintPrincipal, and Agent
Identity creation. One higher-level Agent Identity guide still contains an
older beta request example, so execution-time verification remains required.

## Pipeline design

### Current reference implementation

The [Markets Risk Agent ID workflow](../.github/workflows/markets-risk-agent-id.yml)
and its [deterministic Graph adapter](../lob/markets/markets-risk-analyst/identities/provision.py)
are the first Markets-only implementation of this model. The workflow calls
Microsoft Graph v1.0 directly; it does not invoke Agent 365 CLI. The
[Markets desired-state package](../lob/markets/markets-risk-analyst/identities/README.md)
remains the source of approved blueprint and instance intent.

The implementation is checked in but dormant. Both blueprints and all four
instances remain `proposed` with `provisioningEnabled: false`. The risk tier
and production geography are unresolved. No GitHub environment, federated
planner or provisioner, Graph permission or consent, symbolic principal
mapping, tenant blueprint, BlueprintPrincipal, Agent Identity, Agent 365
registration, APIM binding, runtime credential, or deployed shared stage is
created merely because the workflow exists.

#### Workflow entry points

| Entry point | Tenant token | Behavior |
|---|---|---|
| Pull request | None | Install pinned tooling, run renderer and provisioner tests, validate policy, and render all discovered instances deterministically |
| Manual `plan` | Planner OIDC token | Read the selected tenant and instance, resolve symbolic principals, write an immutable plan, and upload it for review |
| Manual `apply` | Nonproduction or production provisioner OIDC token | Revalidate the approved plan, create or verify core Agent ID objects, read them back, and upload sanitized evidence |

Manual runs select one of `local`, `dev`, `tst`, or `prd`. The apply path also
requires:

- the workflow source to be the protected `main` branch;
- an applicable plan created in the same workflow run;
- exact confirmation in the form `APPLY <instance>`;
- approval for the target protected GitHub environment;
- unchanged source, desired-state, principal mapping, and tenant state; and
- lifecycle approval for both the selected blueprint and instance.

Workflow concurrency is scoped to the selected instance and does not cancel an
apply already in progress.

#### GitHub environments and OIDC applications

Create three separate GitHub environments and three separate Microsoft Entra
applications:

| GitHub environment | Entra application | Allowed responsibility |
|---|---|---|
| `markets-risk-agent-id-plan` | Markets Risk planner | Tenant-aware plan and principal resolution only |
| `markets-risk-agent-id-nonprod` | Markets Risk nonproduction provisioner | Core blueprint and `local`, `dev`, or `tst` Agent ID operations |
| `markets-risk-agent-id-prd` | Markets Risk production provisioner | Core production blueprint and `prd[-instance]` Agent ID operations |

All three GitHub environments must:

- allow deployments only from protected `main`;
- require named reviewers;
- prevent self-approval by the application author;
- keep production reviewers separate from nonproduction reviewers; and
- retain deployment and approval history.

Each Entra application uses an environment-scoped GitHub federated identity
credential with audience `api://AzureADTokenExchange`. For this repository,
the expected subjects are:

```text
repo:drewelewis/ai-hybrid-data-sources:environment:markets-risk-agent-id-plan
repo:drewelewis/ai-hybrid-data-sources:environment:markets-risk-agent-id-nonprod
repo:drewelewis/ai-hybrid-data-sources:environment:markets-risk-agent-id-prd
```

Do not configure a client secret. The adapter obtains the GitHub OIDC token,
exchanges it for an app-only Microsoft Graph token, and never logs either
token.

#### Required GitHub variables

Configure these environment variables in each protected GitHub environment:

| Variable | Purpose |
|---|---|
| `ENTRA_TENANT_ID` | Explicit target tenant UUID |
| `ENTRA_CLIENT_ID` | Client UUID of that environment's planner or provisioner application |
| `AGENT_ID_PRINCIPAL_MAP_JSON` | Reviewed mapping from symbolic repository references to exact tenant object UUIDs and principal types |

Principal maps contain identifiers, not credentials. They must use this
closed shape:

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

The production mapping uses
`markets-agent-identity-production-provisioner`. The adapter resolves every
object ID directly and rejects missing entries, type mismatches, invalid
UUIDs, and duplicate or ambiguous tenant objects. Sponsor groups must be
dynamic-membership or Microsoft 365 groups. Assigned security groups and
role-assignable groups are rejected. Owners must be users or service
principals because Agent ID does not support groups as owners.

The applying workload service principal must be a declared blueprint owner.
This ensures that the owner Microsoft Graph automatically associates with a
new blueprint is already part of approved desired state.

#### Microsoft Graph application permissions

| Application | Required application permissions |
|---|---|
| Planner | `AgentIdentityBlueprint.Read.All`, `AgentIdentityBlueprintPrincipal.Read.All`, `AgentIdentity.ReadWrite.All`, `Application.Read.All`, `Group.Read.All`, `User.Read.All` |
| Nonproduction provisioner | `AgentIdentityBlueprint.ReadWrite.All`, `AgentIdentityBlueprintPrincipal.ReadWrite.All`, `AgentIdentity.ReadWrite.All`, `Application.Read.All`, `Group.Read.All`, `User.Read.All` |
| Production provisioner | Same API permissions as the nonproduction provisioner, but on a separate application, federated credential, GitHub environment, and approval path |

An authorized identity administrator creates the applications, grants the
permissions, and completes admin consent outside the application workflow.
Application authors and runtime Agent Identities must not hold these
provisioning permissions.

The current Graph v1.0 sponsor-list API requires
`AgentIdentity.ReadWrite.All` application permission even for read-back. The
Markets planner therefore has a write-capable token despite being an
operationally read-only role. Its adapter enforces GET-only requests in code,
uses a separate federated application, and must be monitored for any Graph
write. Its GitHub environment must allow only protected `main` deployments
and require named reviewers so modified branch code cannot obtain the token.
Reassess and reduce that permission when Microsoft exposes a read-scoped
sponsor-list operation.

#### Plan contract

The tenant-aware plan records:

- plan schema and Microsoft Graph API versions;
- target tenant, instance, and environment;
- source commit and desired-state digest;
- reviewed principal object IDs and types;
- sanitized observed blueprint, BlueprintPrincipal, and Agent Identity IDs;
- `create` or `verify` actions in dependency order;
- policy, lifecycle, mapping, duplicate, and drift blockers;
- deferred operations; and
- a digest over the complete plan.

The plan is deterministic for the same source and tenant state. The apply job
downloads the plan artifact from the same workflow run, validates its digest,
rerenders desired state, reresolves principals, and replans immediately before
mutation. Any difference stops apply and requires a new reviewed plan.

#### Apply and read-back contract

The adapter is deliberately create-or-verify only:

1. Create or verify the Agent Identity Blueprint.
2. Record its application object `id` and application `appId` separately.
3. Create or verify the BlueprintPrincipal from the blueprint `appId`.
4. Wait with bounded retries for directory propagation.
5. Create or verify the selected Agent Identity using that blueprint `appId`.
6. Add the approved Agent Identity owners.
7. Read owners, sponsors, tags, blueprint relationship, and all three object
   IDs back from Microsoft Graph.
8. Fail unless every resulting action is `verify`.

The adapter refuses updates, deletes, permissions, consent, credentials,
duplicate display names, unsupported principal types, unapproved lifecycle,
unresolved governance, drift, plan tampering, stale plans, branch mismatch,
and target-tenant mismatch. It does not silently adopt or repair existing
objects.

Successful evidence uses result `core-agent-id-provisioned` and records only
non-secret IDs, digests, actions, and deferred operations. If apply fails
after mutation might have begun, the workflow uploads
`failed-or-partial` evidence that instructs operators to read tenant state
before retrying. Never blindly rerun a failed apply.

#### Deferred rollout gates

Core Agent ID evidence does not mean the agent is registered, credentialed,
connected, or production-ready. The current adapter explicitly defers:

- Agent 365 inventory registration;
- APIM product and runtime binding;
- blueprint credential creation or rotation;
- custom security attribute assignment;
- manager-application configuration;
- permission grants and administrator consent; and
- runtime, Purview, Defender, Entra, and Agent 365 telemetry acceptance.

Other LOBs must not copy the workflow until they have their own validated
desired-state package, owner and sponsor topology, protected environments,
and approved planner and provisioner identities. The repeated workflow
surface should be extracted into a centrally owned reusable workflow after a
second LOB proves that the contract is stable.

### Pull-request validation

Every pull request that changes an application, blueprint, identity overlay,
permission, APIM reference, or lifecycle must run:

1. schema and policy validation;
2. unit and focused integration tests;
3. dependency, license, and secret scanning;
4. prohibited direct-model-endpoint checks;
5. deterministic rendering;
6. identity and blueprint uniqueness checks;
7. unresolved-governance checks;
8. documentation and ledger checks; and
9. a read-only desired-versus-observed plan when tenant read access is
   available.

Pull-request validation must not have tenant-write, consent, production
secret, or production deployment authority.

### Plan

The protected plan stage:

- selects the target tenant and instance explicitly;
- resolves symbolic references;
- reads current blueprint, principal, identity, permission, registration, and
  APIM state;
- calculates additions, updates, unchanged objects, and removals;
- fails on ambiguous names, duplicate stable keys, or unowned objects;
- identifies preview or changed API surfaces;
- attaches source and artifact digests; and
- produces a human-readable and machine-readable plan.

Destructive changes, permission expansion, credential replacement, blueprint
splits, sponsor changes, and production changes require highlighted approval.

### Approval

Use protected environments and named approvers. At minimum, separate:

- application author;
- LOB product or business sponsor;
- identity administrator;
- security and privacy reviewers;
- model-risk and compliance reviewers where applicable;
- production release manager; and
- administrator who grants tenant-wide consent.

The [tenant governance guide](./tenant_governance.md) defines the baseline
RACI. The [LOB rollout strategy](./lob_rollout_strategy.md) defines the
promotion evidence.

### Apply blueprints

For each approved blueprint:

1. Create or update the blueprint application.
2. Read back its application object ID and `appId`.
3. Create or verify the BlueprintPrincipal.
4. Wait for directory propagation.
5. Configure approved credential mechanisms, protocol properties,
   `managerApplications`, and inheritable permission declarations.
6. Verify no prohibited credential or permission exists.

Do not place credentials on Agent Identity service principals.

### Apply instances

For each approved instance:

1. Resolve its `blueprintRef` to the verified blueprint `appId`.
2. Create or update the Agent Identity.
3. Assign approved sponsors and owners.
4. Apply tags and custom security attributes.
5. Apply only approved instance-specific permissions.
6. Verify that the instance references the expected blueprint.

One instance failure must not silently redirect the runtime to another stage's
identity.

### Register and deploy

Agent 365 registration is separate from Agent Identity creation. Create or
update the inventory record only after the identity is verified.

Application deployment then binds:

- the immutable application artifact;
- the stage-specific Agent Identity;
- the stage-specific APIM product or subscription;
- approved on-premises network configuration; and
- credential references from the approved secret store.

The pipeline must never copy a local `.env` file to a shared or production
runtime.

### Verify and publish evidence

Acceptance requires independent read-back of:

- blueprint and BlueprintPrincipal;
- identity-to-blueprint relationship;
- owners and sponsors;
- credentials by type and expiry, never value;
- permissions and consent status;
- custom security attributes and tags;
- Agent 365 registration;
- APIM attribution and limits;
- runtime health and token readiness; and
- expected Entra, Purview, Defender, and Agent 365 telemetry.

Use the [verification process](./verification_process.md). Record partial
success explicitly; do not turn a failed read-back into a success-shaped
pipeline result.

## Environment promotion

| Stage | Pipeline posture | Identity posture | Minimum gate |
|---|---|---|---|
| `local` | Developer validation with no production authority | Dedicated local integration identity or approved short-lived mechanism | Business owner, initial risk and data review, unit and evaluation evidence |
| `dev` | Shared nonproduction integration | Separate `-dev` identity and APIM boundary | Architecture, threat, privacy, authorization, telemetry, quota, cost, and recovery evidence |
| `tst` | Independently controlled production-like validation | Separate `-tst` identity and production-like policy | End-to-end, adversarial, resilience, rollback, Purview, Defender, Entra, and operational acceptance |
| `prd` | Protected release with named approvers and ring controls | Separate `-prd[-geo]` identity and production credential boundary | Formal approvals, immutable release, rollback rehearsal, support readiness, and residual-risk acceptance |

Promotion changes lifecycle only for the target instance. It must not enable
every instance that shares a base or blueprint. A production blueprint and
identity remain independently approved from nonproduction.

## Pipeline identities and permissions

Use separate identities for separate responsibilities:

| Identity | Allowed responsibility | Prohibited responsibility |
|---|---|---|
| Build identity | Build, test, scan, sign, publish artifact | Tenant writes, consent, production secrets |
| Planner identity | Read approved Entra, Agent 365, and APIM state; adapter must enforce GET-only behavior | Graph mutation and consent; monitor the temporary write-capable sponsor-read permission |
| Nonproduction provisioner | Approved nonproduction identity operations | Production objects and tenant-wide consent |
| Production provisioner | Approved production plan application | Self-approval and unrelated LOB objects |
| Consent administrator | Explicit approved grants | Application deployment and source modification |
| Runtime Agent Identity | Runtime token acquisition and approved resource access | Provisioning or managing other identities |
| Evidence reader | Read-back and audit collection | Mutation |

Prefer workload federation or certificates for automation. Use client secrets
only where explicitly approved, time-bounded, and stored in an approved secret
service.

## Branching, releases, and provenance

Use short-lived branches and protected pull requests into the main branch.
Environment state should be selected by reviewed instance overlays and
protected pipeline environments, not long-lived environment branches that
drift independently.

Every plan and evidence record should include:

- repository and source commit;
- application artifact digest;
- renderer and schema version;
- input digest;
- target tenant, environment, and instance key;
- approved plan digest;
- tool and API versions;
- operator or workload identity;
- start and completion timestamps;
- non-secret created or changed object IDs;
- verification results; and
- approval and exception references.

## Drift management

Run scheduled read-only reconciliation. Classify drift as:

| Class | Example | Default action |
|---|---|---|
| Expected | Server-generated timestamp or ID | Record and ignore |
| Review required | Owner or sponsor changed through an approved emergency process | Open reconciliation pull request |
| High risk | Permission expansion, unknown credential, blueprint reassignment, missing sponsor | Alert, block promotion, and investigate |
| Critical | Production identity disabled unexpectedly or unapproved credential added | Invoke incident and containment procedures |

Do not automatically delete unknown production objects or revoke permissions
without an approved policy and tested rollback. Drift repair must produce a
new plan.

## Failure, rollback, and retirement

Microsoft Graph and Agent 365 operations are not one atomic transaction. On
partial failure:

1. Stop further dependent mutations.
2. Read back every attempted object.
3. Record which operations succeeded.
4. Preserve correlation IDs and redacted diagnostics.
5. Disable or contain exposed runtime access.
6. Resume only from a newly calculated and approved plan.

Application rollback and identity rollback are separate. Rolling back an
application image does not normally mean deleting its identity.

For retirement:

1. Stop or isolate the runtime.
2. Preserve required evidence.
3. Disable the instance identity.
4. Remove direct permissions and registration.
5. Remove the instance after retention approval.
6. Remove blueprint credentials.
7. Delete the BlueprintPrincipal and blueprint only after every dependent
   instance is gone.
8. Verify deletion and account for orphaned Agent users separately.

Never place unreviewed cleanup or `--yes` behavior in a pipeline.

## Markets reference activation sequence

The workflow and adapter are implemented, but activation remains an
administrative change:

1. Create the separate planner, nonproduction provisioner, and production
   provisioner applications.
2. Grant and consent only the application permissions listed above.
3. Create one environment-scoped GitHub federated credential on each
   application.
4. Create the three protected, main-only GitHub environments with named
   reviewers and separation of duties.
5. Populate `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, and the reviewed principal
   map in each environment.
6. Confirm the business sponsor is a supported group and each technical owner
   is the expected provisioner service principal or approved user.
7. Resolve the risk tier and, for production, region and legal entity.
8. Approve and enable only the target blueprint and instance through a pull
   request.
9. Run manual `plan`, inspect the plan digest, objects, actions, blockers, and
   deferred operations, and retain approval evidence.
10. Run `apply` with exact typed confirmation and protected-environment
    approval.
11. Inspect success or failed-or-partial evidence and independently verify the
    tenant objects.
12. Complete the separate Agent 365 registration, credential, APIM/runtime,
    custom-attribute, permission, consent, deployment, and telemetry gates.
13. Update desired and observed lifecycle records through a new reviewed
    change; do not edit the applied commit or generated evidence.

Do not begin tenant mutation until the unresolved risk tier, owners, sponsors,
region, legal entity, credential mechanism, permissions, and approvals are
resolved for the target instance.

## Extending the workflow to other LOBs

Each LOB ultimately needs a rollout entry point, but not a copied independent
control plane. Before adding one, the LOB must have:

- a schema-validated desired-state package;
- explicit production and nonproduction blueprint boundaries;
- independently promoted instance overlays;
- approved sponsor and owner topology;
- stage-specific APIM and runtime references;
- lifecycle and unresolved-governance enforcement;
- renderer and provisioner tests; and
- approved planner and provisioner applications and GitHub environments.

After a second LOB proves that these inputs are stable, extract the common
jobs into one centrally owned reusable workflow. Each LOB should then have a
thin caller that supplies only its package path, LOB key, supported instances,
environment mapping, and approved policy profile. Do not give one LOB caller
access to another LOB's provisioner application or GitHub environment.

## Related guidance

- [Agent 365 CLI guide](./agent365_cli.md)
- [Provisioning runbook](./provisioning_runbook.md)
- [LOB rollout strategy](./lob_rollout_strategy.md)
- [Tenant governance](./tenant_governance.md)
- [Security and privacy](./security_and_privacy.md)
- [Operations runbook](./operations_runbook.md)
- [Verification process](./verification_process.md)
- [Markets Risk desired-state package](../lob/markets/markets-risk-analyst/identities/README.md)

Microsoft references:

- [Agent 365 CLI reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/)
- [Onboard a single agent with Agent 365 CLI](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-365-onboarding-cli)
- [Agent 365 bulk onboarding with PowerShell](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/bulk-agent-365-onboarding)
- [Create an Agent Identity Blueprint](https://learn.microsoft.com/en-us/entra/agent-id/create-blueprint)
- [Create Agent Identities](https://learn.microsoft.com/en-us/entra/agent-id/create-delete-agent-identities)
