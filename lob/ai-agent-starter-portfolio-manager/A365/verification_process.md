# Verify and Start Using the Agent 365 Integration

## What this process verifies

This is an operator acceptance process, not a developer unit-test checklist.
It answers four practical questions:

1. Can a user start and use the Trading Platform Agent?
2. Is the running agent using its registered Microsoft Entra Agent Identity?
3. Does Agent 365 receive and display the agent's activity?
4. Which Agent 365 capabilities work now, and which require more integration?

The process uses **ARRANGE, ACT, ASSERT** throughout.

## Deployed Agent 365 objects

Use these values when searching portals:

| Object | Deployed value |
|---|---|
| Tenant | `00648bab-6c91-4292-9a2a-2297df511222` |
| Blueprint | `trading-platform-agent Blueprint` |
| Blueprint application ID | `341ff526-fa67-4487-a028-5d61dd6e5a92` |
| Local Agent Identity | `trading-platform-agent-local-dev` |
| Agent Identity application ID | `7f2edbcc-8375-4d1d-a430-93c14e8db94e` |
| Runtime agent name | `TradingPlatformAgent` |
| Service name | `ai-agent-starter-portfolio-manager` |
| Channel | `local-cli` |

Never place secrets, tokens, device codes, raw prompts, responses, account
records, or trade data in screenshots or verification notes.

## Recommended acceptance path

For the fastest end-to-end confirmation, perform these scenarios in order:

1. Start the deployed application.
2. Use the real interactive client.
3. Generate several recognizable agent runs.
4. Find the registered identity in Microsoft 365 Admin Center.
5. Find the generated activity on its **Activity** tab.
6. Find the security events in Microsoft Defender.
7. Review the capability matrix so preview or unimplemented features are not
   mistaken for failures.

Allow at least 5-15 minutes for portal ingestion before declaring telemetry
missing.

---

## Scenario 1: Start the deployed application

### ARRANGE

Open PowerShell and go to the application:

```powershell
Set-Location C:\gitrepos\ai-hybrid-data-sources\lob\ai-agent-starter-portfolio-manager
```

Confirm Docker Desktop is running. The existing Git-ignored `.env` must
contain the model, APIM, database, and Agent 365 settings already configured
for this environment.

### ACT

Start the complete local stack:

```powershell
docker compose up -d
docker compose ps
```

Then query health:

```powershell
$health = Invoke-RestMethod http://127.0.0.1:8989/health
$health | ConvertTo-Json -Depth 4
```

### ASSERT

The three containers are running, and health reports:

```text
status: healthy
agent: ready
database: connected
a365_observability.enabled: true
a365_observability.state: ready
a365_observability.token_ready: true
a365_observability.content_recording: false
```

`state: ready` proves that the running application completed the two-step
Agent ID token exchange. It does not yet prove that Agent 365 displayed the
activity; that is verified later.

The runtime refreshes the Agent 365 token in the background before it expires.
After a long idle period, health should therefore remain `ready`. A
`degraded` state with `last_error: null` can indicate an older container that
predates background refresh; rebuild and recreate the API service.

If health reports `degraded`, inspect:

```powershell
docker compose logs --tail 100 ai-agent-starter-api
```

Do not continue until the API, database, and A365 state are understood.

---

## Scenario 2: Start using the agent as a user

### ARRANGE

Use the supported interactive client. Be ready to complete Microsoft
device-code sign-in if no cached user session is available.

Use test questions that exercise distinct capabilities without changing
portfolio data:

| Capability | Suggested question |
|---|---|
| Model response | `What can you help me with?` |
| Database tool | `List all accounts.` |
| Price lookup | `What is the latest price for MSFT?` |
| Trade lookup | `Show BUY trades for an account.` |
| Cross-account analysis | `Which accounts have the largest positions?` |
| Conversation continuity | Ask a follow-up about the previous result |

Do not test `insert_trade_event` unless a data-changing test is separately
approved.

### ACT

Run:

```powershell
.\.venv\Scripts\python.exe chat.py
```

Complete sign-in, then submit at least three suggested questions. Use:

```text
status
clear
quit
```

to verify client status, start a fresh conversation, and exit.

Record only:

- UTC start and finish time;
- the categories of questions tested;
- whether each response succeeded; and
- the session identifier if it contains no user or portfolio data.

### ASSERT

- The client connects to `http://127.0.0.1:8989`.
- Microsoft sign-in succeeds.
- The agent returns non-empty answers.
- Database-backed questions return data rather than fabricated answers.
- A follow-up question uses conversational context.
- `clear` starts a new conversation.
- No telemetry error interrupts the user experience.

