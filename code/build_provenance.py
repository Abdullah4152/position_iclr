#!/usr/bin/env python3
"""Build the item-level provenance map for the selected evaluation set.

The reproducibility statement promises "an item-level provenance map for the selected
evaluation set": for each of the 160 items, where it came from (evidence arc, source
papers), what the expert decided about it, whether the expert's corrected gold answer was
used, and how much graded evidence the release carries for it.

Everything here is read from data/items.json (the built evaluation set, which retains the
expert-review fields) and results/per_item_scores.jsonl. Writes into provenance/:
  item_provenance_map.csv / .json   one row per selected item
  source_arcs_used.json             the evidence arcs the selected items come from
  expert_review_records_selected.csv  expert decision, labels, rationale and notes
  README.md                         what each file is, and what it is not
"""
from __future__ import annotations

import collections
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "provenance")

FIELDS = [
    "question_id", "dialogue_id", "source_arc_id", "arc_title", "domain",
    "category_used", "expert_category_label", "category_relabelled",
    "answerability_used", "expert_answerability_label", "answerability_relabelled",
    "expert_item_decision", "expert_gold_answer_correctness", "expert_evidence_support",
    "gold_answer_source", "gold_status", "n_gold_source_ids", "gold_source_ids",
    "n_gold_method_slots", "n_gold_condition_slots", "primary_failure_mode",
    "requires_cross_session_memory", "requires_cross_paper_reasoning",
    "n_source_papers", "source_paper_ids", "source_titles", "transcript_sessions",
    "conditions_evaluated", "n_graded_responses",
]


def as_list(v):
    """items.json stores some multi-valued fields pipe-delimited rather than as lists."""
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split("|") if x.strip()]
    return list(v)


