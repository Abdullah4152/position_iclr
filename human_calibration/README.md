# Human calibration subset

120 responses, stratified 20 per diagnostic condition and spread across capability categories
and systems. The sheet is blinded: it carries the question, the expert gold answer, the gold
labels, the evidence, and the response, but not which system produced it and not the model
judge's verdict. The judge's verdicts and the system identities live in
`key_and_judge_verdicts.jsonl`, which a grader should not open until the sheet is filled.

## Why this exists

Every preservation component in the paper is graded by a model judge. That judge is validated
against targeted corruptions and is self-consistent, but it agrees only moderately with a
second judge, so absolute levels in the paper are judge-dependent. A human pass over this
subset is what would turn those levels into calibrated numbers. It is sized for roughly one
annotator-day.

## How to grade

For each row, read the question, the gold answer and the evidence, then judge the response
only against what the gold answer and evidence support. Fill one value per column:

- `human_answer_fidelity`: correct | partial | incorrect. Use *correct* only if the response
  conveys the gold conclusion with the same strength and the same qualifications.
- `human_unsupported_claim`: true | false. True if the response asserts any fact, number,
  mechanism, condition or attribution that the gold answer and evidence do not support.
- `human_contradiction_preserved`: yes | no | na. Na if the gold record contains no conflict.
- `human_revision_preserved`: yes | no | na. Na if the gold record contains no revision.
- `human_scope_preserved`: yes | no | na. Na if the gold record carries no method or
  condition limits.
- `human_uncertainty_preserved`: yes | no | na. Na if the gold record is definitive.
- `human_provenance_correct`: yes | no | na. Na if the response attributes nothing and no
  attribution was required.

Use `human_notes` for anything that does not fit. Grade every row independently; do not go
back and adjust earlier rows for consistency.

## What to compute afterwards

Agreement and Cohen's kappa between `human_*` and the `judge` fields in the key file, per
component, and the joint-fidelity rate under human grading versus under the judge. Those two
numbers are what the paper is missing, and what any future automatic scorer should be
validated against.
