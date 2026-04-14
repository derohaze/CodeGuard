Shared remediation policy for Khwarizm:

- Prefer complete sink-level or service-layer fixes over router-only filtering.
- Distinguish clearly between:
  - full fix
  - partial mitigation
  - temporary guard
  - risky workaround
- Do not claim a full fix if the sink pattern still fundamentally remains reachable.
- Preserve project style and local code shape. Avoid unrelated refactors.
- If a safer fix belongs deeper in the service, DAO, query, execution, or session layer, say that explicitly.

Category guidance:

- Command injection:
  - prefer structured execution (`argv` arrays, `shell=False`, `execFile`, `spawn` without shell) over filtering
- SSRF:
  - prefer URL parsing, scheme/host validation, allowlists, private/link-local/metadata blocking, and client-layer enforcement over regex-only checks
- SQL / NoSQL injection:
  - prefer parameterization, typed filters, safe query builders, and operator allowlists over sanitization-only approaches
- Auth / session:
  - prefer fixes in authentication/session/security logic over route-only guards
  - consider regeneration, invalidation, rotation, and server-side verification where relevant
- Path traversal / filesystem:
  - prefer canonicalization plus safe-root enforcement over filename filtering
- GraphQL:
  - respect resolver/context evidence, auth directives or middleware, and data-exposure boundaries when they are present

Output discipline:

- If the product expects structured fields such as fix type, security strength, regression risk, residual risks, or policy notes, populate them directly instead of forcing defaults downstream.
