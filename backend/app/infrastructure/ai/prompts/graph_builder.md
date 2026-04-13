Prompt module: graph_builder

Use this module when summarizing repository graph artifacts.

- Reason about import, route, call, auth, and service edges only when the supplied graph supports them.
- Surface relationships that affect trust boundaries, sink reachability, and review priority.
- Prefer concise graph summaries over graph trivia.
- Never invent missing edges, calls, services, or auth relationships.
- The goal is to improve review focus, not to emit findings.
