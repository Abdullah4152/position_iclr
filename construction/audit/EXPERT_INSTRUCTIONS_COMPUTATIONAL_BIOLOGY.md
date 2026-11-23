# Expert Review Instructions: Computational Biology

## Purpose

You are reviewing computational biology QA items for the construction audit accompanying the paper on scientific memory in research-agent dialogues. Your task is to judge
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
domain = computational_biology
```

There should be 100 computational biology rows in the construction-audit
sample.

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

Use `accept` only when the item is scientifically correct, sufficiently
supported by the provided evidence, and correctly labeled.

Use `revise` when the item is useful but needs a limited fix, such as a softer
scope, corrected evidence, clearer condition, or corrected category.

Use `reject` when the answer is unsupported, the source is wrong, the question is
not answerable from the evidence, the apparent contradiction is artificial, or
the item is too generic to test scientific memory.

If you choose `revise`, write a corrected answer in
`expert_corrected_gold_answer` when possible.

Keep `expert_rationale` short: one or two sentences.

## Computational Biology Checks

Watch for these domain-specific issues:

- Do not collapse assay-dependent CRISPR off-target results into a single
  absolute genome-wide risk number. GUIDE-seq, CIRCLE-seq, DISCOVER-seq, and
  CHANGE-seq answer different methodological questions.
- For CCLE/GDSC reproducibility, distinguish harmonization from full
  vindication. Harmonized AUC and matched compounds improve concordance, but the
  original IC50 reproducibility issue is not simply erased.
- For gut microbiome Firmicutes:Bacteroidetes ratio, keep mouse mechanistic
  claims distinct from human population claims.
- For AlphaFold2, separate IDR-specific limits from broad community-assessment
  claims. Akdel 2022 is broader than IDRs alone.
- For PD-L1 IHC, distinguish tumor-cell scoring from immune-cell scoring. Hirsch
  2017 and Tsao 2018 are scope differences, not a simple flip-flop.
- For BRCA1 saturation genome editing, treat ACMG/AMP and variant-classification
  papers as standards that SGE plugs into, not as contradictory evidence.
- For scRNA-seq integration, remember that no universal best batch-correction
  method exists. Seurat v3 should be described as anchor-based integration, not
  just generic CCA.
- For EZH2, the key contrast is gain-of-function Y641 mutations in DLBCL versus
  loss-of-function contexts in MDS/MPN.
- For senescence, single markers such as p16 or p21 are insufficient by
  themselves. Multi-marker interpretation is central.
- For TNBC, Lehmann TNBCtype-4 and Burstein's four-subtype scheme are parallel
  frameworks, not the same four classes.

## Final Handoff

Return the completed rows as a CSV. Preserve the original row order if possible.
If splitting by domain, name the completed file:

```text
expert_review_sample_300_completed_computational_biology.csv
```
