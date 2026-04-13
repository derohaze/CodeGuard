Prompt module: framework_detector

Use this module when classifying the repository stack from manifests, imports, route markers, and framework hints.

- Identify the most credible primary framework from explicit evidence.
- Separate primary framework from secondary framework hints.
- Mention ambiguity if markers are mixed, weak, or partial.
- Prefer conservative framework labels over speculative ones.
- Carry forward the strongest detection evidence into planning and trust-boundary reasoning.
- Do not create findings, severity, or exploitability claims in this step.
