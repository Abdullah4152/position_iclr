# Expert Review Instructions: Materials Science

## Purpose

You are reviewing materials science QA items for the construction audit accompanying the paper on scientific memory in research-agent dialogues. Your task is to judge
whether each question, gold answer, evidence link, and label is scientifically
usable.

You are validating the dataset, not grading model predictions.

## File To Review

Use:

```text
data/expert_review_sample_300_completed.csv
```

Review only rows where:

```text
domain = materials_science
```

There should be 100 materials science rows in the construction-audit sample.

## Columns To Read

For each row, read:

- `source_arc_id`
- `question_id`
- `category`
- `question`
- `gold_answer`
- `answerability`
- `source_paper_ids`
- `source_titles`
- `evidence_text`
- `method_slots`
- `condition_slots`
- `requires_cross_session_memory`
- `requires_cross_paper_reasoning`
## Columns To Fill

Fill these columns:

- `expert_gold_answer_correctness`
- `expert_evidence_support`
- `expert_category_label`
- `expert_answerability_label`
- `expert_item_decision`
- `expert_rationale`
- `expert_corrected_gold_answer`
- `expert_notes`

Do not change `question_id`, `source_arc_id`, or other ID columns.

## Allowed Labels

For `expert_gold_answer_correctness`, use:

- `correct`
- `partially_correct`
- `incorrect`
- `cannot_judge`

For `expert_evidence_support`, use:

- `fully_supported`
- `partially_supported`
- `unsupported`
- `wrong_source`
- `insufficient_evidence`

For `expert_category_label`, use one of:

- `hypothesis_tracking`
- `evidence_provenance`
- `contradiction_resolution`
- `temporal_claim_revision`
- `method_condition_constraints`
- `cross_paper_synthesis`
- `uncertainty_abstention`
- `entity_relation_recall_control`
- `category_mismatch`

For `expert_answerability_label`, use:

- `answerable`
- `ambiguous`
- `unanswerable`
- `mislabeled`

For `expert_item_decision`, use:

- `accept`
- `revise`
- `reject`

## Decision Rules

Use `accept` only when the item is scientifically accurate, sufficiently
supported by the provided evidence, and correctly labeled.

Use `revise` when the item is useful but needs a limited fix, such as a softer
scope, corrected evidence, clearer processing condition, or corrected category.

Use `reject` when the answer is unsupported, the cited source is wrong, the
question is not answerable from the evidence, the apparent contradiction is
artificial, or the item is too generic to test scientific memory.

If you choose `revise`, write a corrected answer in
`expert_corrected_gold_answer` when possible.

Keep `expert_rationale` short: one or two sentences.

## Materials Science Checks

Watch for these domain-specific issues:

- For halide perovskite PVs, efficiency gains are not composition-independent.
  Composition, processing, additives, and architecture all matter.
- For magic-angle twisted bilayer graphene, distinguish reproducibility issues
  from nonexistence of superconductivity. Local twist-angle disorder and pressure
  tuning should not be conflated.
- For MoS2 monolayer mobility, do not reduce the Fuhrer/Hone critique to only
  high-k dielectric screening. Four-probe/two-probe ambiguity and Y-function
  extraction matter.
- For LLZO, inadvertent Al incorporation from alumina crucibles is central.
  Early "pure" cubic LLZO may actually be Al-stabilized.
- For high-entropy alloys, Cantor and Yeh are near-simultaneous but different:
  empirical observation versus entropy-framing. Do not imply single-phase
  formation is guaranteed for all HEAs.
- For Bi2Se3 topological insulators, separate ARPES surface-state evidence from
  transport dominated by bulk n-doping from Se vacancies.
- For MOF surface area, activation protocol and BET applicability criteria are
  part of the measurement story, not incidental details.
- For graphene CVD on Cu, trace surface oxygen suppressing nucleation density is
  the mechanistic point in the Hao 2013 arc.
- For Ni-rich NMC, higher Ni increases capacity but worsens degradation risk;
  gradient, coating, and single-crystal strategies are engineering responses.
- For perovskite defect tolerance versus ion migration, shallow electronic
  defects and halide ion migration are different physical channels, not a direct
  contradiction.

## Final Handoff

Return the completed rows as a CSV. Preserve the original row order if possible.
If splitting by domain, name the completed file:

```text
expert_review_sample_300_completed_materials_science.csv
```
