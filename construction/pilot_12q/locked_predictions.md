# Locked Expectations for the 5DP-Subset Study

**Locked before any model call.**
Seed: 43. Items: 12. Models: 2: `moonshotai/kimi-k2-thinking` and
`nvidia/llama-3.3-nemotron-super-49b-v1.5`. GLM-5.1 is excluded because it
was used as annotation-triage evidence in the supplement and evaluating it as
a system-under-test would create a circularity concern. Conditions: 3
(`partial-source`, `gold-source`, `gold-memory-state`). Total runs: 72.
Manual scoring files were prepared; the released supplement reports visible
outputs and qualitative interpretation rather than model rankings.

## Why partial-source instead of minimal-context

A pure closed-book "minimal-context" condition is interpretively ambiguous:
a strong model that abstains is exhibiting scientifically appropriate
behavior, not a memory failure. We replace it with `partial-source`, which
surfaces only the first source ID and the first half of the evidence text,
explicitly framed as a retrieval miss. This better simulates the realistic
failure mode and makes failure attributable to the model's response to
incomplete evidence rather than to the absence of all evidence.

## Primary monotonicity prediction

Across the two models, aggregated clear-or-partial failure counts (12 items
x 2 models = 24 responses per condition) are predicted to satisfy:

```
partial-source  >  gold-source  >  gold-memory-state
```

with each gap at least 4 failures wide. We do not predict strict monotonic
ordering at the level of individual capabilities or items.

## Per-capability predictions

- **Status correctness** (all categories): improves sharply from
  partial-source to gold-source as the model gets the full evidence picture;
  modest further improvement at gold-memory-state.

- **Provenance correctness**: low at partial-source (only one source ID
  shown, creating a risk of over-attribution to that one source); high at gold-source
  (all source IDs available); equal-or-slightly-degraded at gold-memory-state
  if the model paraphrases the structured record without re-emitting source
  IDs. This is the one place we expect possible non-monotonicity.

- **Contradiction preservation** (contradiction_resolution items, some
  cross_paper_synthesis, some uncertainty items): this is the **most
  diagnostic capability for partial-source**. Partial-source typically
  shows one side of a contradiction. The diagnostic failure is whether the
  model confidently completes from the visible side OR correctly notes the
  fragment may be one-sided. Expected: partial-source fails most (model
  collapses to visible side); gold-source partial (model has both sides but
  may flatten); gold-memory-state best (contradiction is structurally
  encoded in the `status` field).

- **Method/condition scope** (method_condition_constraints, some
  cross_paper_synthesis): expected to be the most stubborn failure mode.
  Even at gold-source, models are predicted to drop scope qualifications.
  Partial-source likely hides the scope qualifier entirely, inviting
  unscoped overgeneralization. Gold-memory-state should outperform
  gold-source on this capability because scope is a named structured field.

- **Uncertainty handling** (uncertainty_abstention items, especially
  `unanswerable` and `ambiguous`): partial-source should HELP if the model
  reasons "this fragment is incomplete, I should not commit". A model that
  emits a confident determinate answer at partial-source is exhibiting
  uncertainty collapse on top of capability failure. Gold-source and
  gold-memory-state should both produce well-qualified answers; failure
  here is the cleanest demonstration of "uncertainty collapse" per the
  paper's taxonomy.

## What would surprise us

Any of the following, if observed, should be reported and not spun:

1. Failure counts not monotonically decreasing as gold structure increases.
2. Both evaluated systems passing all 12 items at gold-memory-state. Indicates the
   reviewed item pool is too easy and 5DP's diagnostic value is on harder
   items only. Position paper framing should be adjusted accordingly.
3. Gold-source matching gold-memory-state on status, provenance, contradiction,
   scope, and uncertainty simultaneously across >=10 of 12 items per model.
   This is approximately the falsifying conjunction stated in Section 5.2 of
   the paper, scaled to this exhibit's size; it would weaken the position.
4. Partial-source performing comparably to gold-source. Indicates either the
   first-half evidence already contains the diagnostic content, or the model
   is correctly recognizing incompleteness across the board (good for the
   model, neutral for the position).

## Fallback paragraph if the exhibit shows null result

If failure rates are uniformly low or the monotonicity prediction fails, the
honest reporting is: "On this bounded expert-reviewed sample, 5DP's three
conditions did not produce the predicted ordering. Qualitative inspection of
items {ids} suggests the protocol's diagnostic value is concentrated on
harder, adversarial items not represented in the reviewed item pool. We
retain 5DP as a methodological proposal and defer empirical validation to a
future benchmark-grade dataset."

## Lock Record

The expectations above were recorded before model calls were executed. The corresponding run plan was created at `2026-05-04T03:25:19.492153+00:00` with fixed seed `43`, two non-GLM systems, three conditions, and 72 planned runs.
