# Run regional capacity preflight

## When to use
- Before the first deployment to a subscription or tenant.
- When selecting hub, App Service, or Foundry regions.
- After a regional SKU, quota, model, or capacity deployment failure.
- When the last preflight report is stale.

## Purpose
Generate subscription-specific regional evidence before `azd up`. The workflow is read-only:
it checks the subscription-scoped APIM SKU/restriction API, advertised resource availability,
exact App Service and Foundry model SKUs, and quota APIs where supported. It never treats
missing quota data as unlimited capacity.

## Run
1. Confirm Azure CLI targets the intended subscription:
   `az account show --query "{name:name,id:id,tenantId:tenantId}" -o table`
2. Install or update the quota extension:
   `az extension add --name quota --upgrade`
3. Run from the repository root:
   `./scripts/regional-preflight.ps1 -SubscriptionId <subscription-id>`
   The default policy selects the first generally available `GlobalStandard` small chat model
   from the preference list independently for each Foundry candidate region.
4. For an explicit candidate set:
   `./scripts/regional-preflight.ps1 -SubscriptionId <subscription-id> -HubRegions canadacentral,centralus -AppRegions canadaeast,eastus2 -FoundryRegions swedencentral,centralus`
5. To require one exact model:
   `./scripts/regional-preflight.ps1 -SubscriptionId <subscription-id> -ModelSelection Exact -ModelName gpt-5.4-mini -ModelVersion 2026-03-17`
6. Read `.azure/preflight/regional-preflight.json` and summarize the placement evidence.

## Result semantics
- `PASS`: the queried evidence supports the exact requirement.
- `CONDITIONAL`: the service is advertised, but deploy-time SKU capacity is not exposed.
- `UNKNOWN`: the provider or quota API returned no usable evidence. Never interpret this as
  unlimited capacity.
- `FAIL`: a required resource type, SKU, model, or version is unavailable.

The script exits `2` when any placement has a `FAIL`; `CONDITIONAL` and `UNKNOWN` do not
produce a failing exit code. The APIM SKU API can eliminate missing or formally restricted
PremiumV2 regions, but it does not expose transient physical capacity. ARM `validate` and
`what-if` also do not exercise that capacity gate.

## Interpretation
- Rank regions independently for the hub, application spoke, and Foundry spoke.
- When `ModelSelection` is `AnySmall`, report the selected model and version for each Foundry
  region and require the deployment configuration to use the selected values.
- Prefer a `PASS` placement over `CONDITIONAL`.
- Never describe a `CONDITIONAL` hub as capacity-approved.
- During `azd up`, stage the final VNet-injected APIM resource first. Continue with VPN,
  App Service, DNS, identity, and Foundry only after APIM reaches `Succeeded`.
- Explain any model lifecycle or deprecation warning.
- Record the report timestamp because capacity evidence becomes stale.

## Safety
- Do not register providers, request quota, create resources, or run `azd up`.
- Do not hard-code a tenant or subscription in the repository.
- Do not write secrets to the report.
- Do not promise physical capacity from the read-only report. The staged final APIM create is
  the decisive live probe and is billable if it succeeds.