At this point the agent application is working. The next scenarios prove that
the Agent 365 integration is working.

---

## Scenario 3: Generate recognizable Agent 365 activity

### ARRANGE

Choose a unique test window and record its UTC start time:

```powershell
$verificationStart = (Get-Date).ToUniversalTime()
$verificationStart
```

Start a new client session with `clear`.

### ACT

Run this sequence through `chat.py`:

1. `What is the latest price for MSFT?`
2. `List all accounts.`
3. `Which accounts have the largest positions?`
4. Ask one follow-up about the third result.

These runs should create:

- conversational sessions;
- `invoke_agent` operations;
- model calls;
- tool calls;
- database dependencies; and
- successful completion status.

Optionally generate one safe authentication failure to test exception
reporting:

```powershell
$body = @{
    session_id = "a365-unauthorized-verification"
    message = "health verification"
} | ConvertTo-Json

try {
    Invoke-RestMethod `
        -Uri http://127.0.0.1:8989/chat `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
} catch {
    $_.Exception.Response.StatusCode.value__
}
```

The expected result is HTTP `401`; do not supply a fake token.

Wait for batch export and portal ingestion:

```powershell
Start-Sleep -Seconds 15
```

### ASSERT

Recent application logs contain successful `/chat` requests:

```powershell
docker compose logs --since 15m ai-agent-starter-api
```

The logs must not contain:

```text
No token resolved
dropping chunk
telemetry authentication failed
unexpected audience
subject does not match
export failed
```

The optional unauthenticated test returns `401` and does not affect subsequent
authenticated chat.

---

## Scenario 4: Verify inventory in Microsoft 365 Admin Center

### ARRANGE

Sign in to [Microsoft 365 Admin Center](https://admin.microsoft.com/) with an
account that can view the Agent Registry.

Have the deployed name and ID available:

```text
trading-platform-agent-local-dev
7f2edbcc-8375-4d1d-a430-93c14e8db94e
```

### ACT

1. Go to **Agents** > **All agents**.
2. Select the **Registry** tab.
3. Search for the name or Agent Identity application ID.
4. Open the agent details pane.
5. Review the available **Details**, **Data & Tools**, **Security**,
   **Permissions**, and **Activity** tabs.

Tabs vary by agent capability, so not every tab is guaranteed to appear.

### ASSERT

- The local-development agent appears in the Registry.
- Its identity is
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`.
- It is associated with the expected Trading Platform blueprint.
- The expected sponsor/owner is present.
- No unexpected Microsoft 365 data permissions are listed.
- No mail, Teams, SharePoint, Files, Work IQ, or broad Graph data access was
  granted.
- The agent is not confused with the provisioning application named
  `Agent 365 CLI`.

The presence of **Install**, **Block**, **Uninstall**, or **Pin for users**
actions does not mean this local CLI agent is a Teams or Microsoft 365 app.
The current implementation has no Teams/Microsoft 365 channel package or
hosted interaction endpoint.

---

## Scenario 5: Verify the Activity experience

### ARRANGE

Remain in the registered agent's details pane. Use the UTC window recorded in
Scenario 3. Allow 5-15 minutes for ingestion and refresh the page.

### ACT

Open the **Activity** tab and select a time range that includes the test.
Inspect:

- sessions or runs;
- invocation count;
- runtime or duration;
- completion status;
- exceptions;
- model activity;
- tool activity; and
- trace relationships where exposed.

### ASSERT

- Activity appears for the registered agent after the test run.
- The activity time matches the recorded UTC window.
- Successful prompts appear as completed agent runs.
- The optional unauthorized request appears as a failed run or exception if
  that operation is represented by the current preview.
- Activity is attributed to
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`, not to a random runtime-generated
  agent ID.
- The raw question, answer, account data, tool arguments, tool results, and
  SQL are absent.
- Operational metadata such as status, duration, operation, model/tool
  category, and trace identifiers can be present.

If the agent appears in Registry but **Activity** is empty:

1. wait for ingestion and refresh;
2. confirm `/health` still reports A365 `ready`;
3. inspect recent API logs for dropped chunks;
4. confirm at least one tenant user has a Microsoft 365 E7 or Microsoft Agent
   365 license assigned;
5. confirm the viewer has permission to see agent activity; and
6. verify the runtime Agent Identity matches the registry entry.

A `200` response from an exporter is not by itself proof of ingestion; the
Activity record is the end-to-end assertion.

---

## Scenario 6: Verify security activity in Microsoft Defender

### ARRANGE

Sign in to [Microsoft Defender](https://security.microsoft.com/) with access
to **Advanced Hunting**.

### ACT

Run:

```kusto
let agentIdToFind = "7f2edbcc-8375-4d1d-a430-93c14e8db94e";
CloudAppEvents
| where Timestamp > ago(1d)
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
| project Timestamp, ActionType, AgentId, TargetAgentId,
    PlatformTargetAgentId, data
