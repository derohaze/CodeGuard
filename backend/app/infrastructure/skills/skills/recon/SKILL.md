---
name: recon
description: External recon playbook for a web target — subdomain enumeration, live-host probing, tech fingerprinting, and a first pass at content discovery. Use when the user gives you a root domain or apex and wants attack surface mapping.
allowed-tools:
  - shell
  - http
  - file_write
---

# Recon playbook

Stay surgical — do not scan IP ranges or third-party assets.

Default to curl and the built-in HTTP tool. Do not pull in specialized scanners (subfinder, httpx, ffuf, gobuster) unless the user explicitly asks for them.

## 1. Confirm scope
Before running anything, restate the apex domain and confirm scope.

## 2. Passive subdomain enumeration with curl
Pull from public CT logs:
```
APEX="example.com"
mkdir -p "recon/$APEX"
: > subs.txt
for attempt in 1 2 3; do
  resp=$(curl -fsS --max-time 30 -H 'Accept: application/json' \
    "https://crt.sh/?q=%25.$APEX&output=json" 2>/dev/null || true)
  if printf '%s' "$resp" | jq -e 'type == "array"' >/dev/null 2>&1; then
    printf '%s' "$resp" \
      | jq -r '.[].name_value' \
      | sed 's/^\*\.//' \
      | tr 'A-Z' 'a-z' | tr -d '\r' \
      | sort -u > subs.txt
    break
  fi
  sleep 3
done
```

Second source - AlienVault OTX:
```
otx=$(curl -fsS --max-time 30 "https://otx.alienvault.com/api/v1/indicators/domain/$APEX/passive_dns" 2>/dev/null)
printf '%s' "$otx" | jq -e . >/dev/null 2>&1 \
  && printf '%s' "$otx" | jq -r '.passive_dns[].hostname' | sort -u >> subs.txt
sort -u -o subs.txt subs.txt
```

## 3. Liveness + tech fingerprinting
```
while read h; do
  curl -ksS -o /tmp/body -w "%{http_code}\t%{url_effective}\t%header{server}\t%header{x-powered-by}\n" \
    --max-time 8 "https://$h/" 2>/dev/null \
    | awk -F'\t' -v host="$h" '{title=""; getline title < "/tmp/body"; sub(/.*<title>/,"",title); sub(/<\/title>.*/,"",title); print $0"\t"title}'
done < subs.txt > httpx.txt
```

## 4. Content discovery
```
HOST="app.example.com"
WORDLIST=/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt
while read w; do
  code=$(curl -ksS -o /dev/null -w "%{http_code}" --max-time 5 "https://$HOST/$w")
  case "$code" in 200|204|301|302|401|403) echo "$code /$w";; esac
done < "$WORDLIST"
```

## 5. Summarize
Write a summary with:
- Counts: total subdomains, live hosts, by tech stack
- Top interesting hosts
- Candidate next steps
