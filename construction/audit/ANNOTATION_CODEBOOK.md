# Construction Audit Codebook

This codebook is for human validation of the construction-audit QA items. Validators judge
the dataset, not model predictions.

## Unit of Annotation

Annotate one QA item at a time while viewing:

- the question;
- the gold answer;
- the linked evidence spans;
- the dialogue sessions up to the cutoff session, if present;
- relevant source metadata and source-arc notes.

Do not use outside scientific knowledge to override the provided evidence state.
If the evidence state is scientifically implausible or unsupported, flag the
item for revision or rejection.

## Required Labels

### 1. Gold Answer Correctness

Allowed values:

- `correct`
- `partially_correct`
- `incorrect`
- `cannot_judge`

Use `correct` only if the gold answer follows from the linked evidence and uses
appropriate scope and uncertainty.

### 2. Evidence Support

Allowed values:

- `fully_supported`
- `partially_supported`
- `unsupported`
- `wrong_source`
- `insufficient_evidence`

Evidence is fully supported only when the minimal necessary evidence is present.
For contradiction questions, both sides of the contradiction should be linked
where possible.

### 3. Category Correctness

Allowed values are the frozen category slugs:

- `hypothesis_tracking`
- `evidence_provenance`
- `contradiction_resolution`
- `temporal_claim_revision`
- `method_condition_constraints`
- `cross_paper_synthesis`
- `uncertainty_abstention`
- `entity_relation_recall_control`
- `category_mismatch`

Choose `category_mismatch` if none of the frozen categories fits.

### 4. Answerability Correctness

Allowed values:

- `answerable`
- `ambiguous`
- `unanswerable`
- `mislabeled`

Use `ambiguous` when a qualified answer is possible but a single determinate
answer is not supported. Use `unanswerable` when the requested information is
absent from the evidence state.

### 5. Memory Requirement

Allowed values:

- `cross_session_required`
- `cross_session_not_required`

A question requires cross-session memory if a correct answer needs evidence from
two or more sessions, or requires recognizing a state update across sessions.

### 6. Cross-Paper Requirement

Allowed values:

- `cross_paper_required`
- `cross_paper_not_required`

A question requires cross-paper reasoning if a correct answer needs evidence
from two or more source papers or scientific records.

### 7. Final Item Decision

Allowed values:

- `accept`
- `revise`
- `reject`

Accept only if the answer, evidence, category, and answerability label are all
usable. Revise if a limited edit can fix the issue. Reject if the item is
unsupported, scientifically distorted, duplicated, trivial, or generated from a
false contradiction.

## Category Guidance

`hypothesis_tracking`: The item asks for the current working hypothesis or how
the hypothesis changed.

`evidence_provenance`: The item asks which source, experiment, paper, span, or
dialogue turn supports a claim.

`contradiction_resolution`: The item asks whether evidence conflicts, why it
conflicts, or how to preserve both sides.

`temporal_claim_revision`: The item asks how an earlier claim should be updated
after later evidence.

`method_condition_constraints`: The item asks whether a claim transfers across
assay, protocol, dataset, material, cell line, solvent, temperature, composition,
time point, benchmark split, or another scoped condition.

`cross_paper_synthesis`: The item asks for a combined picture across multiple
sources without flattening caveats.

`uncertainty_abstention`: The item asks about a claim whose evidence is mixed,
missing, unresolved, or insufficient.

`entity_relation_recall_control`: The item asks for ordinary scientific facts
or relations and is included as a control.

## Common Rejection Reasons

- The gold answer says more than the evidence supports.
- The question can be answered from generic domain knowledge alone.
- The category label is only loosely related to the question.
- The cited source is the wrong paper, turn, or experiment.
- The item asks for a single answer where the evidence is intentionally mixed.
- The apparent contradiction was introduced by the generator, not by the source
  arc.
- The item is a duplicate or near-duplicate.
- The dialogue contains unsupported scientific claims beyond the source arc.

## Adjudication

Adjudicators should record:

- the final label;
- the disagreement type;
- the reason for the decision;
- whether the item was edited, accepted as-is, or rejected.

Report raw agreement for all labels. Report kappa or alpha for answerability and
category labels when label distributions are not too imbalanced.

## Optional Model Triage

Before human validation, the construction audit may use an annotation-triage model to flag
likely answer-evidence mismatches, category errors, and answerability problems.
These model annotations are not ground truth.

For the paper-facing construction-audit summary, only GLM 5.1 agreement with expert labels is
reported as optional triage evidence. Expert judgment remains authoritative.

If a model triage label disagrees with expert judgment, the expert label is used
for all paper-facing counts.
