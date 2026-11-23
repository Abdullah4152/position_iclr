#!/usr/bin/env python3
"""Build a stratified, ready-to-grade calibration subset.

The reviews asked for a fully human-graded subset to calibrate absolute levels and to
serve as a gold reference for future judge development. We cannot supply human labels
ourselves, so we supply the next most useful thing: a blinded, stratified sample with a
filled-in grading protocol and an empty answer sheet, sized for one annotator-day, plus
the judge's own verdicts held out in a separate file so the grader is not anchored.
"""
from __future__ import annotations
import csv, json, os, random, collections

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "release", "human_calibration")
os.makedirs(OUT, exist_ok=True)
SEED = 20260914
N_PER_CONDITION = 20

items = {i["question_id"]: i for i in
         json.load(open(os.path.join(HERE, "data", "items.json"), encoding="utf-8"))}
rows = [json.loads(l) for l in
        open(os.path.join(HERE, "results", "per_item_scores.jsonl"), encoding="utf-8")]

responses = {}
for name in os.listdir(os.path.join(HERE, "raw")):
    if not name.startswith("responses_") or not name.endswith(".jsonl"):
        continue
    for line in open(os.path.join(HERE, "raw", name), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("raw"):
            responses[r["record_id"]] = r

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
rng = random.Random(SEED)

# stratify by condition, then spread over capability and system within each condition
pool = [r for r in rows if r.get("study") == "main" and r.get("format") == "structured"
        and r.get("joint_fidelity") is not None and r["record_id"] in responses]
chosen = []
for cond in LADDER:
    sub = [r for r in pool if r["condition"] == cond]
    bycat = collections.defaultdict(list)
    for r in sub:
        bycat[(r["category"], r["model"])].append(r)
    keys = sorted(bycat)
    rng.shuffle(keys)
    picked, i = [], 0
    while len(picked) < N_PER_CONDITION and any(bycat[k] for k in keys):
        k = keys[i % len(keys)]
        if bycat[k]:
            picked.append(bycat[k].pop())
        i += 1
    chosen.extend(picked)
rng.shuffle(chosen)

sheet_cols = ["blind_id", "question", "gold_answer", "gold_answerability", "gold_status",
              "gold_source_ids", "gold_method_slots", "gold_condition_slots", "evidence_text",
              "response", "human_answer_fidelity", "human_unsupported_claim",
              "human_contradiction_preserved", "human_revision_preserved",
              "human_scope_preserved", "human_uncertainty_preserved",
              "human_provenance_correct", "human_notes"]
key = []
with open(os.path.join(OUT, "grading_sheet_blinded.csv"), "w", encoding="utf-8",
          newline="") as f:
    wr = csv.DictWriter(f, fieldnames=sheet_cols)
    wr.writeheader()
    for n, r in enumerate(chosen, 1):
        it = items[r["question_id"]]
        resp = responses[r["record_id"]]
        parsed = resp.get("parsed") or {}
        text = parsed.get("answer") if isinstance(parsed.get("answer"), str) else (resp.get("raw") or "")
        extra = " ".join("[%s=%s]" % (k, parsed.get(k)) for k in
                         ("status", "answerability", "source_ids", "method_scope",
                          "condition_scope", "contradiction_present", "revision_occurred")
                         if parsed.get(k) not in (None, "", []))
        bid = "H%03d" % n
        wr.writerow({
            "blind_id": bid, "question": it["question"], "gold_answer": it["gold_final"],
            "gold_answerability": it["expert_answerability_label"],
            "gold_status": it["gold_status"],
            "gold_source_ids": "|".join(it["gold_source_ids"]),
            "gold_method_slots": json.dumps(it["gold_method_slots"]),
            "gold_condition_slots": json.dumps(it["gold_condition_slots"]),
            "evidence_text": it["evidence_text"],
            "response": (text + (" " + extra if extra else "")).strip(),
            "human_answer_fidelity": "", "human_unsupported_claim": "",
            "human_contradiction_preserved": "", "human_revision_preserved": "",
            "human_scope_preserved": "", "human_uncertainty_preserved": "",
            "human_provenance_correct": "", "human_notes": ""})
        key.append({"blind_id": bid, "record_id": r["record_id"],
                    "question_id": r["question_id"], "model": r["model"],
                    "condition": r["condition"], "category": r["category"],
                    "domain": r["domain"],
                    "judge": {k: r.get(k) for k in
                              ("fidelity", "unsupported", "contradiction", "revision", "scope",
                               "uncertainty", "provenance", "joint_fidelity")}})

with open(os.path.join(OUT, "key_and_judge_verdicts.jsonl"), "w", encoding="utf-8") as f:
    for k in key:
        f.write(json.dumps(k) + "\n")

protocol = """# Human calibration subset

%d responses, stratified %d per diagnostic condition and spread across capability categories
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
""" % (len(chosen), N_PER_CONDITION)
open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write(protocol)

print("wrote %d rows to release/human_calibration/ (%d per condition)"
      % (len(chosen), N_PER_CONDITION))
print("by condition:", dict(collections.Counter(r["condition"] for r in chosen)))
