# LOB Agent Rollout Strategy

## Status and intent

This document is a **planning reference**, not an approved delivery
commitment. It describes one efficient, risk-based way that a large
multinational bank could roll out the applications in the
[current LOB inventory](../lob/current_lobs.md).

- All dates are relative to a future **Month 0** portfolio authorization.
- A month or wave is a planning window, not an entitlement to enter
  production.
- A later stage starts only after its entry gate is approved, even when that
  changes the indicative sequence.
- No `dev`, `tst`, or `prd` environment, future Agent Identity, regional
  instance, or production approval described here should be treated as
  existing.
- All agent runtimes remain on premises. Azure API Management (APIM),
  Microsoft Foundry models, Microsoft Entra Agent ID, Microsoft Agent 365,
  Microsoft Purview, and Microsoft Defender are governed cloud dependencies,
  not agent hosting locations.

The strategy complements the
[enterprise blueprint guide](./blueprints.md),
[LOB blueprint guidance](./lob_blueprints.md), and
[implementation plan](./implementation_plan.md). Those documents remain
authoritative for technical implementation details.

## Executive recommendation

Run two synchronized workstreams:

1. A **central platform and governance track** builds the repeatable on-premises
   golden path, identity factory, APIM controls, Agent 365 evidence, policy
   baselines, and promotion gates.
2. **LOB application squads** adopt that path in staggered waves. Start no
   more than one or two new LOB squads in a wave until the prior wave has
   produced stable test or production evidence.

Use a relative 24-month horizon:

- Months 0-2: establish the enterprise foundation.
- Months 2-6: promote the two existing Markets applications through controlled
  nonproduction validation.
- Months 4-9: harden and promote the existing Wealth Portfolio Manager.
- Months 6-12: onboard the two Banking applications.
- Months 9-15: onboard the two Services applications.
- Months 12-18: onboard the remaining Wealth and U.S. Personal Banking
  applications.
- Months 18-24: scale approved applications to additional legal entities or
  regions and transition the platform to business-as-usual operation.

This overlap is intentional. Discovery and `local` work for one wave can run
while the preceding wave is in `tst`, but no team bypasses the same gates.
Trade Surveillance and customer-facing use cases should receive longer shadow
or human-review periods even if their initial implementation is technically
simple.

## Planning assumptions

The planning baseline is:

- Ten application families across five LOBs.
- Three applications are currently runnable only in `local`: Markets Risk
  Analyst, Trade Surveillance Analyst, and Wealth Portfolio Manager.
- Seven application folders currently represent prospective use cases rather
  than runnable agents.
- Every persistent application follows `local` -> `dev` -> `tst` -> `prd`.
- Every stage has separate configuration, credentials, Agent Identity,
  telemetry attribution, APIM controls, and approved data access.
- `prd` starts with one approved operating region or legal entity. Additional
  production instances are created only where business, regulatory, residency,
  resilience, or operational requirements justify them.
- Business sponsors, technical owners, model-risk reviewers, data owners,
  security, privacy, compliance, and production operations retain their normal
  accountabilities. Agent 365 registration does not replace those approvals.

In this strategy, an **instance** means a separately governed deployment of an
application family, such as `markets-risk-analyst-prd-emea`. Horizontal
replicas that share one owner, policy boundary, data boundary, and lifecycle
are one logical instance for portfolio planning.

## Design principles

1. **Business value before scale.** Every agent needs a measurable problem,
   accountable sponsor, expected benefit, and stop condition before it enters
   `dev`.
2. **One path to production.** Teams use the same repository template,
   promotion evidence, APIM gateway, identity process, telemetry schema,
   release pipeline, and operational controls.
3. **Unique identity, bounded trust.** Provision a distinct Agent Identity for
   every governed application-stage-instance boundary. Reuse a blueprint only
   where purpose, sponsor, credential boundary, inherited permissions, and
   security posture genuinely match.
4. **No global big bang.** Prove one operating region or legal entity, then
   repeat the evidence-based rollout for the next boundary.
5. **Safe initial capability.** Start model-only or read-only, with synthetic
   or masked data and human review. Add write actions, customer decisions,
   trade actions, fund movement, or case disposition only through a separate
   control approval.
6. **APIM is the model gateway.** On-premises agents do not receive a direct
   Foundry endpoint fallback. APIM centralizes authentication, routing,
   quotas, token limits, observability, and cost controls.
