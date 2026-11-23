# Scientific-Memory Source Arc Collection Plan

Frozen on: 2026-05-01

This document records the source-arc construction plan used before the
30-source-arc construction audit. A source arc is the seed for one multi-session
dialogue and its QA set. The released supplement includes the resulting
expert-reviewed 30-arc seed set and 450 candidate QA items; it does not release
the full future benchmark.

## Target

| Domain | Source arcs | Dialogues | QA target | Human-validated QA | Expert-validated QA |
|---|---:|---:|---:|---:|---:|
| Computational biology | 100 | 100 | 1,500 | 500 | 100 |
| Chemistry | 100 | 100 | 1,500 | 500 | 100 |
| Materials science | 100 | 100 | 1,500 | 500 | 100 |
| Total | 300 | 300 | 4,500 | 1,500 | 300 |

One accepted source arc should normally produce one dialogue and about 15 QA
items.

## Source Arc Definition

Each source arc should contain 3-5 connected papers, paper sections, datasets,
or public scientific records. The arc must support a research-memory challenge,
not just a static fact lookup.

Accept arcs that contain at least two of:

- evolving hypothesis;
- contradiction or apparent conflict;
- method or condition dependency;
- cross-paper synthesis opportunity;
- uncertainty or insufficient evidence;
- ordinary entity/relation recall controls.

## First Batch

Before scaling to 300 arcs, collect a high-confidence seed batch:

| Domain | First batch target |
|---|---:|
| Computational biology | 10 arcs |
| Chemistry | 10 arcs |
| Materials science | 10 arcs |

After these 30 arcs are inspected, generate a tiny dry run:

- 3 dialogues per domain;
- 15 QA items per dialogue;
- model annotation with two holdout models;
- manual spot check of evidence support.

Scale only after the dry run reveals no schema, evidence, or category-balance
problems.

## Collection Fields

Use `source_arc_tracker.csv` while collecting. Required fields:

- `arc_id`
- `domain`
- `status`
- `arc_title`
- `core_claim`
- `source_count`
- `paper_ids`
- `source_urls`
- `license_status`
- `redistributable_text`
- `has_hypothesis_update`
- `has_contradiction`
- `has_method_condition_scope`
- `has_cross_paper_synthesis`
- `has_uncertainty`
- `expected_qa_count`
- `curator`
- `notes`

## Status Values

- `candidate`
- `needs_license_check`
- `needs_domain_check`
- `accepted`
- `rejected`
- `generated`
- `validated`

## Domain Hints

Computational biology:

- assay-dependent claims;
- perturbation or intervention effects;
- cell-line or organism scope;
- mechanism claims revised by later evidence;
- open PMC sources where possible.

Chemistry:

- catalyst, substrate, solvent, temperature, base, or yield scope;
- synthesis route changes;
- side reactions or failed transfer conditions;
- mechanistic uncertainty;
- open-access papers and public reaction datasets where possible.

Materials science:

- composition, processing, annealing, morphology, measurement protocol, or
  structure-property claims;
- contradictory reported values;
- experimental versus computational disagreement;
- arXiv, open-access materials papers, and public benchmark references where
  possible.

## Rejection Rules

Reject an arc if:

- source licensing prevents even minimal evidence release;
- claims require private full text to verify;
- the arc is answerable from generic domain knowledge;
- the source relation is too shallow for 10-15 QA items;
- contradiction is artificial or only caused by loose wording;
- method/condition scope cannot be identified;
- source metadata is incomplete.
