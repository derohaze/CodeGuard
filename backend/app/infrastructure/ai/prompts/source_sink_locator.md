Prompt module: source_sink_locator

Use this module when source, sink, and sanitizer artifacts are available.

- Identify the strongest candidate source -> sink paths supported by the supplied evidence.
- Prefer concrete trust-boundary paths with credible attacker influence.
- Mention sanitizer activity when present and let it reduce confidence unless the sink still remains reachable.
- Avoid confirming a vulnerability unless both attacker influence and sensitive sink evidence are visible.
- Feed the strongest path hints back into repository mapping, path review, and finding validation.