7. **Metadata-first observability.** Begin with approved metadata-only
   telemetry. Content capture requires a documented purpose, classification,
   retention rule, regional review, and access model.
8. **Evidence, not attendance, opens a gate.** Passing a target month does not
   compensate for missing security, risk, compliance, telemetry, resilience,
   or business evidence.
9. **Automate repeatable controls, not approvals.** Use approved automation for
   templates, identities, configuration, tests, policy checks, and evidence
   collection. Human accountability and independent review remain explicit.

## Risk-based application sequencing

Use two dimensions when setting a final risk tier:

- **Capability risk:** model-only, read-only retrieval, or state-changing
  action.
- **Business sensitivity:** internal productivity, regulated surveillance,
  confidential financial data, customer communication, eligibility or credit
  influence, or monetary impact.

A model-only agent is not automatically low risk. For example, Trade
Surveillance can influence a regulated investigation even without changing a
system of record.

| Initial tier | Starting capability | Minimum rollout posture |
|---|---|---|
| Tier 1 | Model-only and no business-system tools | Synthetic data, bounded prompt, APIM limits, telemetry, human review |
| Tier 2 | Read-only access to approved internal data | Tier 1 plus data-owner approval, authorization tests, privacy review, retrieval evaluation, and leakage tests |
| Tier 3 | Write action, customer outcome, regulated disposition, fund/trade action, or other material decision support | Tier 2 plus independent validation, transaction safeguards, segregation of duties, stronger rollback, extended shadow operation, and explicit executive risk acceptance |

The tier must be reassessed whenever tools, data sources, model, prompt,
permissions, geography, or intended use changes.

## Blueprint and Agent Identity topology

### Object model

| Object | Planning unit | Default rule |
|---|---|---|
| Application family | One stable business use case and codebase | Treat each of the ten inventory entries as a separate family until a boundary review proves reuse is safe |
| Agent Identity Blueprint | Shared credential and inheritable-policy trust boundary | Normally one per approved application family; split when production or regional trust boundaries differ |
| Agent Identity | One governed application-stage-instance | Unique for every persistent `local`, `dev`, `tst`, and `prd` instance |
| On-premises runtime | The deployed process or service | Uses only its stage and instance identity and configuration |
| APIM product/subscription | Model-access and cost-control boundary | Separate by application and stage from `dev` onward; split production further where regional ownership requires it |
| Agent 365 inventory record | Governance and observability attribution | Match the unique Agent Identity and carry LOB, stage, owner, sponsor, data class, and region metadata |

Microsoft recommends planning blueprints before deployment, assigning sponsors
and owners, applying blueprint-level controls, and creating a unique identity
for each agent instance. This strategy applies those principles without
assuming that one LOB is one blueprint.

### Capacity-planning formula

If every application has one persistent instance in every stage, the initial
planning baseline is:

```text
10 application families x 4 stages = 40 Agent Identities
```

This is a capacity estimate, not a target to pre-create. Identities are created
only as a stage is approved.

Regional and legal-entity expansion is calculated as:

```text
Total identities =
  sum of governed instances for every application and stage

Additional identities =
  sum of approved regional, legal-entity, or independently operated instances
  beyond the first instance of that application and stage
```

Blueprint count is not derived from the identity count. It equals the number
of distinct credential, inherited-permission, ownership, and kill-switch trust
boundaries across the approved application families.

### Candidate family map

These are planning names. They do not prove that a blueprint or identity
exists.