| order by Timestamp desc
```

Filter the results to the Scenario 3 UTC window.

### ASSERT

- At least one `InvokeAgent` event appears.
- Model and tool events appear when the current instrumentation and Defender
  schema expose them.
- Events identify the registered Agent Identity.
- Success and failure status align with the tests performed.
- No prompt, response, trade record, account ID, SQL, credential, or token is
  present.

Defender schema and action coverage can change during preview. If the Registry
Activity tab works but this query is empty, verify licensing, permissions,
table availability, and the current Microsoft schema before changing the
application.

Agent 365 onboarding documentation does not list the Microsoft 365 Activities
app connector as a prerequisite for Agent 365 spans. It says an assigned
Microsoft Agent 365 or Microsoft 365 E7 license enables the observability
routing, while the Microsoft OpenTelemetry Distro documentation separately
requires Defender Advanced Hunting to have access to the `CloudAppEvents`
table. Generic Defender for Cloud Apps documentation describes the Microsoft
365 connector for its broader Microsoft 365 activity feed; that is not proof
that the connector is required for Agent 365 telemetry.

If even `CloudAppEvents | take 1` fails because the table cannot be resolved,
classify the Defender assertion as blocked by tenant-side Defender
provisioning rather than as an empty agent query. Do not deploy unrelated
Cloud Discovery sources or manually create Microsoft first-party service
principals to work around it. Escalate to Microsoft with the Agent 365 license,
Admin Center Activity, Defender subscription/MTP errors, and unresolved-table
evidence.

---

## Scenario 7: Verify the Entra identity

### ARRANGE

Sign in to [Microsoft Entra Admin Center](https://entra.microsoft.com/) with
permission to view Agent Identities, enterprise applications, permissions,
and workload sign-ins.

### ACT

Search by Agent Identity application ID:

```text
7f2edbcc-8375-4d1d-a430-93c14e8db94e
```

Review:

- the Agent Identity and its blueprint relationship;
- sponsor/owner;
- assigned application permissions;
- delegated grants;
- credentials; and
- workload identity sign-in activity around the Scenario 3 window.

Also locate the blueprint:

```text
341ff526-fa67-4487-a028-5d61dd6e5a92
```

### ASSERT

- The Agent Identity exists and references the expected blueprint.
- The sponsor is correct.
- The Agent Identity itself has no password, certificate, or federated
  credential; credentials belong to the blueprint.
- No broad Microsoft 365 data role is assigned to the Agent Identity.
- No delegated user grant is assigned for this S2S telemetry flow.
- Workload sign-in activity is consistent with the verification window.
- The local blueprint secret is understood to be development-only.

---

## Scenario 8: Understand what Purview can verify today

### ARRANGE

Recognize the current data boundary:

- the agent reads PostgreSQL portfolio data;
- model traffic goes through APIM;
- prompts and responses are intentionally not exported;
- the agent has no SharePoint, OneDrive, Exchange, Teams, or Work IQ data
  permission.

### ACT

In the Agent Registry, review the **Data & Tools** and **Security** tabs. If
your tenant exposes applicable Purview audit or risk records for the agent,
inspect only the Scenario 3 window.

### ASSERT

- Agent identity and operational metadata can be governed.
- No Microsoft 365 knowledge source or data permission is listed.
- No confidential portfolio content appears in Purview.
- The absence of SharePoint/Exchange/Teams DLP events is expected and is not
  an integration failure.

Do not attempt to prove Purview DLP by granting the agent Microsoft 365 data
access. A meaningful DLP test requires a separately approved Microsoft 365
tool, labeled test content, a test DLP policy, and a nonproduction scenario.

---

## Scenario 9: Test governance actions safely

### ARRANGE

Use the Agent Registry details pane. Do not select **Block**, **Uninstall**, or
change permissions unless a reversible nonproduction test has been approved.

### ACT

Perform read-only governance review:

1. Confirm the sponsor and technical owner.
2. Review permissions.
3. Review security status.
4. Review available policy/template assignment.
5. Add approved organizational tags if tag changes are in scope.
6. Record credential expiry and rotation owner without recording the secret.

Recommended tags:

```text
owner-portfolio-platform
environment-local-dev
data-confidential
identity-agent-id
telemetry-metadata-only
```

### ASSERT

- An accountable sponsor and technical owner are known.
- Permissions remain least privilege.
- No unapproved capability was enabled.
- Development and future production instances are distinguishable.
- A credential rotation date and incident owner are defined.

Blocking an Agent Registry entry might not stop the separately running local
Python process or revoke its APIM user access. Identity disablement, blueprint
credential revocation, APIM authorization, and telemetry disablement are
separate controls and must be tested separately.

---

## What is working versus what is not enabled

### Implemented and testable now

| Capability | How to verify |
|---|---|
| Local interactive agent | Run `chat.py` |
| APIM-authorized model access | Successful authenticated chat |
| PostgreSQL tools | Ask account, price, position, and trade questions |
| Entra Agent Identity | Entra identity and workload sign-ins |
| Agent 365 Registry | Admin Center **Agents** > **All agents** |
| Metadata-only observability | Registry **Activity** tab |
| Sponsor and ownership | Registry and Entra details |
| Permissions review | Registry **Permissions** and Entra grants |
| Emergency telemetry disable | `ENABLE_A365_OBSERVABILITY=false` |

### Available as governance work, but not yet fully configured

| Capability | Current state |
|---|---|
| Organizational tags | Recommended, assignment not yet verified |
| Agent policy template | Review/assignment still required |
| Workload Conditional Access | Review/assignment still required |
| Formal lifecycle review | Process still required |
| Credential rotation drill | Still required |
| Retention/residency confirmation | Tenant decision still required |
| Production managed identity/WIF | Not implemented; local secret is in use |
| Defender security event visibility | Instrumentation and licensing are present, but this tenant does not currently expose `CloudAppEvents` |

### Intentionally not enabled

| Capability | Why it is not expected |
|---|---|
| Teams chat with this agent | No Teams/Microsoft 365 channel is deployed |
| Teams user Activity tab | The current channel is `local-cli` |
| Install/pin as a Microsoft 365 app | No deployable app/channel package exists |
| Work IQ | No Microsoft 365 Copilot data integration was approved |
| Mail, SharePoint, Files, or Teams tools | Broad Graph data permissions were denied |
| Agent user account and notifications | Explicitly out of scope |
| Autonomous triggers | No scheduler/event trigger is implemented |
| Connected agents | No agent-to-agent connection is configured |
| Computer use | Not configured or approved |
| Prompt/response display in telemetry | Disabled by the metadata-only policy |

These missing capabilities are not deployment defects. Each is a separate
feature with additional architecture, licensing, permissions, privacy, and
governance decisions.

---

## Final acceptance decision

### ARRANGE

Collect sanitized results from Scenarios 1-9.

### ACT

Complete:

```text
Application starts and is healthy: PASS | FAIL
Interactive agent questions succeed: PASS | FAIL
Agent appears in Registry: PASS | FAIL
Activity appears for the registered identity: PASS | FAIL
Defender events appear: PASS | FAIL | NOT LICENSED/AVAILABLE
Entra identity and sign-ins are correct: PASS | FAIL
No unapproved permissions exist: PASS | FAIL
No confidential content appears in telemetry: PASS | FAIL
Sponsor and owner are confirmed: PASS | FAIL
```

### ASSERT

Declare the current Agent 365 implementation **working** when:

1. the agent works through `chat.py`;
2. `/health` reports A365 `ready`;
3. the agent appears in the Microsoft 365 Agent Registry;
4. Activity appears for the registered Agent Identity;
5. Defender visibility is confirmed when licensed and available;
6. no unexpected permissions are present; and
7. no confidential content is exposed.

If the local agent works but Registry Activity never appears, classify the
Agent 365 integration as **partially working** and troubleshoot ingestion,
licensing, identity attribution, and viewer permissions.

For this validated environment, the current result is **partially working**:
the runtime, Agent Identity, Registry, metadata-only export, and Admin Center
Activity are working, but Defender verification is blocked because
`CloudAppEvents` is unavailable in the tenant. This does not prove that the
agent failed to export spans, and Admin Center arrival does not prove that
every child inference and tool span was accepted.

## Current Microsoft references

- [Understand agent details in Microsoft 365 Admin Center](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/agent-details)
- [Agent 365 observability](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/monitor-agents)
- [Microsoft OpenTelemetry Distro](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry)
- [Agent 365 observability concepts](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-concepts)
- [Troubleshoot direct OpenTelemetry integration](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-direct-troubleshoot)
- [Observe agent activity](https://learn.microsoft.com/en-us/microsoft-agent-365/observe)
- [Microsoft Purview support for Agent 365](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/purview-agent-365)
