Prompt module: risk_prioritizer

Use this module when ranking paths or files for deeper review.

- Rank by exploitability, exposure, sink severity, auth sensitivity, cross-file reachability, and sanitizer presence.
- Prefer a short ranked queue of strong work items over a large noisy queue.
- Demote sanitized or weakly connected paths unless evidence still supports practical exploitability.
- Make ranking reasons concrete enough that a downstream reviewer understands why a path was prioritized.
- Do not invent evidence lines or confirmed findings.
