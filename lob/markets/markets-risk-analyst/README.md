# Markets Risk Analyst

This folder contains a simple, model-only Microsoft Agent Framework agent for
Contoso Bank Markets risk professionals. It sends model requests through the
governed Azure API Management endpoint and has no direct model route.

The agent does not connect to position, limit, trade, or market-data systems.
It analyzes only approved information supplied in the conversation and keeps
risk decisions with qualified human reviewers.

## Configure

From this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item env.sample .env
```

Edit the git-ignored `.env` with environment-specific values:

| Setting | Purpose |
| --- | --- |
| `ENVIRONMENT_NAME` | Required on-premises lifecycle stage: `local`, `dev`, `tst`, or `prd` |
| `APIM_OPENAI_ENDPOINT` | HTTPS origin of the APIM gateway, without `/openai` |
| `APIM_TOKEN_SCOPE` | Entra scope exposed for the APIM model API |
| `APIM_SUBSCRIPTION_KEY` | Server-side APIM product subscription key |
| `MODEL_DEPLOYMENT_NAME` | Azure OpenAI deployment exposed through APIM |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI-compatible API version |
| `AZURE_AUTH_MODE` | `default` or `device-code` |
| `AZURE_TENANT_ID` | Required only for device-code authentication |
| `AZURE_CLIENT_ID` | Required only for device-code authentication |

Never commit the populated `.env` or an APIM subscription key.
The workstation-local `.env` starts with `ENVIRONMENT_NAME=local`; its APIM
token scope and subscription key remain blank until approved values are
provided.

## Agent ID desired state

The [Agent ID desired-state folder](./identities/README.md) contains:

- Separate nonproduction and production blueprint specifications.
- One common Agent Identity base with independently promoted, schema-validated
  instance overlays for `local`, `dev`, `tst`, and `prd`.
- Support for additional regional or legal-entity production instances and
  controlled sponsor overrides.
- Closed blueprint and identity schemas, a deterministic renderer, blueprint
  readiness enforcement, and focused policy tests.
- A GitHub OIDC plan/apply workflow for create-or-verify provisioning of the
  core blueprint, BlueprintPrincipal, and selected Agent Identity.
- Sponsor, owner, tag, custom-security-attribute, APIM attribution, Agent 365
  registration, credential-policy, and lifecycle intent.

These internal artifacts are not raw Graph payloads and do not indicate that
tenant objects exist. Every included identity and blueprint is `proposed` with
provisioning disabled, unresolved governance references, no permission
grants, and no credential material. Generated plans are ignored and must not
be committed.

The checked-in workflow is also inactive until administrators configure its
protected GitHub environments, federated planner and provisioner
applications, Graph permissions, consent, and symbolic principal mappings.
No workflow definition or desired-state artifact proves tenant deployment.

## Run

```powershell
.\.venv\Scripts\python.exe .\chat.py
```

The console preserves conversation continuity for the current process. Type
`quit` or `exit` to stop it.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest .\test_markets_risk_agent.py -q
```

The tests validate configuration, authentication selection, prompt
boundaries, and APIM client construction without sending a model request.
