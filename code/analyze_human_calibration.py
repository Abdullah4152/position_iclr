#!/usr/bin/env python3
"""Analyse a completed human-calibration pass.

Usage:
    python analyze_human_calibration.py sheet_completed__alice.csv [sheet_completed__bob.csv]

Takes one or two filled copies of `grading_sheet_blinded.csv`, joins them to the judge's
held-out verdicts and to the deterministic gates in the released per-item scores, and
reports what the paper is missing: human-graded joint fidelity, the human-graded
compositional gap, per-component agreement with the judge, and the direct test of the
unsupported-claim gate's false-positive rate.

Prints a report; writes nothing unless --out is given.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(HERE, "..", "release")
CAL = os.path.join(REL, "human_calibration")

COMPONENTS = [
    ("human_answer_fidelity", "fidelity", "answer fidelity"),
    ("human_unsupported_claim", "unsupported", "unsupported claim"),
    ("human_contradiction_preserved", "contradiction", "contradiction preserved"),
    ("human_revision_preserved", "revision", "revision preserved"),
    ("human_scope_preserved", "scope", "scope preserved"),
    ("human_uncertainty_preserved", "uncertainty", "uncertainty preserved"),
    ("human_provenance_correct", "provenance", "provenance correct"),
]
PRESERVATION = ["human_contradiction_preserved", "human_revision_preserved",
                "human_scope_preserved", "human_uncertainty_preserved"]


def norm(v):
    """Normalise a cell to a comparable token."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "-", "--"):
        return None
    if s in ("true", "t", "y"):
        return "true"
    if s in ("false", "f", "n"):
        return "false"
    return s


