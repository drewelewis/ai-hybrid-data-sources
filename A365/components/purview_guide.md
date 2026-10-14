# Microsoft Purview Guide for Agent 365

## Purpose

This guide maps the major Microsoft Purview surfaces where Agent 365 activity,
sensitive-data risk, policy evaluation, alerts, investigations, and audit
evidence can appear.

Purview has multiple evidence layers:

```text
Agent activity
  -> activity or audit record
  -> policy evaluation
  -> policy match
  -> alert or case
  -> investigation and remediation
```

Evidence at one layer does not prove the next. In particular, zero alerts does
not mean there was no Agent 365 activity.

For end-to-end acceptance, use the
[verification process](../verification_process.md). For content-capture and
privacy rules, use the
[security and privacy guide](../security_and_privacy.md).

## Reference identifiers

| Identifier | Value |
|---|---|
| Tenant ID | `00648bab-6c91-4292-9a2a-2297df511222` |
| Runtime agent name | `TradingPlatformAgent` |
| Agent Identity application ID | `7f2edbcc-8375-4d1d-a430-93c14e8db94e` |
| Blueprint application ID | `341ff526-fa67-4487-a028-5d61dd6e5a92` |
| Service name | `ai-agent-starter-portfolio-manager` |
| Normal content mode | Metadata-only |

Use UTC times and stable IDs. Display names are useful filters but can be
duplicated or changed.

## Product transition

As observed on October 14, 2026, Microsoft Purview presents:

- The new unified **Data Security Posture Management (DSPM)** experience.
- A unified **AI observability** area for cloud and local agents.
- The classic **DSPM for AI** experience and its **Activity explorer** during
  a transition period.

The portal states that classic DSPM and DSPM for AI retire on
**November 30, 2026**. Use unified DSPM as the durable navigation model. Use
the classic Activity Explorer as a transition evidence surface while it
remains available, and revalidate navigation after retirement.

Do not confuse the transition between portal experiences with loss of
underlying activity.

## Major Purview areas at a glance

| Area | What to look for | Evidence type |
|---|---|---|
| DSPM > AI observability | Agent inventory, status, risk level, risk types, sensitive activity trend | Aggregated AI/agent posture |
| DSPM > Posture and Objectives | Sensitive-data posture metrics, remediation objectives, tasks, reports | Governance and remediation |
| DSPM for AI (classic) > Activity explorer | AI interactions, Agent name, activity type, sensitive info, labels | Raw or transformed activity evidence |
| Data Loss Prevention | Policies, policy matches, alerts, investigation details | Data-protection control outcomes |
| Insider Risk Management | Indicators, policy matches, alerts, cases | Insider-risk outcomes |
| Audit | Searchable agent and AI audit events | Independent audit evidence |
| Communication Compliance | Inappropriate or regulated AI interactions | Conduct policy outcomes |
| eDiscovery | Preserved and searchable interaction evidence where supported | Legal and investigation evidence |

## 1. Unified DSPM AI observability