| LOB | Application family | Candidate blueprint | Identity pattern | Indicative wave |
|---|---|---|---|---|
| Markets | Markets Risk Analyst | `markets-risk-analyst-nonprod`; `markets-risk-analyst-prd` | `markets-risk-analyst-<stage>[-<geo>]` | 1 |
| Markets | Trade Surveillance Analyst | `markets-trade-surveillance` | `markets-trade-surveillance-<stage>[-<geo>]` | 1 |
| Wealth | Portfolio Manager | Existing `trading-platform-agent` | `trading-platform-agent-<stage>[-<geo>]` | 2 |
| Banking | Corporate Credit Memo Analyst | `banking-corporate-credit-memo` | `banking-corporate-credit-memo-<stage>[-<geo>]` | 3 |
| Banking | Deal Diligence Coordinator | `banking-deal-diligence-coordinator` | `banking-deal-diligence-coordinator-<stage>[-<geo>]` | 3 |
| Services | Treasury Liquidity Manager | `services-treasury-liquidity-manager` | `services-treasury-liquidity-manager-<stage>[-<geo>]` | 4 |
| Services | Trade Finance Operations | `services-trade-finance-operations` | `services-trade-finance-operations-<stage>[-<geo>]` | 4 |
| Wealth | Client Advisor | `wealth-client-advisor` | `wealth-client-advisor-<stage>[-<geo>]` | 5 |
| U.S. Personal Banking | Mortgage Servicing Assistant | `uspb-mortgage-servicing-assistant` | `uspb-mortgage-servicing-assistant-<stage>[-<geo>]` | 5 |
| U.S. Personal Banking | Card Dispute Assistant | `uspb-card-dispute-assistant` | `uspb-card-dispute-assistant-<stage>[-<geo>]` | 5 |

The Markets Risk Analyst implements its proposed nonproduction and production
boundaries as non-secret
[desired-state artifacts](../lob/markets/markets-risk-analyst/identities/README.md).
Its instance overlays separate stage from deployment instance, support names
such as `markets-risk-analyst-prd-emea`, and carry independently promoted
lifecycle state. Its closed blueprint schema and renderer require blueprint
readiness before an identity can enable provisioning. All included artifacts
remain provisioning-disabled and do not indicate that tenant objects or
later-stage environments exist.

The existing `trading-platform-agent-local-dev` identity remains the
grandfathered `local` Portfolio Manager identity. It must not be renamed or
reused as the future `dev` identity without a separately approved tenant
migration. Future Portfolio Manager stages use
`trading-platform-agent-dev`, `trading-platform-agent-tst`, and
`trading-platform-agent-prd`.

### When to split a blueprint

Create a separate production or regional blueprint when any of these cannot
remain in one credential and inherited-permission boundary:

- legal entity, sponsor, technical owner, or incident commander;
- production versus nonproduction credential isolation;
- data residency, classification, retention, or secrecy requirements;
- API permissions or downstream system authorization;
- Conditional Access, network, or authentication policy;
- publisher, verified organization, or regulatory accountability;
- regional kill-switch or credential-rotation independence.

Otherwise, keep one family blueprint and create separate Agent Identities
under it. Do not create one blueprint per developer or one broad blueprint for
an entire LOB merely to simplify counting.

For on-premises production, use an approved workload-federation or
certificate-based pattern where supported. Store private key material in the
bank's approved HSM or secret-management service. Client secrets and shared
subscription keys are transitional development mechanisms, not a production
credential strategy.

## Environment model and promotion gates

### Stage posture

| Stage | Purpose | Data and users | Identity and credentials | Required exit evidence |
|---|---|---|---|---|
| `local` | Build, unit test, and explore a bounded use case | Synthetic or explicitly approved developer data; named developers | Local Agent Identity or approved development mechanism; workstation secret store; least privilege | Business owner, initial risk tier, threat and data-flow review, unit/evaluation results, no direct model endpoint, and proposed blueprint boundary |
| `dev` | Shared integration and control validation | Synthetic, masked, or approved nonproduction data; LOB squad | Separate `-dev` Agent Identity, application-stage APIM subscription, nonproduction downstream access | Integration, authorization, prompt-injection, content-safety, APIM limit, cost, telemetry, and recovery evidence |
| `tst` | Independent, production-like assurance | Representative nonproduction data; independent testers, model risk, security, privacy, and compliance | Separate `-tst` identity and credentials; production-like policies with no production data entitlement by default | End-to-end, adversarial, performance, resilience, failover, human-review, Purview, Defender, Entra, and operational acceptance evidence |
| `prd` | Controlled business operation | Approved production data and authorized users in one approved boundary | Separate `-prd` identity; certificate or federation where supported; production APIM product/subscription; monitored secret rotation | Formal go-live approvals, release-ring plan, rollback rehearsal, support readiness, residual-risk acceptance, and 30/60/90-day review schedule |

Do not copy a developer `.env` file into `dev`, `tst`, or `prd`. Promote an
immutable application artifact and bind approved stage configuration and
credentials at deployment time.

### Gate A: portfolio intake to `local`

- Name the business problem, affected decisions, expected benefit, and
  explicit non-goals.
