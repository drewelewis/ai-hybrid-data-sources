# Agent 365 Tenant Governance

## Objective

Define who approves, operates, reviews, and responds to the Trading Platform
Agent after it is registered in Agent 365.

## Required roles

| Responsibility | Typical role |
|---|---|
| Blueprint registration | Agent ID Developer or Global Administrator |
| Consent | Global Administrator |
| Agent inventory and policy | Agent 365 AI administrator |
| Identity policy | Entra administrator/security |
| Threat monitoring | Security operations/Defender |
| Data compliance | Purview/compliance administrator |
| Business accountability | Sponsor |
| Runtime operation | Application owner |

Use the least privileged role that supports each task.

## RACI

| Activity | Sponsor | App owner | Identity admin | Security | Compliance |
|---|---|---|---|---|---|
| Approve purpose | A/R | C | I | C | C |
| Register blueprint | I | R | A | I | I |
| Grant permissions | C | R | A | C | C |
| Configure telemetry | I | A/R | C | C | C |
| Apply policy template | C | C | A/R | C | C |
| Review risk signal | I | C | C | A/R | C |
| Privacy review | C | C | I | C | A/R |
| Disable agent | A | R | R | R | C |
| Retire identity | A | R | R | C | C |

Customize named people/groups before production.

## Policy template

Apply an Agent 365 policy template appropriate for an internal, local,
portfolio-data agent.

The template should address:

- Identity and sign-in controls.
- Permission approval and expiry.
- External content sharing restrictions.
- Data/compliance controls.
- Threat protection.
- Lifecycle review.

Record the assigned template and deviations. Do not manage every agent with
unique manual controls when a reusable template can prevent drift.

## Tenant settings

Review Microsoft 365 admin center under **Agents > Settings**:

- Agent availability and publishing controls.
- User access and sharing controls.
- Feedback/data-sharing settings.
- Tags.
- Connected platforms.
- Any preview-specific settings.

Recommended tags:

- `owner-portfolio-platform`
- `environment-local-dev`
- `data-confidential`
- `identity-agent-id`
- `telemetry-metadata-only`

## Identity governance

- Require a sponsor and technical owner.
- Review permissions quarterly.
- Use agent/workload Conditional Access.
- Prefer federation to secrets.
- Assign Azure RBAC directly to the agent identity.
- Disable stale or ownerless identities.
- Separate development and production instances.

## Risk management

Agent 365 risk combines signals from Entra, Purview, and Defender.

Triage priority:

1. High severity and high confidence.
2. Unexpected permission or tool use.
3. Prompt-injection detection.
4. Sensitive-data access or exfiltration signal.
5. Anomalous sign-in or credential behavior.

Response options:

- Limit or remove access.
- Disable the agent identity.
- Revoke blueprint credentials.
- Escalate to Defender investigation.
- Preserve trace and identity evidence.

## Purview and data governance

- Classify portfolio and trade data as confidential.
- Keep content capture disabled.
- Review audit visibility.
- Define retention and legal-hold requirements.
- Assess DLP before enabling Microsoft 365 tools.
- Do not grant Work IQ or Graph data access in the telemetry-only phase.

## Licensing

- Identity registration does not require the observability license.
- Observability requires at least one tenant user assigned Microsoft 365 E7 or
  Microsoft Agent 365.
- Work IQ requires Microsoft 365 Copilot and remains out of scope.
- Agent user/notification scenarios require applicable preview access and
  licenses and remain out of scope.

## Review cadence

| Review | Cadence |
|---|---|
| Risk signals | Daily |
| Telemetry and exporter health | Weekly |
| Permissions and sponsor | Monthly |
| Full access/lifecycle review | Quarterly |
| Policy template review | Semiannual or after material change |

## Approval gates

Require written approval before:

- Enabling content recording.
- Adding Graph/Work IQ tools.
- Adding an agent user account.
- Making the blueprint multitenant.
- Sharing production credentials.
- Expanding inherited permissions.
- Changing retention or residency posture.

## References

- [Agent settings](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/agent-settings)
- [Detect risky agents](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/detect-risky-agents)
- [Scale governance](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/scale-governance)
- [Govern local agents](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/govern-local-agents)
