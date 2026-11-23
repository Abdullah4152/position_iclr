#!/usr/bin/env python3
"""Deeper analysis of the completed human-calibration pass, for the paper.

The quick report compares human numbers against the paper-wide judge figures. That is not
the fair comparison: the 120-row subset is stratified 20 per condition, so it includes D1
and D2 and sits below the paper-wide mean by construction. Everything here is computed
for humans AND for the judge on the SAME 120 rows, with item-level bootstrap intervals.

Writes results/human_calibration.json for make_tables.py to consume.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.join(HERE, "..", "release", "human_calibration")
# the annotators' completed sheets live in the source tree; release/ is rebuilt from scratch
RES = os.path.join(HERE, "data", "human_calibration_results")
BOOT = 2000
RNG = random.Random(20260914)

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
SHORT = {"closed_book": "D1", "offline_retrieval": "D2", "online_history": "D3",
         "gold_source": "D4", "gold_memory_state": "D5", "gold_evidence": "D6"}
PRES = ["contradiction", "revision", "scope", "uncertainty"]
COMP = ["fidelity", "unsupported", "contradiction", "revision", "scope", "uncertainty",
        "provenance"]
HCOL = {"fidelity": "human_answer_fidelity", "unsupported": "human_unsupported_claim",
        "contradiction": "human_contradiction_preserved",
        "revision": "human_revision_preserved", "scope": "human_scope_preserved",
        "uncertainty": "human_uncertainty_preserved",
        "provenance": "human_provenance_correct"}


def norm(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "-", "--", "none"):
        return None
    if s in ("true", "t", "y", "1"):
        return "true"
    if s in ("false", "f", "n", "0"):
        return "false"
    return s


def load_sheet(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["blind_id"]: {k: norm(r.get(c)) for k, c in HCOL.items()} for r in rows}


def load_key():
    # the key the annotators actually graded against, frozen with their sheets; the copy in
    # release/ is regenerated on every build and must not be the one used here
    out = {}
    with open(os.path.join(RES, "key_and_judge_verdicts_FROZEN.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out[d["blind_id"]] = d
    return out


def load_det():
    out = {}
    with open(os.path.join(HERE, "results", "per_item_scores.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out[d["record_id"]] = d
    return out


def judge_labels(k):
    j = k["judge"]
    return {"fidelity": norm(j.get("fidelity")),
            "unsupported": norm(j.get("unsupported")),
            "contradiction": norm(j.get("contradiction")),
            "revision": norm(j.get("revision")),
            "scope": norm(j.get("scope")),
            "uncertainty": norm(j.get("uncertainty")),
            "provenance": norm(j.get("provenance"))}


def phi(lab, det):
    """Joint fidelity from a label dict; answerability from the deterministic gate."""
    if lab["fidelity"] != "correct":
        return False
    if lab["unsupported"] != "false":
        return False
    if lab["provenance"] == "no":
        return False
    for c in PRES:
        if lab[c] == "no":
            return False
    if det is not None and det.get("answerability_correct") is False:
        return False
    return True


def comp_pass(lab, det):
    """Passes every component-style check: retrieval, grounding, verdict."""
    if lab["fidelity"] != "correct" or lab["unsupported"] != "false":
        return False
    if det is not None:
        sr = det.get("src_r")
        if sr is not None and sr < 0.5:
            return False
    return True


def boot_rate(vals_by_item):
    items = sorted(vals_by_item)
    flat = [v for q in items for v in vals_by_item[q]]
    if not flat:
        return None, None, None, 0
    obs = sum(flat) / len(flat)
    reps = []
    for _ in range(BOOT):
        s = [RNG.choice(items) for _ in items]
        v = [x for q in s for x in vals_by_item[q]]
        reps.append(sum(v) / len(v))
    reps.sort()
    return obs, reps[int(0.025 * BOOT)], reps[int(0.975 * BOOT)], len(flat)


def kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None, 0
    n = len(pairs)
    obs = sum(1 for x, y in pairs if x == y) / n
    ca = collections.Counter(x for x, _ in pairs)
    cb = collections.Counter(y for _, y in pairs)
    exp = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    return (None if exp >= 1 else (obs - exp) / (1 - exp)), n


def main():
    key = load_key()
    det = load_det()
    A = load_sheet(os.path.join(RES, "STUDENT_A.csv"))
    B = load_sheet(os.path.join(RES, "STUDENT_B.csv"))
    ids = sorted(b for b in A if b in B and b in key)
    out = {"n_rows": len(ids), "graders": 2}

    def D(b):
        return det.get(key[b]["record_id"])

    # ---------------------------------------------------------------- Phi, all three
    graders = {"human_A": A, "human_B": B,
               "judge": {b: judge_labels(key[b]) for b in ids}}
    # consensus: a response is human-correct on a gate only if BOTH graders say so
    cons = {}
    for b in ids:
        c = {}
        for k in COMP:
            a, bb = A[b][k], B[b][k]
            if k == "unsupported":
                c[k] = "false" if (a == "false" and bb == "false") else "true"
            elif k == "fidelity":
                c[k] = "correct" if (a == "correct" and bb == "correct") else \
                    ("incorrect" if (a == "incorrect" or bb == "incorrect") else "partial")
            else:
                c[k] = "no" if (a == "no" or bb == "no") else \
                    ("yes" if (a == "yes" or bb == "yes") else "na")
        cons[b] = c
    graders["human_consensus"] = cons

    phi_tab = {}
    for gname, labs in graders.items():
        byq = collections.defaultdict(list)
        for b in ids:
            byq[key[b]["question_id"]].append(1.0 if phi(labs[b], D(b)) else 0.0)
        m, lo, hi, n = boot_rate(byq)
        # per condition
        per = {}
        for c in LADDER:
            sub = [1.0 if phi(labs[b], D(b)) else 0.0 for b in ids if key[b]["condition"] == c]
            per[c] = (sum(sub) / len(sub)) if sub else None
        phi_tab[gname] = {"mean": m, "ci_lo": lo, "ci_hi": hi, "n": n, "by_condition": per}
    out["phi"] = phi_tab

    # ---------------------------------------------------------------- gap, all three
    gap_tab = {}
    for gname, labs in graders.items():
        base = [b for b in ids if comp_pass(labs[b], D(b))]
        byq = collections.defaultdict(list)
        broken = collections.Counter()
        for b in base:
            f = not phi(labs[b], D(b))
            byq[key[b]["question_id"]].append(1.0 if f else 0.0)
            if f:
                for c in PRES:
                    if labs[b][c] == "no":
                        broken[c] += 1
                if labs[b]["provenance"] == "no":
                    broken["provenance"] += 1
                d = D(b)
                if d is not None and d.get("answerability_correct") is False:
                    broken["answerability"] += 1
        m, lo, hi, n = boot_rate(byq)
        gap_tab[gname] = {"base": len(base), "fail": int(sum(x for v in byq.values() for x in v)),
                          "rate": m, "ci_lo": lo, "ci_hi": hi, "broken": dict(broken)}
    out["gap"] = gap_tab

    # ---------------------------------------------------- unsupported gate on trial
    # rows both humans call correct and clean; how often does the judge flag them?
    clean = [b for b in ids if cons[b]["fidelity"] == "correct" and cons[b]["unsupported"] == "false"]
    fired = [b for b in clean if graders["judge"][b]["unsupported"] == "true"]
    byq = collections.defaultdict(list)
    for b in clean:
        byq[key[b]["question_id"]].append(1.0 if b in fired else 0.0)
    m, lo, hi, n = boot_rate(byq)
    out["unsupported_fp"] = {"clean_n": len(clean), "judge_fired": len(fired),
                             "rate": m, "ci_lo": lo, "ci_hi": hi}
    # and the reverse: rows the judge calls clean that a human flags
    jclean = [b for b in ids if graders["judge"][b]["unsupported"] == "false"]
    hflag = [b for b in jclean if A[b]["unsupported"] == "true" or B[b]["unsupported"] == "true"]
    out["unsupported_fn"] = {"judge_clean_n": len(jclean), "human_flagged": len(hflag),
                             "rate": (len(hflag) / len(jclean)) if jclean else None}

    # ---------------------------------------------------------------- agreement
    agree = {}
    for k in COMP:
        kAJ, nAJ = kappa([A[b][k] for b in ids], [graders["judge"][b][k] for b in ids])
        kBJ, _ = kappa([B[b][k] for b in ids], [graders["judge"][b][k] for b in ids])
        kAB, _ = kappa([A[b][k] for b in ids], [B[b][k] for b in ids])
        agree[k] = {"A_vs_judge": kAJ, "B_vs_judge": kBJ, "A_vs_B": kAB, "n": nAJ}
    out["kappa"] = agree

    # ------------------------------------------------- direction of judge error
    # on each judged gate, is the judge harsher or more lenient than the humans?
    direction = {}
    for k in COMP:
        harsh = lenient = 0
        for b in ids:
            j, h = graders["judge"][b][k], cons[b][k]
            if j == h:
                continue
            if k == "fidelity":
                order = {"incorrect": 0, "partial": 1, "correct": 2}
                if order.get(j, 1) < order.get(h, 1):
                    harsh += 1
                else:
                    lenient += 1
            elif k == "unsupported":
                if j == "true" and h == "false":
                    harsh += 1
                elif j == "false" and h == "true":
                    lenient += 1
            else:
                if j == "no" and h != "no":
                    harsh += 1
                elif j != "no" and h == "no":
                    lenient += 1
        direction[k] = {"judge_harsher": harsh, "judge_more_lenient": lenient}
    out["direction"] = direction

    # ---------------------------------------------------------------- D4 vs D5
    branch = {}
    for gname, labs in graders.items():
        d4 = [1.0 if phi(labs[b], D(b)) else 0.0 for b in ids if key[b]["condition"] == "gold_source"]
        d5 = [1.0 if phi(labs[b], D(b)) else 0.0 for b in ids if key[b]["condition"] == "gold_memory_state"]
        branch[gname] = {"d4": sum(d4) / len(d4) if d4 else None, "n4": len(d4),
                         "d5": sum(d5) / len(d5) if d5 else None, "n5": len(d5)}
    out["branch_unpaired"] = branch

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "results", "human_calibration.json"), "w",
                        encoding="utf-8"), indent=1)

    # ---------------------------------------------------------------- print
    P = lambda x: "--" if x is None else "%.1f" % (100 * x)
    print("=" * 76)
    print("HUMAN CALIBRATION -- same 120 rows, humans and judge side by side")
    print("=" * 76)
    print("\nJOINT FIDELITY Phi (%%), item-level bootstrap 95%% CI")
    print("%-18s %7s %16s   " % ("grader", "Phi", "95% CI") + "  ".join("%5s" % SHORT[c] for c in LADDER))
    for g in ("human_A", "human_B", "human_consensus", "judge"):
        t = phi_tab[g]
        print("%-18s %7s [%5s, %5s]   " % (g, P(t["mean"]), P(t["ci_lo"]), P(t["ci_hi"]))
              + "  ".join("%5s" % P(t["by_condition"][c]) for c in LADDER))

    print("\nCOMPOSITIONAL GAP (%% of component-passing responses that fail Phi)")
    print("%-18s %6s %6s %7s %16s   broken gates" % ("grader", "base", "fail", "gap", "95% CI"))
    for g in ("human_A", "human_B", "human_consensus", "judge"):
        t = gap_tab[g]
        print("%-18s %6d %6d %7s [%5s, %5s]   %s"
              % (g, t["base"], t["fail"], P(t["rate"]), P(t["ci_lo"]), P(t["ci_hi"]), t["broken"]))

    u = out["unsupported_fp"]
    print("\nUNSUPPORTED-CLAIM GATE")
    print("  responses BOTH humans call correct and clean : %d" % u["clean_n"])
    print("  ...that the judge flagged as unsupported     : %d  = %s%% [%s, %s]"
          % (u["judge_fired"], P(u["rate"]), P(u["ci_lo"]), P(u["ci_hi"])))
    f = out["unsupported_fn"]
    print("  responses the judge calls clean              : %d" % f["judge_clean_n"])
    print("  ...that at least one human flagged           : %d  = %s%%" % (f["human_flagged"], P(f["rate"])))

    print("\nKAPPA")
    print("%-16s %10s %10s %10s" % ("component", "A vs judge", "B vs judge", "A vs B"))
    for k in COMP:
        a = agree[k]
        f2 = lambda x: "--" if x is None else "%.2f" % x
        print("%-16s %10s %10s %10s" % (k, f2(a["A_vs_judge"]), f2(a["B_vs_judge"]), f2(a["A_vs_B"])))

    print("\nDIRECTION OF JUDGE DISAGREEMENT (vs human consensus)")
    print("%-16s %14s %18s" % ("component", "judge harsher", "judge more lenient"))
    for k in COMP:
        d = direction[k]
        print("%-16s %14d %18d" % (k, d["judge_harsher"], d["judge_more_lenient"]))

    print("\nD4 vs D5 on this subset (20 per condition -- unpaired, thin)")
    for g in ("human_consensus", "judge"):
        t = branch[g]
        print("  %-16s D4=%s  D5=%s" % (g, P(t["d4"]), P(t["d5"])))
    print("\nwrote results/human_calibration.json")


if __name__ == "__main__":
    main()
