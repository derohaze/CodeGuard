---
name: race
description: Race condition / TOCTOU playbook — limit overrun, single-packet attack (last-byte sync) to force parallel processing, and state-confusion races (file upload + read, order before payment).
allowed-tools:
  - http
  - shell
  - file_write
---

# Race / TOCTOU playbook

## Targets worth racing
- Redeem a gift card / promo code
- Cast a vote / claim a one-per-user reward
- Withdraw / transfer balance
- Submit a 2FA code
- Apply a discount
- Send a friend / invite request
- Confirm an email
- Upload then read a file

## 1. Single packet attack (last-byte sync)
Send N requests where each is fully serialized except the last byte. Flush the final byte of all N in a single write. Python skeleton:
```python
import asyncio, httpx
async def main():
    transport = httpx.AsyncHTTPTransport(http2=True)
    async with httpx.AsyncClient(transport=transport, verify=False) as c:
        ...
asyncio.run(main())
```

## 2. HTTP/1.1 pipelined burst (fallback)
```sh
seq 50 | xargs -P 50 -I{} curl -s -X POST https://target/redeem \
  -H 'Cookie: session=<sess>' -d 'code=GIFT100'
```

## 3. Confirm a race
- Before: query balance / count / state
- Fire N parallel requests
- After: query balance / count / state

If invariant differs by more than 1x the per-request delta, you have a race.

## 4. TOCTOU on file/auth flows
- Upload + scan + serve: race the swap between AV scan and final write.
- "Is admin?" check: race a logout/role-change between check and use.

## 5. Mitigation patterns (what defeats you)
- `SELECT ... FOR UPDATE` / row lock
- Optimistic concurrency with version field
- Idempotency keys
- `UNIQUE` constraints

## 6. Reporting
Required:
- The exact race window measured
- Before/after invariant query results
- Concrete impact
