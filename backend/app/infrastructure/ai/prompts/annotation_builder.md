Prompt module: annotation_builder

Use this module when line-level evidence is transformed into UI annotations or evidence summaries.

- Preserve file and line accuracy.
- Prefer exact evidence-backed ranges over approximate ranges.
- Do not create an annotation if the evidence anchor is missing.
- Keep titles short and evidence-focused.
- If some findings lack line-level evidence, disclose that instead of fabricating ranges.
