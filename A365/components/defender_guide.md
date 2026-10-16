# Microsoft Defender Guide for Agent 365

## Purpose

This guide maps the major Microsoft Defender surfaces where Agent 365
inventory, activity, risk, detections, alerts, and investigations can appear.
Use it to answer:

- Is the agent represented in the cross-product AI security inventory?
- Did Agent 365 activity arrive in Defender Advanced Hunting?
- Did a query or detection identify suspicious behavior?
- Did that behavior become an alert, incident, or case?

These are separate assertions. A healthy Agent 365 exporter, a successful
HTTP response, a visible inventory record, a hunting event, and an alert do
not prove one another.

For end-to-end acceptance, use the
[verification process](../verification_process.md). For trace fields and
larger hunting queries, use the
[observability reference](../observability_reference.md).

## Reference identifiers

Use stable identifiers rather than display names alone:

| Identifier | Value |
|---|---|
| Tenant ID | `00648bab-6c91-4292-9a2a-2297df511222` |
| Runtime agent name | `TradingPlatformAgent` |
| Agent Identity application ID | `7f2edbcc-8375-4d1d-a430-93c14e8db94e` |
| Blueprint application ID | `341ff526-fa67-4487-a028-5d61dd6e5a92` |
| Service name | `ai-agent-starter-portfolio-manager` |
| Channel | `local-cli` |

The application IDs above are client IDs. They are not Microsoft Entra object
IDs, hunting event IDs, trace IDs, or Defender application catalog IDs.

## Major Defender areas at a glance

| Area | What to look for | What it proves |
|---|---|---|
| Security Dashboard for AI | AI inventory, AI risk, attack paths, security recommendations | Defender, Purview, and Entra signals have been aggregated for an AI asset |
| Advanced Hunting | `CloudAppEvents` rows and Agent 365 action types | Defender indexed raw activity that can be queried |
| Custom detections | A scheduled rule based on a proven hunting query | Matching future events can produce security alerts |
| Incidents, alerts, and cases | Alert grouping, affected entities, investigation state, evidence | A security analytic or detection fired and entered SecOps workflow |
| Cloud apps and App Governance | Connected app inventory, OAuth/app behavior, governance findings | Supporting Defender for Cloud Apps coverage exists |

## 1. Security Dashboard for AI

