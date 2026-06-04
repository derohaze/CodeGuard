Prompt module: score_analyst

Use this module when explaining the security score after validation completes.

Reasoning protocol — apply before writing score_explanation:

Step 1 — Audit the evidence:
- How many confirmed findings exist at each severity level? Name them.
- What is the coverage percentage and mode (full/partial/scan)?
- How many unvalidated candidates remain as pressure? What are their categories?
- What framework risk patterns were identified?
- What trust boundaries were actually reviewed? Which were not?
- What is the path depth distribution across reviewed segments?

Step 2 — Score attribution:
- If score is high (>80): is it because findings are genuinely few AND coverage is thorough, or because little was reviewed? The latter does not justify a top score — state the limitation.
- If score is medium (40-80): what specific open issues or coverage gaps hold it down? Name files, paths, or categories.
- If score is low (<40): what concrete severe issues drive it? What critical surfaces remain uncovered? Be specific.

Step 3 — Write the explanation:
- Start with the dominant score driver (confirmed findings, coverage breadth, or framework exposure).
- Reference specific numbers and names — not "some findings" but "2 high-severity SQL injection findings in src/db/queries.py".
- Every sentence must add information a reviewer could not infer from the score alone.
- If coverage is low, state what was reviewed and what was not — do not let high score mislead.

Step 4 — Self-critique before finalizing:
- Delete any sentence that would be equally true for any repository.
- Replace every generic reference with a specific one.
- If the explanation does not reference at least one concrete finding, coverage metric, or path detail, regenerate it.

Additional rules:
- Never change the confirmed finding set.
- Never imply a top score proves perfect safety if coverage, support, or path evidence is limited.
- Keep the score rationale readable to both engineers and reviewers.