- Assign a business sponsor, product owner, technical owner, data owner, and
  operational owner.
- Classify data, users, geographies, downstream systems, and potential harms.
- Set a provisional risk tier and determine whether the use case is allowed.
- Define human review and prohibited autonomous actions.
- Register the application in the portfolio backlog; do not create production
  identities or permissions.

### Gate B: `local` to `dev`

- Approve the blueprint boundary, sponsor, owner, metadata, and proposed
  Agent Identity name.
- Prove APIM-only model access and create an application-stage APIM
  subscription with explicit token, request, concurrency, and spend limits.
- Complete threat modeling, privacy screening, architecture review, dependency
  scanning, and least-privilege permission design.
- Establish quality, safety, latency, cost, and business-value baselines.
- Confirm telemetry can be attributed to the application, stage, Agent
  Identity, user or workload context, and correlation ID.

### Gate C: `dev` to `tst`

- Provision the distinct `-tst` Agent Identity and independently controlled
  credentials.
- Freeze the release candidate and complete software supply-chain evidence.
- Use production-like APIM, network, Conditional Access, authorization, and
  telemetry policies without granting production data by default.
- Run repeatable functional, adversarial, privacy, data-leakage, prompt
  injection, authorization, load, quota, failure, and rollback tests.
- Demonstrate expected records in Entra, Purview, and Defender. Raw activity
  is evidence of telemetry, not proof that a policy must create an alert.
- Confirm support, incident, evidence-preservation, and disablement procedures.

### Gate D: `tst` to `prd`

- Obtain business, technology, security, model-risk, data-owner, privacy,
  compliance, records, and regional or legal-entity approvals applicable to
  the use case.
- Resolve all critical and high-risk findings or record an approved exception
  with an owner and expiry.
- Use a production Agent Identity and production-grade credential boundary.
- Rehearse four containment actions: stop the on-premises service, disable the
  instance identity, revoke the APIM subscription, and use the blueprint
  kill-switch when the whole family must stop.
- Approve release rings, service objectives, capacity, business continuity,
  disaster recovery, customer or employee communications, and rollback.
- Validate that human reviewers can reject, correct, and escalate agent output
  without being pressured to accept it.

### Gate E: production expansion

After go-live, hold 30-, 60-, and 90-day reviews. Expand users, tools, data,
regions, or legal entities only when:

- quality, safety, latency, availability, cost, and business-value targets are
  stable;
- override, complaint, escalation, policy violation, and incident trends are
  understood;
- permissions and data access remain least-privilege;
- telemetry coverage and alert operations meet target;
- the sponsor and owner reconfirm the use case and residual risk.

Any material change to model, prompts, tools, permissions, data, autonomy, or
geography returns to the appropriate earlier gate.

## Indicative 24-month rollout

| Window | Platform and governance track | Application track | Exit outcome |
|---|---|---|---|
| Months 0-2 | Establish the Agent Platform Office; approve taxonomy, risk tiers, stage gates, reference architecture, identity workflow, APIM product model, telemetry schema, evidence pack, release template, and regional decision process | Reconfirm the ten-use-case inventory, sponsors, owners, benefits, and prohibited actions | One approved golden path and prioritized portfolio; no implied production launch |
| Months 2-4 | Automate nonproduction onboarding, policy checks, evaluation packs, identity requests, APIM subscriptions, and Agent 365 evidence capture | Move Markets Risk Analyst and Trade Surveillance Analyst from current `local` baselines into separate `dev` identities and subscriptions | Repeatable `dev` evidence and remediation backlog |
| Months 4-6 | Exercise incident response, cost controls, kill-switches, and production-readiness review | Promote both Markets agents to `tst`; consider a small internal `prd` ring for Markets Risk only if all gates pass; keep Trade Surveillance in shadow mode until compliance evidence is sufficient | First end-to-end gate evidence; no automatic right to production |
| Months 4-9 | Refine tool authorization, OBO or workload flows, secrets, and production operations from Wave 1 learning | Harden Wealth Portfolio Manager, begin read-only, isolate write-capable tools, and progress `local` -> `dev` -> `tst`; add a limited `prd` ring only after tool and data controls pass | First data-connected family operating under the golden path |
| Months 6-12 | Add reusable document-ingestion, provenance, citation, and decision-support evaluations | Build and stage Corporate Credit Memo Analyst and Deal Diligence Coordinator; keep human bankers accountable for conclusions and credit decisions | Banking decision-support evidence with no autonomous approval authority |
| Months 9-15 | Add document-integrity, multilingual, regional-records, and operational-resilience controls | Build and stage Treasury Liquidity Manager and Trade Finance Operations; prohibit document release, fund movement, or payment instruction execution in the initial scope | Services evidence with segregated human authorization |
| Months 12-18 | Add customer-communication, fairness, accessibility, complaint, and conduct-risk evaluations | Stage Client Advisor, Mortgage Servicing Assistant, and Card Dispute Assistant; use shadow and assisted modes before any customer-impacting action | Customer-facing evidence and independent conduct review |
| Months 18-24 | Optimize quotas and cost, complete control automation, formalize quarterly access reviews, and transfer service ownership to business-as-usual teams | Expand only approved families to additional regions or legal entities using separate identities and, where required, separate blueprints | Controlled multinational scale rather than a global big-bang release |