def kappa(a, b):
    """Cohen's kappa over paired label lists."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None, 0, None
    n = len(pairs)
    obs = sum(1 for x, y in pairs if x == y) / n
    ca = collections.Counter(x for x, _ in pairs)
    cb = collections.Counter(y for _, y in pairs)
    exp = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    k = None if exp >= 1.0 else (obs - exp) / (1 - exp)
    return obs, n, k


def load_sheet(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    filled = [r for r in rows
              if any(norm(r.get(c)) is not None for c, _, _ in COMPONENTS)]
    return {r["blind_id"]: r for r in filled}, len(rows)


def load_key(path=None):
    p = path or os.path.join(CAL, "key_and_judge_verdicts.jsonl")
    out = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out[d["blind_id"]] = d
    return out


def load_deterministic():
    """answerability_correct and source recall: machine-computed, no human needed."""
    p = os.path.join(REL, "scores", "per_item_scores.csv")
    if not os.path.exists(p):
        p = os.path.join(HERE, "results", "per_item_scores.jsonl")
        if not os.path.exists(p):
            return {}
        out = {}
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    out[d["record_id"]] = d
        return out
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out[r["record_id"]] = r
    return out


def truthy(v):
    s = norm(v)
    return None if s is None else s in ("true", "yes", "1")


def human_phi(row, det):
    """Phi under human labels; answerability comes from the deterministic gate."""
    if norm(row.get("human_answer_fidelity")) != "correct":
        return False
    if truthy(row.get("human_unsupported_claim")) is not False:
        return False
    if norm(row.get("human_provenance_correct")) == "no":
        return False
    for c in PRESERVATION:
        if norm(row.get(c)) == "no":
            return False
    if det is not None:
        ac = norm(det.get("answerability_correct"))
        if ac in ("false", "0"):
            return False
    return True


def human_components_pass(row, det):
    """The component-style checks: retrieval, grounding, verdict."""
    if norm(row.get("human_answer_fidelity")) != "correct":
        return False
    if truthy(row.get("human_unsupported_claim")) is not False:
        return False
    if det is not None:
        try:
            sr = det.get("src_r")
            if sr not in (None, "", "None") and float(sr) < 0.5:
                return False
        except (TypeError, ValueError):
            pass
    return True


def pct(x):
    return "--" if x is None else "%.1f%%" % (100 * x)


def report(sheets, key, det):
    name0, rows0 = sheets[0]
    print("=" * 74)
    print("HUMAN CALIBRATION REPORT")
    print("=" * 74)
    for nm, rr in sheets:
        print("  %-28s %d rows graded" % (nm, len(rr)))
    print()

    # ---------------------------------------------------------------- coverage
    graded = [b for b in rows0 if b in key]
    print("Joined %d of %d graded rows to the key." % (len(graded), len(rows0)))
    missing_det = [b for b in graded if key[b]["record_id"] not in det]
    if missing_det:
        print("  note: %d rows have no deterministic gate data; answerability and source "
              "recall are skipped for those." % len(missing_det))
    by_cond = collections.Counter(key[b]["condition"] for b in graded)
    print("  by condition:", dict(by_cond))
    print()

    # ------------------------------------------------- agreement with the judge
    print("-" * 74)
    print("1. AGREEMENT WITH THE MODEL JUDGE")
    print("-" * 74)
    print("%-26s %7s %9s %8s" % ("component", "n", "agree", "kappa"))
    for hcol, jkey, label in COMPONENTS:
        A, B = [], []
        for b in graded:
            h = norm(rows0[b].get(hcol))
            j = norm(key[b]["judge"].get(jkey))
            if jkey == "unsupported":
                j = norm(key[b]["judge"].get("unsupported"))
            A.append(h)
            B.append(j)
        obs, n, k = kappa(A, B)
        print("%-26s %7d %9s %8s"
              % (label, n, pct(obs), "--" if k is None else "%.2f" % k))
    print()

    # ------------------------------------------------------------ joint fidelity
    print("-" * 74)
    print("2. JOINT FIDELITY  (paper reports 13.7% under the judge)")
    print("-" * 74)
    hp = [human_phi(rows0[b], det.get(key[b]["record_id"])) for b in graded]
    jp = [truthy(key[b]["judge"].get("joint_fidelity")) for b in graded]
    jp_known = [x for x in jp if x is not None]
    print("  human  Phi = %s   (n=%d)" % (pct(sum(hp) / len(hp)) if hp else "--", len(hp)))
    if jp_known:
        print("  judge  Phi = %s   (n=%d, this subset only)"
              % (pct(sum(jp_known) / len(jp_known)), len(jp_known)))
    agree = [(a, b) for a, b in zip(hp, jp) if b is not None]
    if agree:
        print("  agreement on the Phi verdict itself: %s"
              % pct(sum(1 for a, b in agree if a == b) / len(agree)))
    print()

    # ------------------------------------------------------ compositional gap
    print("-" * 74)
    print("3. COMPOSITIONAL GAP  (paper reports 19.8% under the judge)")
    print("-" * 74)
    base = [b for b in graded
            if human_components_pass(rows0[b], det.get(key[b]["record_id"]))]
    if base:
        fails = [b for b in base
                 if not human_phi(rows0[b], det.get(key[b]["record_id"]))]
        print("  responses passing every component-style check : %d" % len(base))
        print("  of those, failing joint fidelity              : %d  (%s)"
              % (len(fails), pct(len(fails) / len(base))))
        if fails:
            why = collections.Counter()
            for b in fails:
                r = rows0[b]
                for c in PRESERVATION:
                    if norm(r.get(c)) == "no":
                        why[c.replace("human_", "").replace("_preserved", "")] += 1
                if norm(r.get("human_provenance_correct")) == "no":
                    why["provenance"] += 1
                d = det.get(key[b]["record_id"])
                if d is not None and norm(d.get("answerability_correct")) in ("false", "0"):
                    why["answerability"] += 1
            print("  broken gates:", dict(why.most_common()))
    else:
        print("  no responses passed every component check in this subset.")
    print()

    # -------------------------------------- the unsupported-claim gate on trial
    print("-" * 74)
    print("4. THE UNSUPPORTED-CLAIM GATE  (judge fires on 44.2% of verbatim gold)")
    print("-" * 74)
    clean = [b for b in graded
             if norm(rows0[b].get("human_answer_fidelity")) == "correct"
             and truthy(rows0[b].get("human_unsupported_claim")) is False]
    if clean:
        fired = [b for b in clean if truthy(key[b]["judge"].get("unsupported")) is True]
        print("  rows a human called correct AND free of unsupported claims : %d" % len(clean))
        print("  of those, the judge flagged as unsupported                 : %d  (%s)"
              % (len(fired), pct(len(fired) / len(clean))))
        print()
        print("  Read this as the judge's false-positive rate on human-clean responses.")
        print("  If it is high, the gate inflates the compositional gap and the paper's")
        print("  gate-sensitivity analysis (Table 8) becomes the primary reading.")
    else:
        print("  no rows were graded correct-and-clean; cannot estimate.")
    print()

    # ------------------------------------------------------ inter-annotator
    if len(sheets) > 1:
        name1, rows1 = sheets[1]
        both = [b for b in rows0 if b in rows1]
        print("-" * 74)
        print("5. INTER-ANNOTATOR AGREEMENT  (%s vs %s, %d shared rows)"
              % (name0, name1, len(both)))
        print("-" * 74)
        print("%-26s %7s %9s %8s" % ("component", "n", "agree", "kappa"))
        for hcol, _, label in COMPONENTS:
            obs, n, k = kappa([norm(rows0[b].get(hcol)) for b in both],
                              [norm(rows1[b].get(hcol)) for b in both])
            print("%-26s %7d %9s %8s"
                  % (label, n, pct(obs), "--" if k is None else "%.2f" % k))
        hp0 = [human_phi(rows0[b], det.get(key[b]["record_id"])) for b in both if b in key]
        hp1 = [human_phi(rows1[b], det.get(key[b]["record_id"])) for b in both if b in key]
        if hp0:
            print("\n  Phi under grader A: %s   under grader B: %s"
                  % (pct(sum(hp0) / len(hp0)), pct(sum(hp1) / len(hp1))))
        print()

    print("=" * 74)
    print("Absolute levels in the paper are judge-relative. Whatever these numbers say,")
    print("report them: a calibration pass that only confirms is not a calibration pass.")
    print("=" * 74)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="+", help="one or two completed grading sheets (CSV)")
    ap.add_argument("--out", help="also write the report to this file")
    ap.add_argument("--key", help="key file the sheets were graded against (default: the "
                                  "current release key; pass the frozen copy for a finished pass)")
    args = ap.parse_args()

    if len(args.sheets) > 2:
        ap.error("at most two sheets (one per grader)")

    key = load_key(args.key)
    det = load_deterministic()
    if not det:
        print("warning: per-item scores not found; answerability and source-recall gates "
              "will be skipped.\n", file=sys.stderr)

    sheets = []
    for p in args.sheets:
        rows, total = load_sheet(p)
        if not rows:
            ap.error("%s has no filled rows" % p)
        sheets.append((os.path.basename(p), rows))

    if args.out:
        import io as _io
        buf = _io.StringIO()
        stdout = sys.stdout
        sys.stdout = buf
        try:
            report(sheets, key, det)
        finally:
            sys.stdout = stdout
        open(args.out, "w", encoding="utf-8").write(buf.getvalue())
        print(buf.getvalue())
        print("written to", args.out)
    else:
        report(sheets, key, det)


if __name__ == "__main__":
    main()
