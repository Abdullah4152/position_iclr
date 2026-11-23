# Source Arc Expert Review Decision

Date: 2026-05-02

Input files:

- `source_arc_tracker_verified.csv`
- `source_arc_verified_crossref_verification.csv`

## Decision

The first 30 source arcs are approved for the scientific-memory dry-run stage after
applying targeted expert-review corrections.

The set has healthy first-batch coverage:

| Category signal | Coverage |
|---|---:|
| Evolving hypothesis | 23/30 |
| Contradiction or apparent conflict | 14/30 |
| Method/condition dependency | 28/30 |
| Cross-paper synthesis | 27/30 |
| Uncertainty | 14/30 |
| Entity/relation recall controls | implicit in all |

Scaling note: contradiction and uncertainty are thinner than method/synthesis.
When expanding from 30 to 300 arcs, bias new arcs toward contradiction and
uncertainty so each appears in at least 40 percent of arcs.

## Corrections Applied Before Dry Run

- `cb02`: changed "agreement reanalysis" framing to "harmonization reanalysis";
  the 2015 paper improves concordance under harmonized metrics but does not
  fully overturn poor IC50-style reproducibility.
- `cb03`: added host-context note separating mouse mechanistic energy-harvest
  claims from human population Firmicutes/Bacteroidetes claims.
- `cb04`: tightened AlphaFold2 evidence: Akdel is broad; Ruff & Pappu is
  IDR-specific; Saldano is conformational diversity, not generic dynamics.
- `cb05`: changed from contradiction framing to tumor-cell versus immune-cell
  scoring scope.
- `cb07`: corrected Stuart 2019 to Seurat v3 anchor-based integration.
- `cb08`: added the EZH2 Y641 gain-of-function versus myeloid loss-of-function
  dichotomy.
- `ch01`: retained Hori 1994 but reworded it as a metal-series selectivity
  anchor, not the original Cu hydrocarbon-discovery paper.
- `ch06`: substituted Maeda 2006 JACS doi `10.1021/ja061696p` as the substantive
  visible-light overall water-splitting anchor; this arc requires a Crossref
  re-check before scaling.
- `ms03`: added the 4-probe/2-probe, Y-function, and dielectric-screening nuance.
- `ms04`: highlighted inadvertent Al incorporation from alumina crucibles.
- `ms06`: clarified ARPES versus transport as method-dependent evidence.
- `ms10`: clarified defect tolerance versus ion migration as separate mechanisms.

## Dry-Run Arcs

Use the expert-recommended strongest arcs first:

| Arc | Why it is useful |
|---|---|
| `cb01` | CRISPR off-target assay dependence; direct cross-assay comparisons. |
| `cb02` | Claim, critique, harmonization reanalysis dialectic. |
| `ch03` | Active-site identity revised across Cu-zeolite frameworks. |
| `ch07` | Fenton HO radical versus Fe(IV)=O with pH crossover. |
| `ms03` | Direct claim, critique, reply, follow-up exchange. |
| `ms04` | Hidden synthesis artifact in nominally pure LLZO. |
| `ms06` | ARPES versus transport method mismatch. |
| `ms10` | Apparent contradiction resolved by mechanism separation. |

This is an 8-arc dry run rather than the earlier generic 9-arc plan because the
expert review explicitly identified these as the highest-signal first tests.

## Outputs Generated

The reviewed source-arc tracker was converted into the final source-arc records included in this supplement:

- `data/source_arc_tracker_expert_reviewed.csv`
- `data/expert_reviewed_source_arcs_30.jsonl`

Dry-run manifests and large-scale generation scripts are not included in this position-paper supplement.

## Dry-Run Inspection Criteria

The follow-up dry run was designed to inspect:

- JSON validity;
- whether source references remain grounded;
- whether expert-review caveats are preserved;
- category balance across QA;
- evidence-span support;
- whether model annotation catches weak items.