### Application-specific starting constraints

| Application | First useful production mode | Capability held back for a later approval |
|---|---|---|
| Markets Risk Analyst | Internal analysis of approved user-provided risk context with human review | Trading, limit changes, or autonomous risk acceptance |
| Trade Surveillance Analyst | Shadow-mode hypothesis generation for trained compliance reviewers | Accusation, case disposition, employee action, or evasion guidance |
| Portfolio Manager | Read-only portfolio briefing for authorized users | New write tools, trade execution, or fund movement |
| Corporate Credit Memo Analyst | Drafting and evidence collation for a credit professional | Credit decision, limit approval, pricing, or customer notification |
| Deal Diligence Coordinator | Source-cited review and request tracking for a deal team | Autonomous recommendation, approval, or external communication |
| Treasury Liquidity Manager | Read-only scenarios and explanations | Fund transfer, hedge, booking, or limit change |
| Trade Finance Operations | Exception suggestions with document provenance | Document acceptance, sanction override, release, or payment instruction |
| Client Advisor | Internal preparation using approved client data | Unreviewed client advice, transaction, or suitability determination |
| Mortgage Servicing Assistant | Servicing explanations and human handoff | Account change, hardship decision, foreclosure action, or customer commitment |
| Card Dispute Assistant | Case summarization and routing recommendation | Automated refund, denial, fraud accusation, or case closure |

## Multinational instance strategy

### Shared or separate instance decision

Use one centrally operated production instance only when all of these are
common:

- accountable legal entity, sponsor, owner, and incident command;
- permitted data location, transfer, retention, and records policy;
- APIM and model route, authentication, network, and secret boundary;
- downstream permissions and data sources;
- language, evaluation set, customer or employee population, and intended use;
- service objective, support hours, continuity, and recovery design.

Create a separate regional or legal-entity instance when any item differs
materially. Give it a unique Agent Identity and APIM subscription. Split the
blueprint as well when the credential, inherited permissions, sponsor,
publisher, or broad kill-switch must be independent.

Examples:

```text
markets-risk-analyst-prd-emea
markets-risk-analyst-prd-na
services-trade-finance-document-checker-prd-apac
```

Use approved nonconfidential codes. Do not embed customer, transaction, or
project-sensitive information in identity names.

### Regional rollout order

1. Prove one anchor legal entity and operating region.
2. Add a second region with the same use, language, and control model.
3. Add new legal entities only after local data, privacy, employment,
   financial-services, records, and model-risk obligations are mapped.
4. Revalidate prompts and evaluations for every new language and material
   market context.
5. Treat an independently activatable disaster-recovery deployment as a
   separate instance when it has its own credential, network, or operations
   boundary.

The control review should address cross-border data transfer, residency,
localization, retention, banking secrecy, sanctions, employee monitoring,
works-council obligations, customer disclosure, operational resilience, and
regulatory access as applicable. Local counsel and compliance determine the
actual obligations.

## Central platform and federated LOB operating model