Open [Security Dashboard for AI](https://ai.security.microsoft.com).

Use this cross-product starting point for:

- **AI inventory:** discovered AI applications and agents, active/inactive
  status, and links into asset detail.
- **AI risk:** misconfigurations, attack paths, data leaks, and risky agents.
- **Security recommendations:** posture actions grouped under Microsoft Entra,
  Microsoft Defender, and Microsoft Purview.
- **Cross-service triage:** a high-level view that can link to the product
  responsible for the underlying identity, data, or behavior signal.

Always open the asset and correlate its Agent ID with the registered Agent
Identity application ID. Aggregate inventory totals can include Microsoft
agents, cloud agents, discovered applications, and other agent platforms. An
aggregate count does not prove that `TradingPlatformAgent` is present.

The dashboard is a posture and prioritization surface. It is not a replacement
for the raw hunting evidence in `CloudAppEvents`.

## 2. Advanced Hunting

Open [Microsoft Defender](https://security.microsoft.com), then go to
**Advanced Hunting**.

### 2.1 Confirm the table

Start with the smallest query:

```kusto
CloudAppEvents
| take 1
```

Interpret the result carefully:

| Result | Interpretation |
|---|---|
| Table resolves and returns rows | Defender for Cloud Apps data is available |
| Table resolves and returns zero rows | Schema exists, but no rows match the current tenant/time window |
| Table cannot be resolved | Defender for Cloud Apps or hunting schema provisioning needs investigation |
| Query is forbidden | The operator lacks the required hunting permission |

The table contains activity from many applications. A populated table is not
by itself proof of Agent 365 ingestion.

Current Defender Security for AI setup guidance requires the Microsoft 365
connector data path with **Microsoft Entra ID Management events** and
**Microsoft 365 activities** enabled before relying on `CloudAppEvents`.
Treat that as one-time Defender tenant setup, not as a custom detection and
not as a reason to enable prompt or response recording.

### 2.2 Search for Agent 365 actions

Use the registered Agent Identity application ID:

```kusto
let agentIdToFind = "7f2edbcc-8375-4d1d-a430-93c14e8db94e";
CloudAppEvents
| where Timestamp > ago(7d)
| where ActionType in (
    "InvokeAgent",
    "InferenceCall",
    "ExecuteToolBySDK",
    "ExecuteToolByGateway",
    "ExecuteToolByMCPServer")
| extend data = parse_json(tostring(RawEventData))
| extend AgentId = tostring(data.AgentId)
| extend TargetAgentId = tostring(data.TargetAgentId)
| extend PlatformTargetAgentId = tostring(data.PlatformTargetAgentId)
| where AgentId == agentIdToFind
    or TargetAgentId == agentIdToFind
    or PlatformTargetAgentId == agentIdToFind
| project Timestamp, ActionType, AgentId, ReportId, data
| order by Timestamp desc
```

Do not assume every tenant uses identical `RawEventData` fields. First inspect
a real row, then adapt projections to the current schema. Useful base columns
include:

- `Timestamp`
- `ActionType`
- `Application`
- `AccountObjectId`
- `ObjectId`
- `ReportId`
- `RawEventData`
- `AdditionalFields`

Never paste raw prompts, responses, tokens, portfolio records, or full dynamic
payloads into tickets or documentation.

### 2.3 Correlate a known run

Record a sanitized test window before generating activity:

1. UTC start time.
2. Agent Identity application ID.
3. Runtime agent and service names.
4. Test category, such as model-only or tool invocation.
5. Trace ID when safely available.

Search a narrow window first, then widen it. Keep the Agent ID predicate even
when the time range is widened.

### 2.4 Query without the portal

The repository includes a read-only wrapper for the Microsoft Graph Advanced
Hunting API:

```powershell
pwsh
.\A365\query-defender.ps1
```

The script uses delegated `ThreatHunting.Read.All`, stores no application
secret, and can return the schema with `-IncludeSchema`. See
[query-defender.ps1](../query-defender.ps1) and the
[observability reference](../observability_reference.md) for usage.

## 3. Custom detections

Create a custom detection only after:

1. The base table returns current rows.
2. The Agent ID query returns the expected events.
3. The query reliably distinguishes suspicious activity from normal runs.
4. Required timestamp and entity columns satisfy Defender's detection-rule
   requirements.
5. Severity, frequency, ownership, and response actions are approved.

A custom detection turns a repeatable query into a scheduled analytic. It can
create alerts when future rows match. It does not backfill missing Agent 365
telemetry and should not be used to manufacture evidence that ingestion works.

Keep detection logic metadata-focused where possible. Do not place prompt text
or sensitive tool payloads in alert titles or descriptions.

The verification harness's randomized exploit attempts are useful test
traffic, but `CloudAppEvents` may expose only invocation, inference, tool, and
identity metadata. A prompt that reads like an attack does not automatically
create a Defender alert. Correlate the generated UTC-bounded query first, then
decide whether a supported built-in protection or separately approved custom
detection should classify that activity.

### 3.1 Automation boundary

Ad-hoc hunting and persisted detections use different Microsoft Graph
surfaces:

| Artifact | Supported automation | Stability |
|---|---|---|
| Run an Advanced Hunting query | `POST /v1.0/security/runHuntingQuery` with `ThreatHunting.Read.All` | Microsoft Graph v1.0 |
| Create a persisted custom detection | `POST /beta/security/rules/detectionRules` with `CustomDetection.ReadWrite.All` | Microsoft Graph beta |
| Defender Security for AI real-time protection rule | Defender portal | Preview; no documented Graph or PowerShell creation API |

These are Microsoft Defender control-plane objects, not Azure Resource Manager
resources. Do not add them to this repository's Bicep deployment. A future
configuration-as-code script can manage a beta custom detection only after its
KQL, schedule, severity, response action, permissions, and rollback are
separately approved. Disable the rule before deleting it during rollback.

## 4. Incidents, alerts, and cases

Use **Incidents**, **Alerts**, and **Cases** after a Defender analytic,
Microsoft detection, or approved custom detection has fired.

Review:

- Alert title, severity, confidence, and detection source.
- The affected Agent ID, application, account, or other entity.
- First and last activity time in UTC.
- Evidence and the hunting query that produced it.
- Related alerts grouped into the same incident.
- Investigation owner, status, classification, and remediation actions.

Raw hunting events do not automatically become alerts. Zero alerts can mean:

- no detection matched;
- the detection is disabled or misconfigured;
- required data has not arrived;
- the event is benign; or
- the operator cannot view alerts.

An alert-visibility problem is therefore different from an ingestion problem.

## 5. Cloud apps and App Governance

`CloudAppEvents` is part of the Defender for Cloud Apps hunting schema. Use the
**Cloud apps** and **App Governance** areas to review:

- Microsoft 365 and other connected applications.
- OAuth applications and permissions.
- App behavior and governance findings.
- Connector and data-source health.

Generic `CloudAppEvents` documentation describes Microsoft 365 connector
prerequisites for broad SaaS activity. Agent 365 S2S observability follows its
own registered-agent export path. Do not enable an unrelated connector or
weaken a control merely to make an Agent 365 query return rows. Confirm the
tenant design and escalate a provisioning discrepancy when necessary.

Similarly, **Defender for AI Services** protects supported Azure AI resources.
Its posture and runtime detections are useful, but enabling it is not a
substitute for Agent 365 observability from this self-hosted agent.

## Investigation workflow

Use this sequence to avoid false conclusions:

1. Confirm `/health` reports Agent 365 `ready`.
2. Generate a metadata-only test invocation and record the UTC window.
3. Confirm `CloudAppEvents` resolves.
4. Search by Agent ID and Agent 365 action type.
5. Inspect one matching row and validate its schema.
6. Correlate trace, action, agent, and sanitized outcome.
7. Check custom detections only after raw activity exists.
8. Check alerts and incidents only after a detection should have fired.
9. Compare the result with Purview and Entra independently.

## Access, licensing, and timing

- Agent 365 observability requires at least one tenant user with Microsoft 365
  E7 or Microsoft Agent 365 assigned. Without it, export can return HTTP 200
  while the service drops telemetry.
- Advanced Hunting requires an appropriate Defender role or delegated
  `ThreatHunting.Read.All` for the repository CLI.
- Alert, incident, and case access can require broader SecOps roles than
  read-only hunting.
- Allow 30 to 90 minutes or longer for downstream indexing. Detections,
  analytics, and cross-product posture views can take longer.

Use least privilege. Do not add a broad administrator role merely to solve a
single missing table or alert.

## Current tenant evidence

Read-only validation on October 14, 2026 established:

| Assertion | Current state |
|---|---|
| Advanced Hunting opens | Verified |
| `CloudAppEvents` schema resolves | Verified |
| `CloudAppEvents` has Agent 365 rows for this agent | Verified; the October 14 controlled run returned 12 exact-Agent-ID rows: eight `InvokeAgent` and four `InferenceCall` |
| Security Dashboard for AI opens | Verified |
| Dashboard inventory totals identify this exact local agent | Not established |
| Approved Agent 365 custom detection exists | Not created; the source rows now exist, but detection intent, query, severity, schedule, and response actions still require approval |
| Defender alert or incident exists for this agent | Not verified |

Tool actions from the controlled run were not visible in the immediate
Defender result even though Purview exposed tool telemetry. Keep tool-action
coverage and alert generation as separate preview-dependent assertions.

## Common mistakes

| Mistake | Correct interpretation |
|---|---|
| "The dashboard shows agents, so my agent is ingested." | Correlate the exact Agent ID. |
| "The table exists, so Agent 365 data is present." | Query for the Agent ID and action types. |
| "HTTP 200 proves Defender accepted the event." | Verify a hunting row. |
| "No alert means no activity." | Alerts require a matching analytic or detection. |
| "Purview has the event, so Defender must have it." | Validate each downstream service independently. |
| "Enable any connector until rows appear." | Confirm the supported data path; do not add unrelated sources. |

## References

- [Agent 365 observability](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/monitor-agents)
- [Detect risky agents](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/detect-risky-agents)
- [CloudAppEvents schema](https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-cloudappevents-table)
- [Advanced Hunting overview](https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-overview)
- [Custom detection rules](https://learn.microsoft.com/en-us/defender-xdr/custom-detection-rules)
- [Create a detection rule with Microsoft Graph beta](https://learn.microsoft.com/en-us/graph/api/security-rulesroot-post-detectionrules?view=graph-rest-beta)
- [Enable Defender Security for AI](https://learn.microsoft.com/en-us/defender-xdr/security-for-ai/get-started-defender-security-for-ai)
- [Defender Security for AI real-time protection](https://learn.microsoft.com/en-us/defender-xdr/security-for-ai/ai-agent-real-time-protection)
- [Agent 365 validation checklist](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/validation-checklist)