def main():
    items = json.load(open(os.path.join(HERE, "data", "items.json"), encoding="utf-8"))

    conds = collections.defaultdict(set)
    graded = collections.Counter()
    scores = os.path.join(HERE, "results", "per_item_scores.jsonl")
    if os.path.exists(scores):
        for line in open(scores, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            q = r.get("question_id")
            if r.get("study") == "main" and r.get("format") == "structured":
                conds[q].add(r.get("condition"))
            if r.get("judged") or r.get("joint_fidelity") is not None:
                graded[q] += 1

    LADDER = ["closed_book", "offline_retrieval", "online_history",
              "gold_source", "gold_memory_state", "gold_evidence"]
    SHORT = dict(zip(LADDER, ["D1", "D2", "D3", "D4", "D5", "D6"]))

    rows = []
    for it in items:
        q = it["question_id"]
        corrected = bool((it.get("expert_corrected_gold_answer") or "").strip())
        rows.append({
            "question_id": q,
            "dialogue_id": it.get("dialogue_id"),
            "source_arc_id": it.get("source_arc_id"),
            "arc_title": it.get("arc_title"),
            "domain": it.get("domain"),
            "category_used": it.get("category"),
            "expert_category_label": it.get("expert_category_label"),
            "category_relabelled": it.get("category") != it.get("expert_category_label"),
            "answerability_used": it.get("answerability"),
            "expert_answerability_label": it.get("expert_answerability_label"),
            "answerability_relabelled": it.get("answerability") != it.get("expert_answerability_label"),
            "expert_item_decision": it.get("expert_item_decision"),
            "expert_gold_answer_correctness": it.get("expert_gold_answer_correctness"),
            "expert_evidence_support": it.get("expert_evidence_support"),
            "gold_answer_source": "expert_corrected" if corrected else "original_reviewed",
            "gold_status": it.get("gold_status"),
            "n_gold_source_ids": len(as_list(it.get("gold_source_ids"))),
            "gold_source_ids": "|".join(as_list(it.get("gold_source_ids"))),
            "n_gold_method_slots": len(it.get("gold_method_slots") or {}),
            "n_gold_condition_slots": len(it.get("gold_condition_slots") or {}),
            "primary_failure_mode": it.get("primary_failure_mode"),
            "requires_cross_session_memory": it.get("requires_cross_session_memory"),
            "requires_cross_paper_reasoning": it.get("requires_cross_paper_reasoning"),
            "n_source_papers": len(as_list(it.get("source_paper_ids"))),
            "source_paper_ids": "|".join(as_list(it.get("source_paper_ids"))),
            "source_titles": " | ".join(as_list(it.get("source_titles"))),
            "transcript_sessions": it.get("transcript_sessions"),
            "conditions_evaluated": " ".join(SHORT[c] for c in LADDER if c in conds.get(q, ())),
            "n_graded_responses": graded.get(q, 0),
        })
    rows.sort(key=lambda r: r["question_id"])

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "item_provenance_map.csv"), "w", encoding="utf-8",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(os.path.join(OUT, "item_provenance_map.json"), "w",
                         encoding="utf-8"), indent=1)

    # ---- the evidence arcs those items come from
    arcs = {}
    for it in items:
        a = it.get("source_arc_id")
        d = arcs.setdefault(a, {"source_arc_id": a, "arc_title": it.get("arc_title"),
                                "arc_core_claim": it.get("arc_core_claim"),
                                "domain": it.get("domain"), "items": [],
                                "source_paper_ids": [], "source_titles": []})
        d["items"].append(it["question_id"])
        for pid, t in zip(as_list(it.get("source_paper_ids")), as_list(it.get("source_titles"))):
            if pid not in d["source_paper_ids"]:
                d["source_paper_ids"].append(pid)
                d["source_titles"].append(t)
    for d in arcs.values():
        d["n_items"] = len(d["items"])
    json.dump([arcs[k] for k in sorted(arcs)],
              open(os.path.join(OUT, "source_arcs_used.json"), "w", encoding="utf-8"), indent=1)

    # ---- expert-review records for the selected items
    ER = ["question_id", "source_arc_id", "domain", "expert_item_decision",
          "expert_category_label", "expert_answerability_label",
          "expert_gold_answer_correctness", "expert_evidence_support",
          "expert_corrected_gold_answer", "expert_rationale", "expert_notes"]
    with open(os.path.join(OUT, "expert_review_records_selected.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ER, extrasaction="ignore")
        w.writeheader()
        for it in sorted(items, key=lambda x: x["question_id"]):
            w.writerow({k: it.get(k) for k in ER})

    dec = collections.Counter(r["expert_item_decision"] for r in rows)
    corr = sum(1 for r in rows if r["gold_answer_source"] == "expert_corrected")
    dom = collections.Counter(r["domain"] for r in rows)

    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write(
        "# Item-level provenance for the selected evaluation set\n\n"
        "One row per item in the %d-item evaluation set: the evidence arc and source papers\n"
        "it came from, the expert's decision and labels for it, whether the expert's corrected\n"
        "gold answer was used, and how many graded responses the release carries for it.\n\n"
        "## Files\n\n"
        "- `item_provenance_map.csv` / `.json` -- the map, one row per item.\n"
        "- `source_arcs_used.json` -- the %d evidence arcs those items come from, with the\n"
        "  source papers each arc cites and the items drawn from it.\n"
        "- `expert_review_records_selected.csv` -- the expert decision, labels, rationale and\n"
        "  notes for each selected item.\n\n"
        "## Composition\n\n"
        "- Decisions: %s\n"
        "- Items scored against an expert-corrected gold answer: %d\n"
        "- Domains: %s\n\n"
        "## What this is not\n\n"
        "These files are derived from the built evaluation set, so they cover the **selected**\n"
        "items only. The full candidate pool, the complete expert-review sample, the annotation\n"
        "guidelines, and the source-arc collection records are separate artifacts from the\n"
        "original construction audit and are provided under `construction/audit/`.\n"
        "Each item carries one expert decision; there is no second-expert pass, so no\n"
        "inter-expert agreement can be computed from these files.\n"
        % (len(rows), len(arcs), dict(dec), corr, dict(dom)))

    print("provenance/: %d items, %d arcs, decisions %s, expert-corrected gold %d"
          % (len(rows), len(arcs), dict(dec), corr))


if __name__ == "__main__":
    main()
