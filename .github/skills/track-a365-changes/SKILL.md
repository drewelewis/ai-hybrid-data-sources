---
name: track-a365-changes
description: 'Track every Microsoft Agent 365 (A365), Microsoft Entra Agent ID, Agent 365 CLI, identity, registry, observability, governance, licensing, permission, local-tooling, and runtime change in /a365-changes.md. Use before and after any A365 investigation, setup, onboarding, provisioning, configuration, code change, validation, rollback, or cleanup.'
---

# Track Agent 365 changes

## Purpose

Maintain an auditable, chronological record of all Agent 365 work in the
repository-root [`a365-changes.md`](../../../a365-changes.md).

## Mandatory workflow

1. Read `a365-changes.md` before performing Agent 365 work.
2. Identify the proposed action, scope, expected effect, and rollback.
3. Record the action as `Planned` before making a state-changing operation.
4. Obtain approval when the operation creates, modifies, consents, disables, or
   deletes tenant, cloud, identity, permission, license, or production objects.
5. Perform the smallest approved action.
6. Validate the actual result.
7. Update the same entry to `Succeeded`, `Failed`, `Partially succeeded`,
   `Cancelled`, or `Rolled back`.
8. Record unexpected side effects and follow-up work.

Read-only discovery may be recorded after a coherent discovery batch, but it
must be recorded before any resulting state change.

## What must be recorded

- Repository files and dependencies changed.
- Workstation tools, SDKs, modules, environment variables, and configuration.
- Agent 365 CLI commands and outcomes.
- Tenant IDs and non-secret object IDs.
- App registrations, enterprise applications, blueprints,
  BlueprintPrincipals, agent identities, sponsors, and registry entries.
- Permissions requested, consented, denied, or removed.
- Licenses and tenant settings checked or changed.
- Runtime identity, sidecar, telemetry, Defender, Purview, and governance
  changes.
- Validation evidence, failures, rollback steps, and cleanup.

## Entry format

Use one entry per coherent action:

```markdown
## YYYY-MM-DD HH:MM TZ - Short title

- **Status:** Planned | Succeeded | Failed | Partially succeeded | Cancelled | Rolled back
- **Scope:** Workstation | Repository | Tenant | Azure | Runtime
- **Requested by:** User | Assistant | Administrator
- **Purpose:** Why the action is needed.
- **Change:** Exact action and affected objects or paths.
- **Result:** Actual outcome, including versions and non-secret IDs.
- **Validation:** How the result was verified.
- **Rollback:** Exact reversal or `Not applicable`.
- **Follow-up:** Remaining action or `None`.
```

Update a planned entry in place after execution. Do not create separate
success-only entries that lose the original intent.

## Security rules

- Never record secrets, tokens, passwords, client-secret values, device codes,
  private keys, connection strings, or sensitive portfolio content.
- Redact command arguments that contain credentials.
- Record secret metadata only: storage location, credential type, owner, and
  expiry.
- Treat the ledger as operational documentation, not as a secret store.

## Integrity rules

- Keep entries in chronological order.
- Do not erase history. Add a clearly labeled correction if an earlier entry
  is inaccurate.
- Distinguish intended architecture from deployed state.
- Distinguish read-only checks from state changes.
- Record partial and failed operations, including artifacts they may have left.
- Do not claim success without validation.
