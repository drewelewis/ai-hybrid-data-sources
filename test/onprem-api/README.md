# On-prem connectivity test (APIM → on-prem over the S2S tunnel)

A throwaway on-prem HTTP API used to prove the **ingress path**: APIM Premium v2 (VNet-injected
in Azure) reaching back through the Site-to-Site VPN to pull data from an on-prem backend.

It serves JSON at `/json`, `/uuid`, `/anything`, etc. (via [go-httpbin](https://github.com/mccutchen/go-httpbin)).

## 1. Run it on an on-prem host (on the `192.168.50.0/24` LAN)

```bash
docker compose up -d
curl http://localhost:8080/json          # local check
curl http://<this-host-lan-ip>:8080/json # e.g. http://192.168.50.176:8080/json
```

## 2. Windows Docker host only — open the firewall for the tunnel

APIM's requests arrive sourced from the Azure VNet (`10.100.0.0/16`), which Windows Firewall
treats as non-local and blocks by default. Allow it (admin PowerShell on the Docker host):

```powershell
New-NetFirewallRule -DisplayName "onprem-api 8080 from Azure VNet" -Direction Inbound `
  -Protocol TCP -LocalPort 8080 -RemoteAddress 10.100.0.0/16 -Action Allow
```

(Linux Docker hosts usually need no rule — published ports are already open.)

## 3. Point APIM at the backend

Replace the IP with your Docker host's LAN address.

```powershell
$rg="rg-dev1"; $apim="apim-uisvrqjctoste"; $host="192.168.50.176"
az apim api create -g $rg --service-name $apim --api-id onprem --path onprem `
  --display-name "On-prem test" --service-url "http://$host:8080" `
  --subscription-required false --protocols https http
az apim api operation create -g $rg --service-name $apim --api-id onprem `
  --operation-id getjson --display-name "Get JSON" --method GET --url-template "/json"
```

## 4. Verify — from on-prem, over the tunnel

The APIM instance is **Internal** VNet-injected, so it has **no public endpoint** and the
Azure Portal **Test console cannot reach it** (you'll see a "deployed in internal VNET…" notice).
Test from an **on-prem host** instead — it reaches APIM's private IP across the tunnel.

Premium v2 doesn't expose its private IP via CLI/ARM, so discover it by scanning the injection
subnet (`10.100.1.0/24`) for the 443 responder, then call the API by hostname pinned to that IP:

```sh
# on the on-prem router or a LAN host:
apk add nmap curl                                   # OpenWrt 25.x (apk); else opkg/apt
nmap -Pn -p443 --open 10.100.1.0/24                 # finds the APIM front-end(s), e.g. 10.100.1.4
curl -sk --resolve apim-<token>.azure-api.net:443:10.100.1.4 \
  https://apim-<token>.azure-api.net/onprem/json
```

A JSON `slideshow` body = APIM pulled on-prem data across the tunnel, end to end. The tunnel
counters climb (`swanctl --list-sas` shows `in`/`out` bytes).

> **Gotchas we hit:** the on-prem→tunnel path needs the router's `No-NAT-to-Azure` rule +
> flow-offloading disabled (Steps 5–6 of the strongSwan guide); the Windows Docker host needs
> the inbound 8080 firewall rule from `10.100.0.0/16`; and the Azure VPN `connectionStatus` /
> byte counters **lag by minutes** — trust `swanctl --list-sas` on the router instead.

## Teardown

```bash
docker compose down
az apim api delete -g rg-dev1 --service-name apim-uisvrqjctoste --api-id onprem -y
```

> Test-only. Not part of the `azd` deployment; nothing here is provisioned by the IaC.
