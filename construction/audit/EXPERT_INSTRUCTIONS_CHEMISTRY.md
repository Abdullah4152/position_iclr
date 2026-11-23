# Expert Review Instructions: Chemistry

## Purpose

You are reviewing chemistry QA items for the construction audit accompanying the paper on scientific memory in research-agent dialogues. Your task is to judge whether
each question, gold answer, evidence link, and label is scientifically usable.

You are validating the dataset, not grading model predictions.

## File To Review

Use:

```text
data/expert_review_sample_300_completed.csv
```

Review only rows where:

```text
domain = chemistry
```

There should be 100 chemistry rows in the construction-audit sample.

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

Use `accept` only when the item is chemically accurate, sufficiently supported
by the provided evidence, and correctly labeled.

Use `revise` when the item is useful but needs a limited fix, such as a softer
scope, corrected evidence, clearer reaction condition, or corrected category.

Use `reject` when the answer is unsupported, the cited source is wrong, the
question is not answerable from the evidence, the apparent contradiction is
artificial, or the item is too generic to test scientific memory.

If you choose `revise`, write a corrected answer in
`expert_corrected_gold_answer` when possible.

Keep `expert_rationale` short: one or two sentences.

## Chemistry Checks

Watch for these domain-specific issues:

- For Cu CO2 electroreduction, Hori 1994 is a metal-comparison/selectivity
  anchor, not the original 1986 hydrocarbon-discovery paper. Flag overclaims
  that say 1994 established Cu hydrocarbon production.
- For Soai autocatalysis, distinguish ordinary amplification from stochastic
  symmetry breaking with no added chiral source.
- For Cu-zeolite methane-to-methanol active sites, do not overstate the
  trinuclear MOR result as invalidating all dicopper assignments. The active
  species can be framework-dependent.
- For Pd cross-coupling, nanoparticle-reservoir explanations should be framed
  as resolving homogeneous/heterogeneous ambiguity, not as proving every system
  is nanoparticle-catalyzed.
- For proline aldol chemistry, distinguish computational transition-state
  arguments from direct NMR observation of enamine intermediates.
- For photocatalytic water splitting, Maeda 2006 Nature is a brief
  communication; the substantive visible-light overall water-splitting anchor is
  the JACS paper. Flag answers that rely on the brief communication for details
  it does not contain.
- For Fenton chemistry, pH and ligand environment matter for hydroxyl-radical
  versus Fe(IV)=O interpretations.
- For Pd C-H activation, strong directing groups, weak coordination, and
  template-directed remote activation are stages of methodology evolution, not a
  single mechanism.
- For CuAAC, the Sharpless 2002 mononuclear cartoon should not be treated as the
  final mechanism. Worrell 2013 supports two Cu involvement in the transition
  state.
- For FLP H2 activation, separate stoichiometric H2 splitting from catalytic
  hydrogenation extensions.

## Final Handoff

Return the completed rows as a CSV. Preserve the original row order if possible.
If splitting by domain, name the completed file:

```text
expert_review_sample_300_completed_chemistry.csv
```
