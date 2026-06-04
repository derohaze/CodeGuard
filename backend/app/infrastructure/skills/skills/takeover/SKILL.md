---
name: takeover
description: Subdomain takeover playbook — sweep subdomains for dangling CNAMEs/NS records pointing at unclaimed third-party resources (GitHub Pages, S3, Heroku, Azure, Netlify, Shopify, ...), confirm with HTTP fingerprint, then prove impact by claiming the resource.
allowed-tools:
  - http
  - shell
  - file_write
---

# Subdomain takeover playbook

## 1. Enumerate subdomains
```sh
curl -s 'https://crt.sh/?q=%25.target.example.com&output=json' | jq -r '.[].name_value' | sed 's/^\*\.//' | sort -u > subs.txt
curl -s 'https://jldc.me/anubis/subdomains/target.example.com' | jq -r '.[]' >> subs.txt
sort -u subs.txt -o subs.txt
```

## 2. Resolve each name — CNAME first
```sh
while read -r sub; do
  cname=$(dig +short CNAME "$sub" | head -n1)
  if [ -n "$cname" ]; then printf '%s\tCNAME\t%s\n' "$sub" "$cname"; fi
done < subs.txt > resolved.tsv
```

## 3. Match HTTP fingerprints
For each CNAME match, fetch and grep for fingerprint.
Common fingerprints:

| Service | CNAME pattern | Fingerprint |
|---|---|---|
| GitHub Pages | `*.github.io` | `There isn't a GitHub Pages site here.` |
| Heroku | `*.herokuapp.com` | `No such app` |
| AWS S3 | `*.s3-website-*.amazonaws.com` | `NoSuchBucket` |
| Azure App Service | `*.azurewebsites.net` | `404 Web Site not found.` |
| Netlify | `*.netlify.app` | `Not Found - Request ID` |
| Shopify | `*.myshopify.com` | `Sorry, this shop is currently unavailable.` |

## 4. Confirm before reporting
Attempt to register the resource. If it succeeds, serve a benign proof file.

## 5. Reporting
Required: vulnerable subdomain, DNS resolution path, provider, HTTP fingerprint, PoC, impact.