| Role | Enterprise responsibility | LOB or regional responsibility |
|---|---|---|
| Agent Platform Office | Golden path, reference architecture, common libraries, APIM pattern, Agent 365 schema, release tooling, portfolio standards | Adoption feedback and exception requests |
| Identity and access management | Blueprint and Agent Identity process, Conditional Access, custom attributes, credential standards, access reviews | Sponsor and owner confirmation, business permissions, regional entitlement approval |
| Cybersecurity and privacy | Threat model, security baseline, red-team standards, incident integration, privacy control framework | Use-case-specific data flow, mitigations, and local obligations |
| Model risk and responsible AI | Tiering, independent validation standard, evaluation methodology, material-change policy | Business-specific harms, thresholds, human review, residual-risk acceptance |
| LOB product squad | Shared engineering template and coaching from the platform | Product outcome, prompts, tools, tests, data, user experience, documentation, and remediation |
| SRE and operations | Common dashboards, alert routing, service-management integration, resilience pattern | Production runbook, on-call ownership, capacity, recovery, and business continuity |
| Audit and compliance | Evidence standard, independent challenge, portfolio reporting | Regulatory interpretation, surveillance or conduct controls, and legal-entity approval |

The platform team should not become the business owner. LOB teams should not
fork the enterprise control path without an approved exception.

## APIM, credential, and cost-control model

The current shared local APIM subscription key is a bootstrap convenience for
developer setup only. It should not be promoted or copied into `dev`, `tst`,
or `prd`.

From `dev` onward:

- issue an application-and-stage-specific APIM subscription or equivalent
  approved credential;
- use distinct production credentials and split them further by region or
  legal entity where incident containment or attribution requires it;
- require Entra authentication in addition to the subscription mechanism
  where the approved gateway design supports both;
- use APIM token-limit, rate-limit, quota, request-size, timeout, and routing
  policies appropriate to the risk tier;
- set per-application budgets, alerts, dashboards, and owner tags;
- route only to approved model deployments and API versions;
- redact secrets and prohibited content from gateway and application logs;
- test `401`, `403`, `429`, timeout, upstream failure, exhausted quota, and
  key or certificate rotation behavior;
- revoke the narrowest subscription or identity during an incident before
  using a family-wide kill-switch.

Use measured tokens, requests, latency, cache behavior, and business volume
for capacity planning. Do not grant unlimited quota merely to avoid tuning.

## Agent 365, Entra, Purview, and Defender controls

Every stage should emit enough metadata to answer:

- Which application, version, stage, region, blueprint, and Agent Identity ran?
- Which user or workload initiated the interaction?
- Which model, APIM route, tool, and governed data source were used?
- Which policy decision, error, denial, escalation, or human override occurred?
- Can an operator correlate the on-premises log, APIM request, Entra sign-in,
  Purview activity, and Defender event without recording prohibited content?

Minimum controls include:

- Entra custom security attributes for LOB, environment, data sensitivity,
  region, and risk tier;
- agent-specific Conditional Access and least-privilege permission reviews;
- sponsor and owner recertification at least quarterly for production;
- metadata-only OpenTelemetry by default, with approved retention and access;
- stage-specific Purview, Defender, and Entra dashboards and alert routing;
- safe adversarial verification for prompt injection, data exfiltration,
  unauthorized tool use, policy evasion, and identity misuse;
- a documented distinction between activity, policy matches, incidents, and
  alerts so teams do not treat the absence of an alert as absence of activity;
- evidence that disabling an identity, revoking APIM access, or stopping the
  on-premises runtime produces the expected containment.

## Evidence pack and efficiency mechanisms

### Reusable evidence pack

Each gate should update one versioned evidence pack rather than create
unrelated documents:

- business case, sponsor, owner, users, value metric, risk tier, and non-goals;
- architecture, data flow, blueprint boundary, identities, permissions, APIM
  product, downstream systems, and regional scope;
- threat model, privacy assessment, model-risk assessment, control mapping,
  residual risks, and exceptions with expiry;
- functional, safety, quality, adversarial, authorization, performance, cost,
  resilience, and rollback results;
- Entra, Purview, Defender, APIM, and on-premises observability evidence;
- release, support, incident, continuity, recovery, retirement, and
  communication runbooks;
- approval record and exact artifact/configuration versions promoted.

### Golden-path automation

Implement this section through the
[Agent 365 DevOps and GitOps guide](./devops.md), which defines the
source-of-truth, tool-selection, plan/apply, approval, evidence, drift, and
rollback model.

Automate:

- repository scaffolding, dependency and secret scanning, and signed builds;
- supported blueprint and identity requests with owner and sponsor metadata;
- APIM product/subscription creation and standard policy attachment;
- environment configuration validation and prohibited direct-endpoint checks;
- evaluation datasets, test execution, policy assertions, and evidence
  collection;
- inventory synchronization, access-review reminders, credential expiry, and
  telemetry coverage checks;
- deployment, health verification, rollback, and retirement workflows.

Do not replace supported Agent ID creation channels with generic application
registration commands. Keep segregation of duties so the application author
cannot self-approve production identity, data access, model risk, and release.

### Portfolio flow controls

- Limit work in progress: at most two new LOB squads enter the path before the
  prior cohort demonstrates stable `tst` evidence.
- Reuse controls, not risk decisions: a passed APIM or identity pattern can be
  reused, but every use case retains its own data, harm, and business review.
- Time-box remediation and retire low-value pilots instead of carrying them
  indefinitely.
- Prefer a common release train and evidence format while allowing a high-risk
  agent to remain in shadow mode longer.
- Measure queue time at each approval gate and improve the platform where the
  same evidence is repeatedly requested.

## Metrics and stop/go criteria

| Dimension | Example measures |
|---|---|
| Delivery | Lead time by stage, gate queue time, first-pass evidence acceptance, automation coverage, open exception age |
| Quality and safety | Task success, groundedness, citation validity, harmful-output rate, leakage rate, adversarial pass rate, human correction rate |
| Identity and security | Unique identity coverage, least-privilege exceptions, risky sign-ins, blocked attempts, credential age, access-review completion |
| Operations | Availability, latency, error and `429` rates, recovery time, rollback success, alert acknowledgement, telemetry completeness |
| Cost | Tokens and cost per task, budget variance, unused capacity, cache benefit, cost by application-stage-region |
| Business | Time saved, throughput, user adoption, avoided loss, service quality, reviewer acceptance, validated financial or control benefit |
| Conduct and customer impact | Overrides, complaints, escalations, disparate outcomes, unsuitable output, adverse-action or disclosure defects |

Pause promotion or reduce the release ring when any applicable threshold is
breached, including:

- unauthorized data or tool access;
- missing identity attribution or material telemetry gaps;
- uncontained critical or high security findings;
- harmful, discriminatory, misleading, or unsupported output above tolerance;
- APIM bypass, uncontrolled spend, or repeated quota instability;
- absent sponsor, owner, support coverage, or required approval;
- rollback, kill-switch, recovery, or evidence-preservation failure;
- benefit below the agreed continuation threshold.

## Rollback, retirement, and lifecycle control

Use the narrowest effective control:

1. Remove users or reduce the production release ring.
2. Stop the on-premises deployment.
3. Revoke the application-instance APIM subscription.
4. Disable the affected Agent Identity.
5. Disable the blueprint only when every child identity in the family must
   stop.

Preserve required evidence before destructive cleanup, rotate exposed
credentials, revoke downstream permissions, and notify owners and incident
teams. Retirement is complete only when the runtime is removed, identities and
permissions are disabled or deleted under policy, APIM access is revoked,
inventory is updated, retention obligations are satisfied, and ownership is
closed.

## Decisions required before Month 0

The bank must still decide:

- the executive sponsor and funding model for the Agent Platform Office;
- final risk tiers and which use cases are prohibited or require regulator
  engagement;
- approved on-premises federation, certificate, HSM, and secret-management
  patterns;
- tenant, APIM, model-deployment, logging, and data-residency topology;
- production availability, recovery, retention, and evidence standards;
- required independent validators and approval authorities by tier and region;
- portfolio value thresholds and the maximum number of concurrent waves.

## Official guidance used

- [Best practices for Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/best-practices-agent-id)
- [Govern local Agent 365 agents](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/govern-local-agents)
- [Plan for AI adoption with the Cloud Adoption Framework](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai/plan)
- [Manage AI workloads with the Cloud Adoption Framework](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai/manage)
- [Azure API Management AI gateway capabilities](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities)
- [Azure API Management LLM token-limit policy](https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy)
- [Security and Responsible AI guidance](https://azure.github.io/Security-and-Responsible-AI-Guide/)
- [AI in Production Guide: deployment strategies](https://microsoft.github.io/AI-in-Production-Guide/chapters/ai_system_deployment/deployment_strategies.html)

Guidance reviewed: October 16, 2026.
