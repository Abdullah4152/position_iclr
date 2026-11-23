# Item-level provenance for the selected evaluation set

One row per item in the 160-item evaluation set: the evidence arc and source papers
it came from, the expert's decision and labels for it, whether the expert's corrected
gold answer was used, and how many graded responses the release carries for it.

## Files

- `item_provenance_map.csv` / `.json` -- the map, one row per item.
- `source_arcs_used.json` -- the 30 evidence arcs those items come from, with the
  source papers each arc cites and the items drawn from it.
- `expert_review_records_selected.csv` -- the expert decision, labels, rationale and
  notes for each selected item.

## Composition

- Decisions: {'accept': 67, 'revise': 93}
- Items scored against an expert-corrected gold answer: 3
- Domains: {'chemistry': 54, 'computational_biology': 51, 'materials_science': 55}

## What this is not

These files are derived from the built evaluation set, so they cover the **selected**
items only. The full candidate pool, the complete expert-review sample, the annotation
guidelines, and the source-arc collection records are separate artifacts from the
original construction audit and are provided under `construction/audit/`.
Each item carries one expert decision; there is no second-expert pass, so no
inter-expert agreement can be computed from these files.
