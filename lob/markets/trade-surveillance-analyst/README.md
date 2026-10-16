# Trade Surveillance Analyst

This folder contains a simple, model-only Microsoft Agent Framework agent for
Contoso Bank trade-surveillance professionals. It sends model requests through
the governed Azure API Management endpoint and has no direct model route.

The agent does not connect to order, trade, communications, or case systems.
It analyzes only approved information supplied in the conversation, treats
indicators as hypotheses, and keeps investigations with authorized humans.

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

## Run

```powershell
.\.venv\Scripts\python.exe .\chat.py
```

The console preserves conversation continuity for the current process. Type
`quit` or `exit` to stop it.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest .\test_trade_surveillance_agent.py -q
```

The tests validate configuration, authentication selection, prompt
boundaries, and APIM client construction without sending a model request.
