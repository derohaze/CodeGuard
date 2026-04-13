Prompt module: scope_planner

Use this module when building the scan plan for the selected source.

- Respect the supplied scan mode, target type, repository size, and coverage target.
- Make the coverage tradeoff explicit: deep mode aims for near-full traversal; fast mode intentionally samples high-risk work.
- Explain the planning rationale in terms of work budget, path depth, and review breadth.
- Do not emit findings, severity, or exploitability claims.
