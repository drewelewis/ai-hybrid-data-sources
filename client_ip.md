# Client IP addresses in Azure API Management

Azure API Management (APIM) obtains the source IP address from the incoming
network connection. A client does not normally need to send its IP address in a
request header.

## Use the client IP in an APIM policy

The address observed by the APIM gateway is available through:

```xml
@(context.Request.IpAddress)
```

For example, APIM can pass the observed address to a backend:

```xml
<set-header name="X-Client-IP" exists-action="override">
    <value>@(context.Request.IpAddress)</value>
</set-header>
```

Use `exists-action="override"` so that a caller cannot supply a spoofed
`X-Client-IP` value.

## Record the client IP with diagnostic settings

Enable the APIM `GatewayLogs` resource log category in a diagnostic setting and
send it to a Log Analytics workspace. When resource-specific tables are enabled,
the observed address is stored in the `CallerIpAddress` column of the
`ApiManagementGatewayLogs` table:

```kusto
ApiManagementGatewayLogs
| project TimeGenerated, CallerIpAddress, Method, Url, ResponseCode
| order by TimeGenerated desc
```

Diagnostic settings export the address for monitoring after APIM processes the
request. They do not inject an address into a request or make it available to a
policy; policies already have the observed address in
`context.Request.IpAddress`.

## Understand proxies and NAT

Both `context.Request.IpAddress` and `CallerIpAddress` identify the immediate
network peer visible to APIM:

| Request path | Address APIM normally observes |
|---|---|
| Client directly to APIM | Client IP |
| On-premises client over the S2S VPN, without NAT | On-premises client's private IP |
| Client through NAT | NAT address |
| Client through a reverse proxy, Application Gateway, or Front Door | Proxy address |

For this repository's direct on-premises-to-internal-APIM path over the
Site-to-Site VPN, APIM should see the on-premises client's private address unless
the on-premises network or another intermediary applies source NAT.

### Preserve the original address through a trusted proxy

When a trusted reverse proxy is present, it must forward the original address,
usually in `X-Forwarded-For`. The first entry is conventionally the originating
client:

```xml
<set-variable
    name="clientIp"
    value="@(
        context.Request.Headers
            .GetValueOrDefault(&quot;X-Forwarded-For&quot;, context.Request.IpAddress)
            .Split(',')[0]
            .Trim()
    )" />
```

Do not trust `X-Forwarded-For` from arbitrary callers because clients can spoof
request headers. Use it only when:

1. APIM accepts traffic only from the trusted proxy.
2. The proxy overwrites or constructs `X-Forwarded-For`.
3. The policy validates that the immediate peer is an expected proxy before
   trusting the forwarded value.

If these controls are not in place, use `context.Request.IpAddress`.

## References

- [Azure Monitor `ApiManagementGatewayLogs` table](https://learn.microsoft.com/azure/azure-monitor/reference/tables/apimanagementgatewaylogs)
- [APIM policy expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [Monitor Azure API Management](https://learn.microsoft.com/azure/api-management/monitor-api-management)