Open [AI observability](https://purview.microsoft.com/dspm/agentobservability).

The current experience provides:

- **Cloud agents** and **Local agents** source tabs.
- Key metrics and risky-interaction categories.
- Risk categories such as **Oversharing**, **Exfiltration**, and
  **Unethical**.
- Filters for name, platform, status, risk level, and risk type.
- A grid with name, platform, status, Agent ID, risk level, risk types, and
  sensitive-activity trend.
- A link to the cross-product
  [Security Dashboard for AI](https://ai.security.microsoft.com).

Search by the exact Agent Identity application ID when possible. If only a
name filter is available, validate the Agent ID in the result before treating
it as the target.

AI observability is an aggregated posture surface. A missing local-agent row
does not by itself prove that raw Agent 365 activity was not ingested. Compare
it with Activity Explorer, Audit, runtime health, and the registered identity.

## 2. Unified DSPM posture and objectives

Open [Data Security Posture Management](https://purview.microsoft.com/dspm/posture).

Use:

- **Posture** for organization-level data security metrics and featured
  insights.
- **Objectives** for defined outcomes, remediation plans, and progress.
- **Discover** and **Classifiers** for sensitive-data discovery context.
- **Tasks and actions** for remediation ownership and status.
- **Reports** for trend and governance reporting.

DSPM unifies AI apps, agents, Microsoft 365 data, non-Microsoft sources, and
partner integrations. Filter and correlate before attributing an aggregate
metric to this agent.

The posture page can show that a control is enabled or an objective has
findings. It does not prove that a particular invocation generated a specific
event.

## 3. Activity Explorer

During the transition, open the classic
[DSPM for AI Activity Explorer](https://purview.microsoft.com/purviewforai/data).

The current AI activity view supports filters including:

- Timestamp.
- Activity type.
- AI app category.
- App and app-access location.
- Agents involved.
- User participant.
- Sensitive information type.
- Web searched.
- Sensitivity label.

Useful result columns include:

- Activity type.
- Timestamp in UTC.
- AI app category and app.
- Agent name.
- User participant.
- Sensitive information type.
- Sensitivity label.

For this implementation, start with:

1. A narrow UTC time window around a known chat.
2. Activity type `Invoke Agent` when available.
3. Agent name `TradingPlatformAgent`.
4. The registered Agent ID if exposed in event details.

Activity Explorer is not real time. Microsoft documents 60 to 90 minutes for
many audit-backed activities, with other services taking longer. It reports a
limited historical window, currently up to 30 days in the general Activity
Explorer experience.

An empty filter dropdown is not conclusive. Filter options can be generated
from only a subset of records. Use a broader filter or Audit when necessary.

## 4. Data Loss Prevention

Use the **Data Loss Prevention** solution for:

- DLP policy configuration and deployment status.
- Policy matches involving supported data locations and activities.
- DLP alerts and matched sensitive information.
- Investigation, tuning, and remediation.

Separate these assertions:

| Assertion | Evidence |
|---|---|
| The agent invoked | Activity Explorer or Audit event |
| Sensitive data was detected | Sensitive information or label details |
| A DLP rule matched | Policy match or rule details |
| An alert was created | DLP alert dashboard |
| A block or warning occurred | Enforcement action and workload evidence |

Agent 365 observability does not automatically make every interaction subject
to every DLP policy. Coverage depends on the supported workload, event type,
policy location, content availability, and licensing.

## 5. Insider Risk Management

Use **Insider Risk Management** for risk indicators, policy matches, alerts,
cases, and investigations that involve supported user and agent activity.

Insider Risk Management has its own role groups. The warning:

> You currently aren't assigned to a role group that allows you to view alerts.

is an authorization warning for Insider Risk alerts. It does not mean that
Agent 365 telemetry is absent from Activity Explorer, Audit, or DLP.

Common role groups include:

- Insider Risk Management.
- Insider Risk Management Analysts.
- Insider Risk Management Investigators.

Role assignment can require propagation and a new portal session. Use least
privilege and do not grant a broad Purview administrator role solely to clear
the warning.

## 6. Audit

Use **Audit** as an independent searchable record of supported Microsoft 365,
Purview, administrative, and AI activities.

Audit is useful when:

- Activity Explorer has not populated yet.
- A filter value is missing.
- An operator needs a broader date, actor, or activity search.
- A configuration or policy change must be attributed.
- Evidence must be exported for a controlled investigation.

Search by UTC range, activity, agent or application identifier, and sanitized
correlation values. Do not export more event content than the investigation
requires.

Audit retention and search features depend on licensing. Non-user application
or service-principal records can have retention behavior different from user
records.

## 7. Communication Compliance and eDiscovery

These are secondary investigation surfaces, not baseline ingestion checks.

- **Communication Compliance** can evaluate supported AI prompts and responses
  for regulatory, conduct, harassment, threat, or sensitive-information
  concerns.
- **eDiscovery** can search, preserve, review, and export supported content for
  legal matters.

Normal operation is metadata-only. Prompt and response text should therefore
be absent unless an explicitly approved, time-bounded nonproduction test set
`A365_RECORD_CONTENT=true` and the downstream feature supports that content.

Never enable full content merely to make a Purview screen more informative.

## Roles and access boundaries

Purview access is solution-specific:

| Task | Typical least-privilege access |
|---|---|
| Review Activity Explorer | Information Protection or Security Reader-related role defined by tenant policy |
| Configure or investigate DLP | DLP/Information Protection role appropriate to the task |
| View Insider Risk alerts | Insider Risk Management Analysts or equivalent |
| Investigate Insider Risk cases | Insider Risk Management Investigators or equivalent |
| Search Audit | Audit Reader or Audit Manager, depending on the action |
| Manage DSPM posture | DSPM/Purview data security role approved by the tenant |

One role does not automatically grant access to every solution. Record the
specific screen, missing action, and required role before requesting access.

## Investigation workflow

1. Confirm the application is healthy and metadata-only.
2. Record the UTC test window, Agent ID, and test category.
3. Search Activity Explorer or Audit for the invocation.
4. Inspect sensitive-information and label context without copying content.
5. Check whether an applicable DLP, communication, or Insider Risk policy
   evaluated the event.
6. Check alerts only after a policy match should have occurred.
7. Review unified AI observability for aggregated agent risk.
8. Compare Defender and Entra independently.

## Current tenant evidence

Read-only validation on October 14, 2026 established:

| Assertion | Current state |
|---|---|
| `Invoke Agent` activity for `TradingPlatformAgent` appears in Activity Explorer | Verified |
| Unified DSPM opens | Verified |
| Unified AI observability opens | Verified |
| Unified AI observability lists this agent as a local agent | Not verified; current local-agent count is zero |
| Metadata-only is the runtime default | Verified |
| Purview policies exist for approved Agent 365 testing | Verified |
| Policy-generated warning, recommendation, or alert exists | Awaiting evaluation/ingestion window |
| Insider Risk alert access is available | Role-dependent; assignment and session propagation must be checked |

Do not treat the unified AI observability local-agent gap as proof that the
verified Activity Explorer events are invalid. Record it as a separate
aggregation or classification question.

## Common mistakes

| Mistake | Correct interpretation |
|---|---|
| "No alerts means no events." | Confirm activity before policy and alert layers. |
| "The Insider Risk warning means Purview is broken." | It identifies a solution-specific role gap. |
| "Metadata-only should show prompts." | Prompt and response content is intentionally suppressed. |
| "Activity Explorer proves Defender ingestion." | Validate Defender independently. |
| "The classic page is the durable navigation path." | Unified DSPM is replacing classic DSPM for AI. |
| "A dashboard total identifies my agent." | Correlate the exact Agent ID. |

## References

- [How Purview supports Agent 365](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/purview-agent-365)
- [Microsoft Purview protections for generative AI](https://learn.microsoft.com/en-us/purview/ai-microsoft-purview)
- [Data Security Posture Management](https://learn.microsoft.com/en-us/purview/data-security-posture-management-learn-about)
- [Activity Explorer](https://learn.microsoft.com/en-us/purview/data-classification-activity-explorer)
- [Data Loss Prevention](https://learn.microsoft.com/en-us/purview/dlp-learn-about-dlp)
- [Insider Risk Management](https://learn.microsoft.com/en-us/purview/insider-risk-management)
- [Microsoft Purview Audit](https://learn.microsoft.com/en-us/purview/audit-solutions-overview)
