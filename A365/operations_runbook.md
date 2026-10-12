# Agent 365 Operations Runbook

## Scope

This runbook covers normal operation, monitoring, credential rotation,
disablement, incident response, and retirement after the A365 integration is
implemented.

## Start and health verification

1. Start the Docker stack using the existing project workflow.
2. Verify the API:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8989/health
   ```

3. Verify the Agent ID sidecar health endpoint from the API network.
4. Run one non-sensitive test prompt.
5. Confirm an `invoke_agent` trace appears in the expected A365 surfaces.

Expected health:

- API healthy.
- Agent ready.
- Database connected.
- Sidecar healthy when A365 is enabled.
- Exporter queue operating without drops.

## Routine operating cadence

### Daily

- Review exporter authentication failures.
- Review sidecar health failures.
- Review APIM/model throttling separately from telemetry failures.
- Triage high-confidence agent risk signals.

### Weekly

- Confirm traces appear for successful and failed runs.
- Review Defender activity for unexpected tools or access.
- Review telemetry queue drops and exporter timeouts.
- Verify no sensitive content is present.

### Monthly

- Review direct and inherited permissions.
- Confirm sponsor and technical owner.
- Review Conditional Access and policy template assignment.
- Confirm the agent is still required.
- Review credentials approaching expiry.

### Quarterly

- Perform access and lifecycle review.
- Test emergency disable and rollback in nonproduction.
- Review dependency and sidecar versions.
- Revalidate privacy, retention, and licensing.

## Credential rotation

1. Create the replacement blueprint credential.
2. Configure the runtime/secret store with the replacement.
3. Restart the sidecar/API in nonproduction.
4. Validate token subject, audience, tenant, and expiry.
5. Validate end-to-end telemetry.
6. Roll out to production.
7. Remove the old credential.
8. Record operator, timestamps, and validation evidence.

Never rotate by editing a secret into source control.

## Emergency disable

Use the narrowest control that contains the incident:

| Scope | Action |
|---|---|
| One instance | Disable that agent identity |
| Entire agent family | Revoke/disable blueprint credential |
| Telemetry only | Set `ENABLE_A365_OBSERVABILITY=false` |
| Model access | Revoke APIM/user authorization separately |
| Database access | Disable database authorization separately |

Disabling telemetry does not disable the agent. Disabling the agent identity
does not automatically revoke the user's APIM token.

## Incident response

1. Record detection time, agent ID, blueprint ID, trace ID, and affected host.
2. Disable the affected identity if continued operation is unsafe.
3. Preserve API, sidecar, Entra, Defender, Purview, and APIM evidence.
4. Review recent permission changes and sign-ins.
5. Review tool and model operations in the trace.
6. Rotate compromised blueprint credentials.
7. Confirm no other identities share the credential boundary unexpectedly.
8. Restore only after sponsor, security, and technical owner approval.

Do not place tokens, keys, prompts, or portfolio data in incident tickets.

## Telemetry rollback

```dotenv
ENABLE_A365_OBSERVABILITY=false
```

Restart only the API container and verify:

- Chat still works.
- APIM still works.
- Database tools still work.
- No new A365 traces are emitted.

Preserve exporter logs for diagnosis.

## Retirement

1. Obtain sponsor approval.
2. Stop the runtime.
3. Preserve required evidence.
4. Remove permission assignments.
5. Disable and then delete the agent identity.
6. Remove credentials from the blueprint.
7. Delete the blueprint only after all child identities are retired.
8. Remove generated local configuration and secrets.
9. Confirm no orphaned agent user account exists.
10. Update the A365 inventory and documentation status.

## Evidence checklist

- Registration object IDs.
- Sponsor and owner.
- Permission grant record.
- Credential type and expiry, never value.
- Version matrix.
- Test trace ID.
- Defender/Purview validation evidence.
- Privacy inspection result.
- Rotation and disable test result.
- Final retirement approval.
