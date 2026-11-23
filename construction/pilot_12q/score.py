#!/usr/bin/env python3
"""score.py -- Reference scoring script for the scientific-memory diagnostic study.

Implements the metrics named in Section 5.2 of the paper "Scientific Memory
Is Not Chat History":

  - Status accuracy
  - Source-ID precision / recall / F1
  - Scope-slot F1   (method_slots plus condition_slots, set-based)
  - Revision-event accuracy   (over items whose gold category is
                                temporal_claim_revision)
  - Answerability accuracy
  - Abstention precision / recall   (positive class = "unanswerable")
  - Selective risk-coverage   (coverage and error rate over answered items)
  - Contradiction preservation rate   (requires human rubric input)
  - Scope-correctness rate            (requires human rubric input)

The script is pure-stdlib Python 3 (no external dependencies).

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------

  Audit the released diagnostic-study artifacts:

    python score.py audit \\
        --gold      scoring_reference_by_question.csv \\
        --responses visible_responses_blinded.csv \\
        --audit     response_audit_sanitized.jsonl

  Score a system's structured predictions against the gold reference:

    python score.py compute \\
        --gold        scoring_reference_by_question.csv \\
        --predictions my_predictions.jsonl \\
        [--by category|condition|model|none]

------------------------------------------------------------------------------
PREDICTIONS FORMAT  (JSONL, one object per question_id)
------------------------------------------------------------------------------

  {
    "question_id": "scientific_memory_chemistry_0001_q03",
    "model":       "my-system-v1",          // optional, used for grouping
    "condition":   "gold-source",            // optional, one of
                                             //   {online, offline, gold-source,
                                             //    gold-memory-state, gold-evidence,
                                             //    partial-source}
    "predicted_answerability": "answerable", // "answerable" | "unanswerable"
    "predicted_status":        "revised_by_later_evidence",  // exact string match
                                                            //   against expected_status
    "predicted_source_ids":    ["ch01_p2", "ch01_p3"],
    "predicted_method_slots":  ["assay", "synthesis-route"],
    "predicted_condition_slots": ["pH", "ligand"],

    // Optional human rubric fields (set to null when not graded).
    // These are required for the rubric-dependent metrics; without them
    // the corresponding metric is reported as N/A.
    "human_contradiction_preserved": null,   // true | false | null
    "human_scope_correct":           null,   // true | false | null
    "human_uncertainty_correct":     null    // true | false | null
  }

Exact-match comparison is used for status because expected_status is drawn
from a small controlled vocabulary in the gold reference.  Source-ID and
slot comparisons are set-based.  All metrics gracefully skip items for
which the relevant prediction field is missing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


# ----------------------------------------------------------------------------
# I/O helpers
# ----------------------------------------------------------------------------

def load_gold(path: Path) -> dict[str, dict]:
    """Load scoring_reference_by_question.csv keyed by question_id.

    Source IDs are stored pipe-separated in the gold CSV; we split them.
    """
    gold: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row["question_id"].strip()
            if not qid:
                continue
            row["source_ids_set"] = {
                s.strip() for s in row.get("source_ids", "").split("|") if s.strip()
            }
            gold[qid] = row
    return gold


def load_predictions(path: Path) -> list[dict]:
    """Load a JSONL predictions file. Each line is one prediction object."""
    preds: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                preds.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"[score.py] malformed JSON on line {ln} of {path}: {e}")
    return preds


def load_audit(path: Path) -> dict[str, dict]:
    """Load response_audit_sanitized.jsonl keyed by blind_id."""
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            out[obj["blind_id"]] = obj
    return out


# ----------------------------------------------------------------------------
# Metric primitives
# ----------------------------------------------------------------------------

def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def prf(predicted: set, gold: set) -> tuple[float, float, float]:
    """Set-based precision / recall / F1."""
    if not predicted and not gold:
        return 1.0, 1.0, 1.0
    tp = len(predicted & gold)
    p = safe_div(tp, len(predicted))
    r = safe_div(tp, len(gold))
    f = safe_div(2 * p * r, p + r) if (p + r) else 0.0
    return p, r, f


def macro_average(triples: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not triples:
        return 0.0, 0.0, 0.0
    n = len(triples)
    return (
        sum(t[0] for t in triples) / n,
        sum(t[1] for t in triples) / n,
        sum(t[2] for t in triples) / n,
    )


# ----------------------------------------------------------------------------
# Per-item scoring against the gold reference
# ----------------------------------------------------------------------------

def score_item(pred: dict, gold_row: dict) -> dict:
    """Score one prediction against its gold row. Returns a dict of per-item
    flags and counts that aggregate cleanly across items.
    """
    out: dict[str, Any] = {
        "question_id": pred["question_id"],
        "category":    gold_row.get("category", ""),
        "domain":      gold_row.get("domain", ""),
        "model":       pred.get("model"),
        "condition":   pred.get("condition"),
    }

    # --- Answerability -------------------------------------------------------
    gold_ans = (gold_row.get("answerability") or "").strip().lower()
    pred_ans = (pred.get("predicted_answerability") or "").strip().lower()
    if pred_ans:
        out["answerability_correct"] = (pred_ans == gold_ans)
    else:
        out["answerability_correct"] = None

    # --- Status (exact match against expected_status) ------------------------
    gold_status = (gold_row.get("expected_status") or "").strip()
    pred_status = (pred.get("predicted_status") or "").strip()
    if pred_status:
        out["status_correct"] = (pred_status == gold_status)
    else:
        out["status_correct"] = None

    # --- Source-ID set comparison -------------------------------------------
    gold_src: set = gold_row.get("source_ids_set", set())
    pred_src_list = pred.get("predicted_source_ids")
    if pred_src_list is not None:
        pred_src = {s.strip() for s in pred_src_list if isinstance(s, str) and s.strip()}
        out["source_prf"] = prf(pred_src, gold_src)
    else:
        out["source_prf"] = None

    # --- Scope slots (method plus condition slot names, set-based) ----------
    gold_method = _slot_keys(gold_row.get("method_slots", ""))
    gold_cond   = _slot_keys(gold_row.get("condition_slots", ""))
    gold_scope  = gold_method | gold_cond

    pred_method = pred.get("predicted_method_slots")
    pred_cond   = pred.get("predicted_condition_slots")
    if pred_method is not None or pred_cond is not None:
        pred_scope = set(pred_method or []) | set(pred_cond or [])
        out["scope_prf"] = prf(pred_scope, gold_scope)
    else:
        out["scope_prf"] = None

    # --- Revision-event accuracy --------------------------------------------
    # Only meaningful for items whose gold category targets revision.
    out["is_revision_item"] = (out["category"] == "temporal_claim_revision")
    if out["is_revision_item"] and pred_status:
        out["revision_correct"] = (pred_status == gold_status)
    else:
        out["revision_correct"] = None

    # --- Human rubric pass-throughs -----------------------------------------
    out["contradiction_preserved"] = pred.get("human_contradiction_preserved")
    out["scope_human_correct"]     = pred.get("human_scope_correct")
    out["uncertainty_correct"]     = pred.get("human_uncertainty_correct")

    return out


def _slot_keys(slot_field: str) -> set[str]:
    """Gold method_slots / condition_slots are stored as JSON-ish dict
    strings (sometimes '{}'). We treat the keys as the slot vocabulary.
    """
    if not slot_field:
        return set()
    try:
        obj = json.loads(slot_field)
        if isinstance(obj, dict):
            return set(obj.keys())
        if isinstance(obj, list):
            return set(str(x) for x in obj)
    except (json.JSONDecodeError, TypeError):
        pass
    return set()


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------

def aggregate(items: list[dict]) -> dict:
    """Aggregate per-item scores into the metric set named in Section 5.2."""
    n = len(items)
    if n == 0:
        return {"n_items": 0}

    # --- Accuracies (skip None) ---------------------------------------------
    def acc(field: str) -> tuple[float, int]:
        vals = [x[field] for x in items if x[field] is not None]
        if not vals:
            return float("nan"), 0
        return sum(1 for v in vals if v) / len(vals), len(vals)

    status_acc, n_status = acc("status_correct")
    ans_acc,    n_ans    = acc("answerability_correct")

    # Revision-event accuracy is computed only over revision-targeted items.
    rev_items = [x for x in items if x["is_revision_item"] and x["revision_correct"] is not None]
    if rev_items:
        rev_acc = sum(1 for x in rev_items if x["revision_correct"]) / len(rev_items)
    else:
        rev_acc = float("nan")

    # --- Source-ID PRF (macro) ---------------------------------------------
    src_triples = [x["source_prf"] for x in items if x["source_prf"] is not None]
    src_p, src_r, src_f = macro_average(src_triples)

    # --- Scope-slot F1 (macro) ---------------------------------------------
    scope_triples = [x["scope_prf"] for x in items if x["scope_prf"] is not None]
    scope_p, scope_r, scope_f = macro_average(scope_triples)

    # --- Abstention precision / recall (positive = unanswerable) -----------
    # Treat predicted abstention as positive class.
    tp = fp = fn = tn = 0
    for x in items:
        if x["answerability_correct"] is None:
            continue
        # Re-derive labels by walking back through the comparison fields.
        # answerability_correct is True iff pred matches gold; we need the
        # underlying labels, so we attach them earlier — pull from items[i].
        gold_pos = x.get("_gold_unanswerable", False)
        pred_pos = x.get("_pred_unanswerable")
        if pred_pos is None:
            continue
        if   pred_pos and gold_pos:        tp += 1
        elif pred_pos and not gold_pos:    fp += 1
        elif not pred_pos and gold_pos:    fn += 1
        else:                              tn += 1
    abst_p = safe_div(tp, tp + fp)
    abst_r = safe_div(tp, tp + fn)

    # --- Selective risk-coverage -------------------------------------------
    # Coverage = fraction of items the system answered (predicted answerable).
    # Risk    = error rate among answered items, where "error" means the
    #           gold answer was unanswerable (system should have abstained).
    answerability_items = [x for x in items if x.get("_pred_unanswerable") is not None]
    answered = [x for x in answerability_items if x.get("_pred_unanswerable") is False]
    coverage = safe_div(len(answered), len(answerability_items))
    if answered:
        # An "error" within answered items is one whose gold says unanswerable.
        risk = sum(1 for x in answered if x.get("_gold_unanswerable")) / len(answered)
    else:
        risk = float("nan")

    # --- Rubric-dependent rates --------------------------------------------
    def rate(field: str) -> tuple[float, int]:
        vals = [x[field] for x in items if x[field] is not None]
        if not vals:
            return float("nan"), 0
        return sum(1 for v in vals if v) / len(vals), len(vals)

    contra_rate, n_contra = rate("contradiction_preserved")
    human_scope_rate, n_hscope = rate("scope_human_correct")
    uncert_rate, n_uncert = rate("uncertainty_correct")

    return {
        "n_items":                       n,
        "status_accuracy":               (status_acc, n_status),
        "answerability_accuracy":        (ans_acc, n_ans),
        "revision_event_accuracy":       (rev_acc, len(rev_items)),
        "source_id_precision":           src_p,
        "source_id_recall":              src_r,
        "source_id_f1":                  src_f,
        "scope_slot_precision":          scope_p,
        "scope_slot_recall":             scope_r,
        "scope_slot_f1":                 scope_f,
        "abstention_precision":          abst_p,
        "abstention_recall":             abst_r,
        "selective_coverage":            coverage,
        "selective_risk":                risk,
        "contradiction_preservation_rate": (contra_rate, n_contra),
        "scope_correctness_rate":        (human_scope_rate, n_hscope),
        "uncertainty_correctness_rate":  (uncert_rate, n_uncert),
    }


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def fmt_pair(value: tuple[float, int] | float) -> str:
    if isinstance(value, tuple):
        v, n = value
        if n == 0 or v != v:                 # NaN check
            return "  N/A    (n=0)"
        return f"{v:6.3f}  (n={n})"
    if value != value:                       # NaN
        return "  N/A"
    return f"{value:6.3f}"


def print_aggregate(label: str, agg: dict) -> None:
    print(f"\n=== {label}  (items: {agg['n_items']}) ===")
    if agg["n_items"] == 0:
        return
    rows = [
        ("Status accuracy",                  agg["status_accuracy"]),
        ("Answerability accuracy",           agg["answerability_accuracy"]),
        ("Revision-event accuracy",          agg["revision_event_accuracy"]),
        ("Source-ID precision",              agg["source_id_precision"]),
        ("Source-ID recall",                 agg["source_id_recall"]),
        ("Source-ID F1",                     agg["source_id_f1"]),
        ("Scope-slot precision",             agg["scope_slot_precision"]),
        ("Scope-slot recall",                agg["scope_slot_recall"]),
        ("Scope-slot F1",                    agg["scope_slot_f1"]),
        ("Abstention precision",             agg["abstention_precision"]),
        ("Abstention recall",                agg["abstention_recall"]),
        ("Selective coverage",               agg["selective_coverage"]),
        ("Selective risk (among answered)",  agg["selective_risk"]),
        ("Contradiction preservation rate",  agg["contradiction_preservation_rate"]),
        ("Scope-correctness rate (human)",   agg["scope_correctness_rate"]),
        ("Uncertainty-correctness rate",     agg["uncertainty_correctness_rate"]),
    ]
    width = max(len(name) for name, _ in rows)
    for name, val in rows:
        print(f"  {name.ljust(width)}  :  {fmt_pair(val)}")


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------

def cmd_audit(args: argparse.Namespace) -> int:
    gold      = load_gold(Path(args.gold))
    audit     = load_audit(Path(args.audit))

    with Path(args.responses).open(encoding="utf-8-sig", newline="") as f:
        responses = list(csv.DictReader(f))

    missing_meta = [r["blind_id"] for r in responses if r["blind_id"] not in audit]
    non_scored = []
    for r in responses:
        meta = audit.get(r["blind_id"], {})
        response_text = (r.get("model_response") or "").strip()
        status = (meta.get("status") or "").strip().lower()
        if status == "not_scored" or response_text.startswith("NOT_SCORED"):
            non_scored.append(r["blind_id"])
    scored_visible = len(responses) - len(non_scored)

    print("=== Released-data audit ===")
    print(f"Gold reference items    : {len(gold)}")
    print(f"Response rows           : {len(responses)}")
    print(f"Scored visible responses: {scored_visible}")
    print(f"Non-scored markers      : {len(non_scored)}")
    print(f"Audit-metadata records  : {len(audit)}")
    if non_scored:
        print(f"Non-scored blind_ids    : {', '.join(sorted(non_scored))}")
    if missing_meta:
        print(f"WARNING: {len(missing_meta)} response row(s) lack audit metadata.")

    # Per-condition x per-model coverage matrix.
    by_cond_model: Counter = Counter()
    for r in responses:
        meta = audit.get(r["blind_id"])
        if not meta:
            continue
        by_cond_model[(meta["condition"], meta["model"])] += 1

    print("\nResponses by (condition, model):")
    for (cond, model), count in sorted(by_cond_model.items()):
        print(f"  {cond:22s}  {model:48s}  n={count}")

    domains = Counter(r["domain"] for r in responses)
    print("\nResponses by domain:")
    for d, c in sorted(domains.items()):
        print(f"  {d:22s}  n={c}")

    categories = Counter(r["category"] for r in responses)
    print("\nResponses by capability category:")
    for cat, c in sorted(categories.items()):
        print(f"  {cat:32s}  n={c}")

    # Sanity: every response should reference a known gold question.
    missing = [r["blind_id"] for r in responses if r["question_id"] not in gold]
    if missing:
        print(f"\nWARNING: {len(missing)} responses reference unknown question_ids.")
    else:
        print("\nAll response question_ids resolve to gold reference.")

    return 1 if (missing or missing_meta) else 0


def cmd_compute(args: argparse.Namespace) -> int:
    gold  = load_gold(Path(args.gold))
    preds = load_predictions(Path(args.predictions))

    # Score each prediction.
    scored: list[dict] = []
    skipped: list[str] = []
    for p in preds:
        qid = p.get("question_id")
        if qid not in gold:
            skipped.append(qid or "<missing question_id>")
            continue
        item = score_item(p, gold[qid])

        # Stash raw labels for abstention / selective-risk math.
        gold_unans = (gold[qid].get("answerability", "").strip().lower() == "unanswerable")
        pred_ans = (p.get("predicted_answerability", "") or "").strip().lower()
        pred_unans = None
        if pred_ans in {"answerable", "unanswerable"}:
            pred_unans = (pred_ans == "unanswerable")
        item["_gold_unanswerable"] = gold_unans
        item["_pred_unanswerable"] = pred_unans
        scored.append(item)

    if skipped:
        print(f"NOTE: skipped {len(skipped)} prediction(s) with unknown question_ids.")

    # --- Always print overall aggregate ------------------------------------
    print_aggregate("OVERALL", aggregate(scored))

    # --- Optional grouping --------------------------------------------------
    if args.by != "none":
        groups: dict[str, list[dict]] = defaultdict(list)
        for x in scored:
            key = x.get(args.by) or "<unspecified>"
            groups[key].append(x)
        for key in sorted(groups):
            print_aggregate(f"BY {args.by.upper()} = {key}", aggregate(groups[key]))

    return 0


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="score.py",
        description="Reference scoring for the scientific-memory diagnostic study.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="Audit released diagnostic-study artifacts.")
    p_audit.add_argument("--gold",      required=True, help="scoring_reference_by_question.csv")
    p_audit.add_argument("--responses", required=True, help="visible_responses_blinded.csv")
    p_audit.add_argument("--audit",     required=True, help="response_audit_sanitized.jsonl")
    p_audit.set_defaults(func=cmd_audit)

    p_compute = sub.add_parser("compute", help="Compute Section 5.2 metrics over predictions.")
    p_compute.add_argument("--gold",        required=True, help="scoring_reference_by_question.csv")
    p_compute.add_argument("--predictions", required=True, help="predictions JSONL (see header docstring)")
    p_compute.add_argument("--by", default="none",
                           choices=["none", "category", "condition", "model", "domain"],
                           help="optional grouping for breakdown reports")
    p_compute.set_defaults(func=cmd_compute)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
