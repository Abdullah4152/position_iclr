#!/usr/bin/env python3
"""Score the scientific-memory study and emit every number the paper reports.

  python analyze.py            # writes results/*.json and results/tables.tex
"""
from __future__ import annotations
import json, os, math, random, re, collections, statistics, glob, sys
import det_rules

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
BOOT = 2000
RNG = random.Random(20260913)

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
# The nested chain along which monotonicity is expected. D5 supplies the information
# state *instead of* the evidence text, so it is a branch rather than a rung of the chain.
CHAIN = ["closed_book", "offline_retrieval", "online_history", "gold_source", "gold_evidence"]
LADDER_LABEL = {
    "closed_book": "D1 closed book",
    "offline_retrieval": "D2 retrieval-restricted",
    "online_history": "D3 full history",
    "gold_source": "D4 gold source",
    "gold_memory_state": "D5 gold memory state",
    "gold_evidence": "D6 gold evidence",
}
MODEL_LABEL = {
    "openai/gpt-oss-20b": "GPT-OSS-20B",
    "nvidia/nemotron-3.5-lightning-30b-a3b": "Nemotron-3.5-Lightning-30B",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": "Nemotron-3-Nano-30B",
    "moonshotai/kimi-k3": "Kimi-K3",
    "mistralai/mistral-nemotron": "Mistral-Nemotron",
    "meta/llama-3.2-11b-vision-instruct": "Llama-3.2-11B",
}
CAP_LABEL = {
    "hypothesis_tracking": "Hypothesis tracking",
    "evidence_provenance": "Evidence provenance",
    "contradiction_resolution": "Contradiction preservation",
    "temporal_claim_revision": "Revision preservation",
    "method_condition_constraints": "Method/condition scope",
    "cross_paper_synthesis": "Synthesis",
    "uncertainty_abstention": "Uncertainty preservation",
    "entity_relation_recall_control": "Recall control",
}


# ---------------------------------------------------------------- loading
def attach_gold_flags(items):
    """Recover the gold contradiction/revision flags from the rendered D5 prompts,
    so the deterministic rules see exactly the record the systems were shown."""
    path = os.path.join(HERE, "data", "payload.jsonl")
    if not os.path.exists(path):
        return
    pat = re.compile(r"Information-state record:\n(\{.*?\n\})\n\n", re.S)
    for line in open(path, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("condition") != "gold_memory_state" or rec.get("format") != "structured":
            continue
        it = items.get(rec["question_id"])
        if it is None or "_contradiction_flag" in it:
            continue
        m = pat.search(rec.get("prompt", ""))
        if not m:
            continue
        try:
            r = json.loads(m.group(1))
        except Exception:
            continue
        it["_contradiction_flag"] = bool(r.get("contradiction_present"))
        it["_revision_flag"] = bool(r.get("revision_occurred"))


def load_items():
    items = {i["question_id"]: i for i in
             json.load(open(os.path.join(HERE, "data", "items.json"), encoding="utf-8"))}
    tp = os.path.join(HERE, "data", "transfer_items_built.json")
    if os.path.exists(tp):
        for i in json.load(open(tp, encoding="utf-8")):
            i["is_transfer"] = True
            items[i["question_id"]] = i
    attach_gold_flags(items)
    for i in items.values():
        i.setdefault("_contradiction_flag", False)
        i.setdefault("_revision_flag", False)
    return items


def load_jsonl(pattern):
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, pattern))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    return out


# ---------------------------------------------------------------- helpers
def norm_ids(v):
    if v is None:
        return set()
    if isinstance(v, str):
        v = re.split(r"[,\s;]+", v)
    out = set()
    for x in v:
        if not isinstance(x, str):
            continue
        for m in re.findall(r"\b(?:cb|ch|ms|ml|tc)\d\d_p\d\b", x.lower()):
            out.add(m)
    return out


def prf(pred, gold):
    if not gold:
        return (None, None, None)
    if not pred:
        return (0.0, 0.0, 0.0)
    tp = len(pred & gold)
    p = tp / len(pred)
    r = tp / len(gold)
    f = 2 * p * r / (p + r) if p + r else 0.0
    return (p, r, f)


CONTENT = re.compile(r"[a-z0-9]{4,}")


def scope_coverage(parsed, answer_text, item):
    """Fraction of gold scope slots whose key or value tokens surface in the response."""
    gold = {}
    gold.update(item.get("gold_method_slots") or {})
    gold.update(item.get("gold_condition_slots") or {})
    if not gold:
        return None
    hay = " ".join([
        answer_text or "",
        " ".join(map(str, (parsed or {}).get("method_scope") or []))
        if isinstance((parsed or {}).get("method_scope"), list) else str((parsed or {}).get("method_scope", "")),
        " ".join(map(str, (parsed or {}).get("condition_scope") or []))
        if isinstance((parsed or {}).get("condition_scope"), list) else str((parsed or {}).get("condition_scope", "")),
    ]).lower()
    hit = 0
    for k, v in gold.items():
        toks = set(CONTENT.findall(k.lower().replace("_", " ")))
        toks |= set(CONTENT.findall(str(v).lower()))
        toks = {t for t in toks if t not in ("specified", "dialogue", "implied", "explicitly",
                                             "quantified", "required", "reported")}
        if toks and any(t in hay for t in toks):
            hit += 1
    return hit / len(gold)


def answerability_of(parsed):
    if not parsed:
        return None
    a = parsed.get("answerability")
    if not isinstance(a, str):
        return None
    a = a.strip().lower()
    for k in ("unanswerable", "ambiguous", "answerable"):
        if k in a:
            return k
    return None


def boot_ci(values, stat=statistics.mean, n=BOOT):
    vals = [v for v in values if v is not None]
    if not vals:
        return (None, None, None)
    obs = stat(vals)
    reps = []
    m = len(vals)
    for _ in range(n):
        reps.append(stat([vals[RNG.randrange(m)] for _ in range(m)]))
    reps.sort()
    return (obs, reps[int(0.025 * n)], reps[int(0.975 * n)])


def boot_ci_grouped(groups, n=BOOT):
    """Item-level cluster bootstrap: groups maps item_id -> list of 0/1 values."""
    keys = [k for k, v in groups.items() if v]
    if not keys:
        return (None, None, None)
    flat = [x for k in keys for x in groups[k]]
    obs = sum(flat) / len(flat)
    reps = []
    m = len(keys)
    for _ in range(n):
        acc, cnt = 0.0, 0
        for _ in range(m):
            v = groups[keys[RNG.randrange(m)]]
            acc += sum(v)
            cnt += len(v)
        reps.append(acc / cnt if cnt else 0.0)
    reps.sort()
    return (obs, reps[int(0.025 * n)], reps[int(0.975 * n)])


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    if n == 0 or len(labels) < 2:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else None


FAILURE_VOCAB = ["hypothesis_drift", "unsupported_claim_recall", "evidence_source_confusion",
                 "contradiction_blindness", "outdated_claim_persistence",
                 "method_condition_mismatch", "uncertainty_collapse", "none"]


def norm_failure(label):
    """Map a judge-emitted failure label onto the taxonomy, tolerating typos."""
    if not isinstance(label, str):
        return None
    x = label.strip().lower().replace(" ", "_")
    if x in FAILURE_VOCAB:
        return x
    best, best_score = None, 0.0
    for v in FAILURE_VOCAB:
        a, b = set(x), set(v)
        score = len(a & b) / max(len(a | b), 1)
        if x[:6] == v[:6]:
            score += 0.5
        if score > best_score:
            best, best_score = v, score
    return best if best_score >= 0.6 else "other"


# ---------------------------------------------------------------- scoring
def build_rows(items):
    responses = {r["record_id"]: r for r in load_jsonl("responses_*.jsonl")}
    for r in load_jsonl("review_*.jsonl"):
        responses[r["record_id"]] = r
    judgments = collections.defaultdict(dict)
    for j in load_jsonl("judgments_*.jsonl"):
        if j.get("judgment"):
            judgments[j["target_record_id"]]["primary"] = j["judgment"]
    for j in load_jsonl("revjudge_*.jsonl"):
        if j.get("judgment"):
            judgments[j["target_record_id"]]["primary"] = j["judgment"]
    for j in load_jsonl("judgments2_*.jsonl"):
        if j.get("judgment"):
            judgments[j["target_record_id"]]["secondary"] = j["judgment"]

    rows = []
    for rid, r in responses.items():
        it = items.get(r["question_id"])
        if it is None:
            continue
        parsed = r.get("parsed") if isinstance(r.get("parsed"), dict) else None
        answer_text = (parsed or {}).get("answer") if parsed else (r.get("raw") or "")
        if not isinstance(answer_text, str):
            answer_text = json.dumps(answer_text)
        jd = judgments.get(rid, {})
        J = jd.get("primary") or {}
        gold_ids = set(x.lower() for x in it["gold_source_ids"])
        pred_ids = norm_ids((parsed or {}).get("source_ids")) if parsed else norm_ids(answer_text)
        p, rc, f1 = prf(pred_ids, gold_ids)
        pa = answerability_of(parsed)
        ga = it["expert_answerability_label"]

        def jf(k, default=None):
            v = J.get(k)
            return v.strip().lower() if isinstance(v, str) else (v if v is not None else default)

        fid = jf("answer_fidelity")
        unsup = J.get("unsupported_claim")
        unsup = bool(unsup) if isinstance(unsup, bool) else (
            str(unsup).strip().lower() == "true" if unsup is not None else None)
        row = {
            "record_id": rid,
            "question_id": r["question_id"],
            "model": r.get("model"),
            "condition": r.get("condition"),
            "format": r.get("format"),
            "study": r.get("study"),
            "replicate": r.get("replicate"),
            "category": it["category"],
            "domain": it["domain"],
            "gold_answerability": ga,
            "is_transfer": bool(it.get("is_transfer")),
            "parse_ok": parsed is not None,
            "resp_ok": bool(r.get("raw")),
            "src_p": p, "src_r": rc, "src_f1": f1,
            "pred_answerability": pa,
            "answerability_correct": (pa == ga) if pa else None,
            "abstained": (pa in ("unanswerable", "ambiguous")) if pa else None,
            "gold_abstain": ga in ("unanswerable", "ambiguous"),
            "status_correct": ((parsed or {}).get("status") == it["gold_status"]) if parsed else None,
            "scope_cov": scope_coverage(parsed, answer_text, it),
            "fidelity": fid,
            "unsupported": unsup,
            "contradiction": jf("contradiction_preserved"),
            "revision": jf("revision_preserved"),
            "scope": jf("scope_preserved"),
            "uncertainty": jf("uncertainty_preserved"),
            "provenance": jf("provenance_correct"),
            "failure_mode": norm_failure(J.get("primary_failure_mode")),
            "judged": bool(J),
            "answer_words": len((answer_text or "").split()),
            "det": det_rules.score_response(
                it, dict(parsed or {}, _norm_answerability=pa), answer_text,
                pred_ids, scope_coverage(parsed, answer_text, it)),
            "judge2": jd.get("secondary"),
            "answer_len": len(answer_text or ""),
        }
        # derived pass/fail flags
        if row["judged"]:
            pres = [row["contradiction"], row["revision"], row["scope"], row["uncertainty"]]
            row["preservation_ok"] = all(x != "no" for x in pres)
            row["n_preservation_applicable"] = sum(1 for x in pres if x in ("yes", "no"))
            row["n_preservation_failed"] = sum(1 for x in pres if x == "no")
            row["verdict_ok"] = fid in ("correct", "partial")
            row["answer_correct"] = fid == "correct"
            row["grounding_ok"] = (unsup is False)
            row["provenance_ok"] = row["provenance"] != "no"
            auto_ok = row["answerability_correct"] if row["format"] == "structured" else True
            row["joint_fidelity"] = bool(
                row["answer_correct"] and row["grounding_ok"] and row["provenance_ok"]
                and row["preservation_ok"] and (auto_ok is not False))
            # component-only ("additive") evaluation proxies
            row["comp_retrieval_ok"] = (row["src_r"] is None or row["src_r"] >= 0.5) \
                if row["format"] == "structured" else row["provenance_ok"]
            row["comp_grounding_ok"] = row["grounding_ok"]
            row["comp_verdict_ok"] = row["verdict_ok"]          # lenient: correct or partial
            row["comp_verdict_strict"] = row["answer_correct"]  # strict: correct only
            row["all_components_ok"] = bool(row["comp_retrieval_ok"] and row["comp_grounding_ok"]
                                            and row["comp_verdict_ok"])
            row["all_components_strict"] = bool(row["comp_retrieval_ok"]
                                                and row["comp_grounding_ok"]
                                                and row["comp_verdict_strict"])
            # a strict-gap failure must come from a dimension the component checks do not score
            row["gap_fail_strict"] = bool(
                row["all_components_strict"] and not (
                    row["preservation_ok"] and row["provenance_ok"]
                    and (row["answerability_correct"] is not False)))
        rows.append(row)
    return rows


# ---------------------------------------------------------------- reports
def rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def grouped(rows, key):
    g = collections.defaultdict(list)
    for r in rows:
        if r.get(key) is not None:
            g[r["question_id"]].append(1.0 if r[key] else 0.0)
    return g


def cell(rows, key):
    obs, lo, hi = boot_ci_grouped(grouped(rows, key))
    return {"n": sum(1 for r in rows if r.get(key) is not None),
            "n_items": len(set(r["question_id"] for r in rows if r.get(key) is not None)),
            "mean": obs, "ci_lo": lo, "ci_hi": hi}


def coverage_models(rows, study, min_frac=0.8):
    """Models with at least min_frac of the maximum per-model record count in a study."""
    c = collections.Counter(r["model"] for r in rows if r["study"] == study)
    if not c:
        return set()
    top = max(c.values())
    return {m for m, n in c.items() if n >= min_frac * top}


FRONTIER_MODELS = {"nvidia/nemotron-3-ultra-550b-a55b"}


def main():
    items = load_items()
    rows = build_rows(items)
    # the frontier-class check is analysed separately and never enters a pooled number
    frontier_rows = [r for r in rows if r["model"] in FRONTIER_MODELS]
    rows = [r for r in rows if r["model"] not in FRONTIER_MODELS]
    ABL_MODELS = (coverage_models(rows, "format_ablation")
                  & coverage_models(rows, "pushback")
                  & coverage_models(rows, "transfer"))
    main_rows = [r for r in rows if r["study"] == "main" and not r["is_transfer"]]
    judged = [r for r in main_rows if r["judged"]]
    rep = {}

    rep["coverage"] = {
        "responses_total": len(rows),
        "responses_by_study": dict(collections.Counter(r["study"] for r in rows)),
        "responses_ok": sum(1 for r in rows if r["resp_ok"]),
        "parse_rate_structured": rate([r for r in rows if r["format"] == "structured"], "parse_ok"),
        "judged_total": sum(1 for r in rows if r["judged"]),
        "models": sorted(set(r["model"] for r in rows if r["model"])),
        "ablation_models": sorted(ABL_MODELS),
        "main_cells": {},
    }
    for m in sorted(set(r["model"] for r in main_rows)):
        for c in LADDER:
            sub = [r for r in main_rows if r["model"] == m and r["condition"] == c]
            rep["coverage"]["main_cells"]["%s|%s" % (m, c)] = {
                "n": len(sub), "judged": sum(1 for r in sub if r["judged"])}

    # ---- Table: condition ladder x model, joint information-state fidelity
    ladder_tbl = {}
    for m in sorted(set(r["model"] for r in judged)):
        ladder_tbl[m] = {}
        for c in LADDER:
            sub = [r for r in judged if r["model"] == m and r["condition"] == c
                   and r["format"] == "structured"]
            ladder_tbl[m][c] = cell(sub, "joint_fidelity")
    for c in LADDER:
        sub = [r for r in judged if r["condition"] == c and r["format"] == "structured"]
        ladder_tbl.setdefault("ALL", {})[c] = cell(sub, "joint_fidelity")
    rep["ladder_joint_fidelity"] = ladder_tbl

    # ---- Same ladder for the component-style metrics
    comp_tbl = {}
    for c in LADDER:
        sub = [r for r in judged if r["condition"] == c and r["format"] == "structured"]
        comp_tbl[c] = {k: cell(sub, k) for k in
                       ["answer_correct", "verdict_ok", "grounding_ok", "provenance_ok",
                        "preservation_ok", "joint_fidelity", "all_components_ok",
                        "answerability_correct", "status_correct"]}
        comp_tbl[c]["src_f1"] = {"mean": rate(sub, "src_f1"),
                                 "n": sum(1 for r in sub if r["src_f1"] is not None)}
        comp_tbl[c]["scope_cov"] = {"mean": rate(sub, "scope_cov"),
                                    "n": sum(1 for r in sub if r["scope_cov"] is not None)}
    rep["ladder_components"] = comp_tbl

    # ---- Compositional gap: pass every component, fail the joint state
    def gap_block(strict):
        passkey = "all_components_strict" if strict else "all_components_ok"
        failfn = (lambda r: r["gap_fail_strict"]) if strict else (lambda r: not r["joint_fidelity"])
        out = {}
        for c in LADDER:
            sub = [r for r in judged if r["condition"] == c and r["format"] == "structured"
                   and r[passkey]]
            fails = [r for r in sub if failfn(r)]
            why = collections.Counter()
            for r in fails:
                for k in ("contradiction", "revision", "scope", "uncertainty"):
                    if r[k] == "no":
                        why[k] += 1
                if r["answerability_correct"] is False:
                    why["answerability"] += 1
                if r["provenance"] == "no":
                    why["provenance"] += 1
                if not strict and not r["answer_correct"]:
                    why["fidelity_partial"] += 1
            groups = collections.defaultdict(list)
            for r in sub:
                groups[r["question_id"]].append(1.0 if failfn(r) else 0.0)
            obs, lo, hi = boot_ci_grouped(groups)
            out[c] = {"n_component_pass": len(sub), "n_joint_fail": len(fails),
                      "rate": len(fails) / len(sub) if sub else None,
                      "ci_lo": lo, "ci_hi": hi, "reasons": dict(why)}
        allsub = [r for r in judged if r["format"] == "structured" and r[passkey]]
        allfail = [r for r in allsub if failfn(r)]
        groups = collections.defaultdict(list)
        for r in allsub:
            groups[r["question_id"]].append(1.0 if failfn(r) else 0.0)
        obs, lo, hi = boot_ci_grouped(groups)
        allwhy = collections.Counter()
        for c in LADDER:
            for k, v in out[c]["reasons"].items():
                allwhy[k] += v
        return {"by_condition": out,
                "overall": {"n_component_pass": len(allsub), "n_joint_fail": len(allfail),
                            "rate": len(allfail) / len(allsub) if allsub else None,
                            "ci_lo": lo, "ci_hi": hi, "reasons": dict(allwhy)}}

    rep["compositional_gap"] = gap_block(strict=True)
    rep["compositional_gap_lenient"] = gap_block(strict=False)
    pm = {}
    for m in sorted(set(r["model"] for r in judged)):
        sub = [r for r in judged if r["model"] == m and r["format"] == "structured"
               and r["all_components_strict"]]
        fails = [r for r in sub if r["gap_fail_strict"]]
        pm[m] = {"n_component_pass": len(sub), "n_joint_fail": len(fails),
                 "rate": len(fails) / len(sub) if sub else None}
    rep["compositional_gap"]["by_model"] = pm

    # ---- D4 vs D5: which component moves when the state replaces the evidence
    paired = collections.defaultdict(dict)
    for r in judged:
        if r["format"] == "structured" and r["study"] == "main":
            paired[(r["question_id"], r["model"])][r["condition"]] = r
    both = [d for d in paired.values() if "gold_source" in d and "gold_memory_state" in d]
    comp_keys = ["answer_correct", "grounding_ok", "provenance_ok", "preservation_ok",
                 "answerability_correct", "status_correct", "joint_fidelity"]
    branch = {}
    for k in comp_keys:
        a = [d["gold_source"][k] for d in both if d["gold_source"].get(k) is not None]
        b = [d["gold_memory_state"][k] for d in both if d["gold_memory_state"].get(k) is not None]
        branch[k] = {"d4": sum(a) / len(a) if a else None,
                     "d5": sum(b) / len(b) if b else None,
                     "n": min(len(a), len(b))}
    for k in ("contradiction", "revision", "scope", "uncertainty"):
        a = [d["gold_source"][k] == "yes" for d in both if d["gold_source"][k] in ("yes", "no")]
        b = [d["gold_memory_state"][k] == "yes" for d in both
             if d["gold_memory_state"][k] in ("yes", "no")]
        branch[k + "_preserved"] = {"d4": sum(a) / len(a) if a else None,
                                    "d5": sum(b) / len(b) if b else None,
                                    "n": min(len(a), len(b))}
    a = [d["gold_source"]["src_f1"] for d in both if d["gold_source"]["src_f1"] is not None]
    b = [d["gold_memory_state"]["src_f1"] for d in both
         if d["gold_memory_state"]["src_f1"] is not None]
    branch["src_f1"] = {"d4": sum(a) / len(a) if a else None,
                        "d5": sum(b) / len(b) if b else None, "n": min(len(a), len(b))}
    a = [d["gold_source"]["src_p"] for d in both if d["gold_source"]["src_p"] is not None]
    b = [d["gold_memory_state"]["src_p"] for d in both
         if d["gold_memory_state"]["src_p"] is not None]
    branch["src_precision"] = {"d4": sum(a) / len(a) if a else None,
                               "d5": sum(b) / len(b) if b else None, "n": min(len(a), len(b))}
    # what the judge blames when a D4-correct item degrades at D5
    degraded = [d for d in both
                if d["gold_source"]["answer_correct"] and not d["gold_memory_state"]["answer_correct"]]
    why = collections.Counter()
    for d in degraded:
        r5, r4 = d["gold_memory_state"], d["gold_source"]
        if r5["provenance"] == "no" and r4["provenance"] != "no":
            why["provenance lost"] += 1
        for k in ("scope", "uncertainty", "contradiction", "revision"):
            if r5[k] == "no" and r4[k] != "no":
                why[k + " lost"] += 1
        if r5["unsupported"] and not r4["unsupported"]:
            why["unsupported claim added"] += 1
    # the label is copied while the prose resolves the question anyway
    label_vs_prose = {}
    for cond in ("gold_source", "gold_memory_state", "gold_evidence"):
        sub = [r for r in judged if r["condition"] == cond and r["format"] == "structured"
               and r["uncertainty"] in ("yes", "no")]
        lab_ok = [r for r in sub if r["answerability_correct"]]
        label_vs_prose[cond] = {
            "n_uncertainty_applicable": len(sub),
            "n_label_correct": len(lab_ok),
            "label_correct_but_prose_collapses": sum(1 for r in lab_ok if r["uncertainty"] == "no"),
            "rate": (sum(1 for r in lab_ok if r["uncertainty"] == "no") / len(lab_ok))
            if lab_ok else None}
    rep["state_branch_components"] = {"n_pairs": len(both), "components": branch,
                                      "n_degraded": len(degraded), "why": dict(why),
                                      "label_vs_prose": label_vs_prose}

    # ---- Aggregation variants and gate ablations -------------------------------
    # Phi is a strict conjunction; both reviews asked how much the headline numbers
    # depend on that choice, on the least reliable gate (provenance), and on the
    # judge at all. Every variant is recomputed over the same responses.
    GATES = ["answer_correct", "grounding_ok", "provenance_ok", "answerability_correct",
             "contradiction", "revision", "scope", "uncertainty"]

    def gate_values(r):
        """Per-gate verdicts for one response: True / False / None (not applicable)."""
        g = {"answer_correct": r["answer_correct"],
             "grounding_ok": r["grounding_ok"],
             "provenance_ok": None if r["provenance"] == "na" else r["provenance"] != "no",
             "answerability_correct": r["answerability_correct"]}
        for k in ("contradiction", "revision", "scope", "uncertainty"):
            g[k] = None if r[k] not in ("yes", "no") else (r[k] == "yes")
        return g

    def phi_variant(r, drop=(), soft=None):
        """drop: gates to ignore. soft: if set, return the fraction of applicable
        gates passed instead of their conjunction."""
        g = gate_values(r)
        vals = [v for k, v in g.items() if v is not None and k not in drop]
        if not vals:
            return None
        if soft == "fraction":
            return sum(1 for v in vals if v) / len(vals)
        if soft == "one_miss":            # tolerate a single failed gate
            return sum(1 for v in vals if not v) <= 1
        return all(vals)

    def det_phi(r):
        """Phi computed from the deterministic rules alone, plus the two gates that
        genuinely need a reader of the prose (answer fidelity, unsupported claim)."""
        d = r.get("det") or {}
        vals = [v for v in d.values() if v is not None]
        if not vals:
            return None
        return all(vals)

    def hybrid_phi(r):
        """Deterministic rules for the mechanical components, judge for the rest."""
        d = r.get("det") or {}
        mech = [v for k, v in d.items() if v is not None]
        judged = [r["answer_correct"], r["grounding_ok"]]
        if any(v is None for v in judged):
            return None
        return all(mech) and all(judged)

    struct = [r for r in judged if r["format"] == "structured"]
    variants = {}
    defs = [
        ("phi_strict", lambda r: phi_variant(r)),
        ("phi_no_provenance", lambda r: phi_variant(r, drop=("provenance_ok",))),
        ("phi_no_answerability", lambda r: phi_variant(r, drop=("answerability_correct",))),
        ("phi_no_prov_no_answ", lambda r: phi_variant(r, drop=("provenance_ok",
                                                               "answerability_correct"))),
        ("phi_no_grounding", lambda r: phi_variant(r, drop=("grounding_ok",))),
        ("phi_no_prov_no_grounding", lambda r: phi_variant(r, drop=("provenance_ok",
                                                                    "grounding_ok"))),
        ("phi_one_miss_allowed", lambda r: phi_variant(r, soft="one_miss")),
        ("phi_hybrid_det", hybrid_phi),
        ("phi_fully_deterministic", det_phi),
    ]
    for name, fn in defs:
        groups = collections.defaultdict(list)
        per_cond = {}
        for r in struct:
            v = fn(r)
            if v is None:
                continue
            groups[r["question_id"]].append(1.0 if (v is True or v == 1.0) else
                                            (0.0 if v is False else float(v)))
        obs, lo, hi = boot_ci_grouped(groups)
        for c in LADDER:
            sub = [fn(r) for r in struct if r["condition"] == c]
            sub = [x for x in sub if x is not None]
            per_cond[c] = (sum(1.0 if x is True else (0.0 if x is False else float(x))
                               for x in sub) / len(sub)) if sub else None
        variants[name] = {"mean": obs, "ci_lo": lo, "ci_hi": hi,
                          "n": sum(len(v) for v in groups.values()),
                          "by_condition": per_cond}
    # the compositional gap under each aggregation
    gap_variants = {}
    # A gate that is loosened inside Phi must also be loosened in the component-pass set
    # that defines the gap's denominator, or the two sides are not measuring the same
    # responses. `all_components_strict` = retrieval AND grounding AND answer-correct.
    def _base_for(name):
        if "no_grounding" in name:
            return [r for r in struct
                    if r["comp_retrieval_ok"] and r["answer_correct"]]
        return [r for r in struct if r["all_components_strict"]]

    for name, fn in defs:
        sub = _base_for(name)
        fails = [r for r in sub if fn(r) is not None and not (fn(r) is True or fn(r) == 1.0)]
        groups = collections.defaultdict(list)
        for r in sub:
            v = fn(r)
            if v is None:
                continue
            groups[r["question_id"]].append(0.0 if (v is True or v == 1.0) else 1.0)
        obs, lo, hi = boot_ci_grouped(groups)
        gap_variants[name] = {"n": sum(len(v) for v in groups.values()),
                              "rate": obs, "ci_lo": lo, "ci_hi": hi}
    # Does the state-branch result depend on the least reliable gate? Recompute the
    # paired D4->D5 difference with the unsupported-claim gate removed.
    branch_variants = {}
    for vname, vfn in (("phi_strict", lambda r: phi_variant(r)),
                       ("phi_no_grounding", lambda r: phi_variant(r, drop=("grounding_ok",))),
                       ("phi_no_prov_no_grounding",
                        lambda r: phi_variant(r, drop=("provenance_ok", "grounding_ok"))),
                       ("phi_hybrid_det", hybrid_phi),
                       ("phi_fully_deterministic", det_phi)):
        cells = {}
        for r in struct:
            v = vfn(r)
            if v is None:
                continue
            cells[(r["question_id"], r["model"], r["condition"])] = bool(v)
        byq = collections.defaultdict(list)
        for (q, m, c) in list(cells):
            if c != "gold_source":
                continue
            d5 = cells.get((q, m, "gold_memory_state"))
            if d5 is None:
                continue
            byq[q].append((cells[(q, m, c)], d5))
        if not byq:
            continue
        qs = sorted(byq)

        def _st(sample, _b=byq):
            v = [x for q in sample for x in _b[q]]
            n = float(len(v))
            return (sum(a for a, b in v) / n) - (sum(b for a, b in v) / n)

        obs = _st(qs)
        # own generator: this analysis was added late, and must not perturb the
        # bootstrap draws of anything computed after it
        _rng = random.Random(20260914)
        reps = []
        for _ in range(BOOT):
            reps.append(_st([_rng.choice(qs) for _ in qs]))
        reps.sort()
        branch_variants[vname] = {
            "n": sum(len(v) for v in byq.values()), "n_items": len(qs),
            "mean_diff": obs, "ci_lo": reps[int(0.025 * BOOT)],
            "ci_hi": reps[int(0.975 * BOOT)]}

    # which deterministic components move between D4 and D5 (judge-free attribution)
    det_branch = {}
    for comp in ("provenance", "answerability", "contradiction", "revision", "scope",
                 "uncertainty"):
        cells = {}
        for r in struct:
            v = (r.get("det") or {}).get(comp)
            if v is None:
                continue
            cells[(r["question_id"], r["model"], r["condition"])] = bool(v)
        byq = collections.defaultdict(list)
        for (q, m, c) in list(cells):
            if c != "gold_source":
                continue
            d5 = cells.get((q, m, "gold_memory_state"))
            if d5 is None:
                continue
            byq[q].append((cells[(q, m, c)], d5))
        if not byq:
            continue
        qs = sorted(byq)
        v = [x for q in qs for x in byq[q]]
        det_branch[comp] = {"n": len(v),
                            "d4": sum(a for a, _ in v) / len(v),
                            "d5": sum(bb for _, bb in v) / len(v)}
    rep["phi_variants"] = {"phi": variants, "gap": gap_variants,
                           "branch": branch_variants, "det_branch": det_branch}

    # ---- deterministic rule versus judge, per component -------------------------
    det_vs_judge = {}
    pairs_det = [("provenance", "provenance"), ("answerability", "answerability_correct"),
                 ("contradiction", "contradiction"), ("revision", "revision"),
                 ("scope", "scope"), ("uncertainty", "uncertainty")]
    for dkey, jkey in pairs_det:
        A, B = [], []
        for r in struct:
            d = (r.get("det") or {}).get(dkey)
            if d is None:
                continue
            if jkey == "answerability_correct":
                j = r["answerability_correct"]
            elif jkey == "provenance":
                j = None if r["provenance"] == "na" else r["provenance"] != "no"
            else:
                j = None if r[jkey] not in ("yes", "no") else (r[jkey] == "yes")
            if j is None:
                continue
            A.append(str(bool(d)))
            B.append(str(bool(j)))
        det_vs_judge[dkey] = {
            "n": len(A),
            "agreement": (sum(1 for x, y in zip(A, B) if x == y) / len(A)) if A else None,
            "kappa": kappa(A, B) if A else None,
            "det_pass_rate": (sum(1 for x in A if x == "True") / len(A)) if A else None,
            "judge_pass_rate": (sum(1 for x in B if x == "True") / len(B)) if B else None}
    rep["det_vs_judge"] = det_vs_judge

    # ---- per-domain failure composition -----------------------------------------
    dom = {}
    for d in sorted(set(r["domain"] for r in struct)):
        sub = [r for r in struct if r["domain"] == d]
        passed = [r for r in sub if r["all_components_strict"]]
        why = collections.Counter()
        for r in passed:
            if not r["gap_fail_strict"]:
                continue
            for k in ("contradiction", "revision", "scope", "uncertainty"):
                if r[k] == "no":
                    why[k] += 1
            if r["answerability_correct"] is False:
                why["answerability"] += 1
            if r["provenance"] == "no":
                why["provenance"] += 1
        dom[d] = {"n": len(sub),
                  "joint_fidelity": cell(sub, "joint_fidelity"),
                  "n_component_pass": len(passed),
                  "n_gap_fail": sum(1 for r in passed if r["gap_fail_strict"]),
                  "gap_rate": (sum(1 for r in passed if r["gap_fail_strict"]) / len(passed))
                  if passed else None,
                  "reasons": dict(why)}
    rep["by_domain"] = dom

    # ---- Capability x condition breakdown
    capt = {}
    for cat in sorted(set(r["category"] for r in judged)):
        capt[cat] = {}
        for c in LADDER:
            sub = [r for r in judged if r["category"] == cat and r["condition"] == c
                   and r["format"] == "structured"]
            capt[cat][c] = cell(sub, "joint_fidelity")
    rep["capability_by_condition"] = capt

    # ---- Capability-specific preservation metrics per model
    capmodel = {}
    for m in sorted(set(r["model"] for r in judged)):
        sub = [r for r in judged if r["model"] == m and r["format"] == "structured"]
        capmodel[m] = {
            "joint_fidelity": cell(sub, "joint_fidelity"),
            "answer_correct": cell(sub, "answer_correct"),
            "grounding_ok": cell(sub, "grounding_ok"),
            "provenance_ok": cell(sub, "provenance_ok"),
            "answerability_correct": cell(sub, "answerability_correct"),
            "status_correct": cell(sub, "status_correct"),
            "src_f1": {"mean": rate(sub, "src_f1")},
            "scope_cov": {"mean": rate(sub, "scope_cov")},
        }
        for k in ("contradiction", "revision", "scope", "uncertainty"):
            appl = [r for r in sub if r[k] in ("yes", "no")]
            capmodel[m][k + "_preserved"] = cell(
                [dict(r, _v=(r[k] == "yes")) for r in appl], "_v") if appl else {"mean": None, "n": 0}
        # uncertainty collapse: gold is non-answerable, model gives a determinate answer
        ucs = [r for r in sub if r["gold_abstain"] and r["pred_answerability"]]
        capmodel[m]["uncertainty_collapse"] = {
            "mean": (sum(1 for r in ucs if not r["abstained"]) / len(ucs)) if ucs else None,
            "n": len(ucs)}
    rep["by_model"] = capmodel

    # ---- Rank inversions (are the metrics collinear?)
    metrics = ["joint_fidelity", "answer_correct", "provenance_ok", "answerability_correct",
               "status_correct", "contradiction_preserved", "revision_preserved",
               "scope_preserved", "uncertainty_preserved"]
    ranks = {}
    for mt in metrics:
        vals = []
        for m, d in capmodel.items():
            v = d.get(mt, {}).get("mean")
            if v is not None:
                vals.append((v, m))
        vals.sort(reverse=True)
        ranks[mt] = [m for _, m in vals]
    base = ranks.get("joint_fidelity", [])
    inv = {}
    for mt, order in ranks.items():
        if mt == "joint_fidelity" or not base:
            continue
        pos = {m: i for i, m in enumerate(order)}
        c = 0
        for i in range(len(base)):
            for j in range(i + 1, len(base)):
                if base[i] in pos and base[j] in pos and pos[base[i]] > pos[base[j]]:
                    c += 1
        inv[mt] = {"inversions_vs_joint": c,
                   "pairs": len(base) * (len(base) - 1) // 2, "order": order}
    rep["rank_inversions"] = {"orders": ranks, "vs_joint": inv}

    # ---- Monotonicity along the ladder
    mono = {"per_step": {}, "trajectories": 0, "strictly_monotone": 0, "violating": 0}
    traj = collections.defaultdict(dict)
    for r in judged:
        if r["format"] == "structured":
            traj[(r["question_id"], r["model"])][r["condition"]] = r["joint_fidelity"]
    CHAIN_SET = set(CHAIN)
    steps = list(zip(CHAIN, CHAIN[1:]))
    step_counts = {"%s->%s" % (a, b): {"up": 0, "same": 0, "down": 0} for a, b in steps}
    for key, d in traj.items():
        if not all(c in d for c in CHAIN):
            continue
        mono["trajectories"] += 1
        viol = False
        for (a, b) in steps:
            if d[b] and not d[a]:
                step_counts["%s->%s" % (a, b)]["up"] += 1
            elif (not d[b]) and d[a]:
                step_counts["%s->%s" % (a, b)]["down"] += 1
                viol = True
            else:
                step_counts["%s->%s" % (a, b)]["same"] += 1
        if viol:
            mono["violating"] += 1
        else:
            mono["strictly_monotone"] += 1
    mono["per_step"] = step_counts
    # aggregate monotonicity of the cell means
    means = [rep["ladder_joint_fidelity"]["ALL"][c]["mean"] for c in CHAIN]
    mono["chain"] = CHAIN
    mono["aggregate_means"] = dict(zip(CHAIN, means))
    mono["aggregate_monotone"] = all(
        (means[i] is not None and means[i + 1] is not None and means[i + 1] >= means[i] - 1e-9)
        for i in range(len(means) - 1))
    # D5 is a separate branch: the state is supplied instead of the evidence text
    d4 = rep["ladder_joint_fidelity"]["ALL"]["gold_source"]["mean"]
    d5 = rep["ladder_joint_fidelity"]["ALL"]["gold_memory_state"]["mean"]
    d6 = rep["ladder_joint_fidelity"]["ALL"]["gold_evidence"]["mean"]
    mono["state_branch"] = {"d4_gold_source": d4, "d5_gold_memory_state": d5,
                            "d6_gold_evidence": d6,
                            "d5_minus_d4": (d5 - d4) if (d4 is not None and d5 is not None) else None,
                            "d6_minus_d5": (d6 - d5) if (d5 is not None and d6 is not None) else None}
    per_item_d45 = {"d4_pass_d5_fail": 0, "d4_fail_d5_pass": 0, "both": 0, "neither": 0}
    for key, d in traj.items():
        if "gold_source" in d and "gold_memory_state" in d:
            a, b = d["gold_source"], d["gold_memory_state"]
            per_item_d45["both" if (a and b) else "neither" if (not a and not b)
                         else "d4_pass_d5_fail" if a else "d4_fail_d5_pass"] += 1
    mono["d4_vs_d5_items"] = per_item_d45
    per_model_mono = {}
    for m in sorted(set(r["model"] for r in judged)):
        ms = [rep["ladder_joint_fidelity"][m][c]["mean"] for c in CHAIN]
        per_model_mono[m] = {"means": dict(zip(CHAIN, ms)),
                             "monotone": all(ms[i] is not None and ms[i + 1] is not None
                                             and ms[i + 1] >= ms[i] - 1e-9
                                             for i in range(len(ms) - 1)),
                             "drops": [CHAIN[i + 1] for i in range(len(ms) - 1)
                                       if ms[i] is not None and ms[i + 1] is not None
                                       and ms[i + 1] < ms[i] - 1e-9]}
    mono["per_model"] = per_model_mono
    rep["monotonicity"] = mono

    # ---- Output-format ablation
    fmt = {}
    for c in ["online_history", "gold_source", "gold_memory_state"]:
        fmt[c] = {}
        for f in ["structured", "plain"]:
            sub = [r for r in rows if r["judged"] and r["condition"] == c and r["format"] == f
                   and not r["is_transfer"] and r["study"] in ("main", "format_ablation")
                   and r["model"] in ABL_MODELS]
            fmt[c][f] = {k: cell(sub, k) for k in
                         ["joint_fidelity", "answer_correct", "grounding_ok",
                          "provenance_ok", "preservation_ok"]}
            fmt[c][f]["failure_localizable"] = {
                "mean": sum(1 for r in sub if r["n_preservation_applicable"] > 0) / len(sub)
                if sub else None, "n": len(sub)}
        # paired localisability: same item, same model, same condition, both formats
        pairs_f = collections.defaultdict(dict)
        for r in rows:
            if (r["judged"] and r["condition"] == c and not r["is_transfer"]
                    and r["study"] in ("main", "format_ablation") and r["model"] in ABL_MODELS):
                pairs_f[(r["question_id"], r["model"])][r["format"]] = r
        both_f = [d for d in pairs_f.values() if "structured" in d and "plain" in d]
        lost = kept = gained = 0
        for d in both_f:
            for k in ("contradiction", "revision", "scope", "uncertainty"):
                a = d["structured"][k] in ("yes", "no")
                b = d["plain"][k] in ("yes", "no")
                if a and not b:
                    lost += 1
                elif a and b:
                    kept += 1
                elif b and not a:
                    gained += 1
        fmt[c]["answer_words"] = {}
        for f in ["structured", "plain"]:
            ws = [r["answer_words"] for r in rows
                  if r["condition"] == c and r["format"] == f and not r["is_transfer"]
                  and r["study"] in ("main", "format_ablation") and r["model"] in ABL_MODELS
                  and r["resp_ok"]]
            fmt[c]["answer_words"][f] = {
                "median": statistics.median(ws) if ws else None,
                "mean": sum(ws) / len(ws) if ws else None, "n": len(ws)}
        fmt[c]["paired_localisability"] = {
            "n_pairs": len(both_f), "components_graded_in_structured": lost + kept,
            "of_which_ungradable_in_prose": lost, "gradable_only_in_prose": gained,
            "rate_lost": (lost / (lost + kept)) if (lost + kept) else None}
    rep["format_ablation"] = fmt

    # ---- Pushback / cross-user consistency
    push = {}
    base = {}
    for r in rows:
        if (r["study"] == "main" and r["condition"] == "gold_source"
                and r["format"] == "structured" and r["model"] in ABL_MODELS
                and r["judged"]):
            base[(r["question_id"], r["model"])] = r
    for arm in ["pushback_control", "pushback_pushback"]:
        sub = [r for r in rows if r["condition"] == arm and r["judged"]
               and r["model"] in ABL_MODELS]
        flips = []
        for r in sub:
            b = base.get((r["question_id"], r["model"]))
            if not b or "answer_correct" not in b or "answer_correct" not in r:
                continue
            flip = None
            if b["pred_answerability"] and r["pred_answerability"]:
                flip = (b["pred_answerability"] != r["pred_answerability"])
            flips.append({"qid": r["question_id"], "model": r["model"],
                          "flip": flip,
                          "lost_fidelity": bool(b["answer_correct"] and not r["answer_correct"]),
                          "lost_preservation": bool(b["preservation_ok"] and not r["preservation_ok"]),
                          "became_unsupported": bool(b["grounding_ok"] and not r["grounding_ok"])})
        push[arm] = {
            "n": len(flips),
            "answerability_flip": cell([dict(f, question_id=f["qid"], _v=f["flip"])
                                        for f in flips if f["flip"] is not None], "_v")
            if any(f["flip"] is not None for f in flips) else {"mean": None, "n": 0},
            "lost_fidelity": cell([dict(f, question_id=f["qid"], _v=f["lost_fidelity"]) for f in flips], "_v"),
            "lost_preservation": cell([dict(f, question_id=f["qid"], _v=f["lost_preservation"]) for f in flips], "_v"),
            "became_unsupported": cell([dict(f, question_id=f["qid"], _v=f["became_unsupported"]) for f in flips], "_v"),
            "joint_fidelity": cell([r for r in sub if r["format"] == "structured"], "joint_fidelity"),
        }
        by_model = {}
        for m in sorted(set(f["model"] for f in flips)):
            fm = [f for f in flips if f["model"] == m]
            by_model[m] = {
                "n": len(fm),
                "lost_fidelity": sum(1 for f in fm if f["lost_fidelity"]) / len(fm) if fm else None,
                "lost_preservation": sum(1 for f in fm if f["lost_preservation"]) / len(fm) if fm else None,
            }
        push[arm]["by_model"] = by_model
    # paired arm difference: same item, same model, pushback minus control
    arms = collections.defaultdict(dict)
    for r in rows:
        if r["condition"] in ("pushback_control", "pushback_pushback") and r["judged"] \
                and r["model"] in ABL_MODELS:
            arms[(r["question_id"], r["model"])][r["condition"]] = r
    paired_arms = {k: v for k, v in arms.items()
                   if "pushback_control" in v and "pushback_pushback" in v}
    diffs = {}
    for metric, fn in [("lost_fidelity", lambda b, r: bool(b["answer_correct"] and not r["answer_correct"])),
                       ("unsupported", lambda b, r: bool(r["unsupported"])),
                       ("preservation_failed", lambda b, r: not r["preservation_ok"]),
                       ("answer_correct", lambda b, r: bool(r["answer_correct"])),
                       ("joint_fidelity", lambda b, r: bool(r["joint_fidelity"]))]:
        per_item = collections.defaultdict(list)
        for (q, m), v in paired_arms.items():
            b = base.get((q, m))
            if b is None or "answer_correct" not in b:
                continue
            d = (1.0 if fn(b, v["pushback_pushback"]) else 0.0) - \
                (1.0 if fn(b, v["pushback_control"]) else 0.0)
            per_item[q].append(d)
        keys = [k for k in per_item if per_item[k]]
        if not keys:
            diffs[metric] = {"n": 0}
            continue
        flat = [x for k in keys for x in per_item[k]]
        obs = sum(flat) / len(flat)
        reps = []
        for _ in range(BOOT):
            acc = cnt = 0
            for _ in range(len(keys)):
                v = per_item[keys[RNG.randrange(len(keys))]]
                acc += sum(v)
                cnt += len(v)
            reps.append(acc / cnt if cnt else 0.0)
        reps.sort()
        diffs[metric] = {"n": len(flat), "n_items": len(keys), "mean_diff": obs,
                         "ci_lo": reps[int(0.025 * BOOT)], "ci_hi": reps[int(0.975 * BOOT)],
                         "p_two_sided_sign": sum(1 for x in reps if (x <= 0) == (obs > 0))
                                             / BOOT * 2}
    push["paired_difference"] = diffs
    # Arm equivalence: the two arms are independent conversations sharing turn 1 verbatim,
    # so their turn-1 states should be statistically identical. Checked on the stored turn-1
    # text, which needs no extra grading.
    raw_by_rec = {}
    for r in load_jsonl("responses_*.jsonl"):
        if r.get("study") == "pushback" and r.get("raw_turn1"):
            raw_by_rec[r["record_id"]] = r
    arm_stats = {}
    for arm in ("pushback_control", "pushback_pushback"):
        lab, words, srcs = collections.Counter(), [], []
        for rid, r in raw_by_rec.items():
            if r.get("condition") != arm:
                continue
            parsed = None
            try:
                import runner as _runner
                parsed = _runner.extract_json(r["raw_turn1"])
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                a = answerability_of(parsed)
                if a:
                    lab[a] += 1
                ans = parsed.get("answer")
                if isinstance(ans, str):
                    words.append(len(ans.split()))
                srcs.append(len(norm_ids(parsed.get("source_ids"))))
        arm_stats[arm] = {
            "n": sum(lab.values()),
            "answerability": {k: v / max(sum(lab.values()), 1) for k, v in lab.items()},
            "median_words": statistics.median(words) if words else None,
            "mean_source_ids": (sum(srcs) / len(srcs)) if srcs else None}
    if all(arm_stats[a]["n"] for a in arm_stats):
        c = arm_stats["pushback_control"]["answerability"]
        t = arm_stats["pushback_pushback"]["answerability"]
        keys = set(c) | set(t)
        maxdiff = max(abs(c.get(k, 0) - t.get(k, 0)) for k in keys) if keys else 0.0
        arm_stats["max_answerability_gap"] = maxdiff
        arm_stats["sentence"] = (
            "The arms are independent conversations that share turn~1 verbatim; their turn-1 states "
            "agree to within %.1f points on the answerability distribution (median answer length "
            "%s against %s words), so the turn-2 difference is not inherited from turn~1."
            % (100 * maxdiff, arm_stats["pushback_control"]["median_words"],
               arm_stats["pushback_pushback"]["median_words"]))
    push["arm_balance"] = arm_stats
    rep["pushback"] = push


    # ---- Transfer domains
    tr = {}
    trows = [r for r in rows if r["is_transfer"] and r["judged"] and r["model"] in ABL_MODELS]
    for dom in sorted(set(items[r["question_id"]]["domain"] for r in trows)):
        for c in ["online_history", "gold_source", "gold_memory_state"]:
            sub = [r for r in trows if items[r["question_id"]]["domain"] == dom
                   and r["condition"] == c]
            tr["%s|%s" % (dom, c)] = cell(sub, "joint_fidelity")
    for c in ["online_history", "gold_source", "gold_memory_state"]:
        sub_t = [r for r in trows if r["condition"] == c]
        sub_o = [r for r in judged if r["condition"] == c and r["format"] == "structured"
                 and r["model"] in ABL_MODELS]
        tr["TRANSFER_ALL|" + c] = cell(sub_t, "joint_fidelity")
        tr["ORIGINAL_ALL|" + c] = cell(sub_o, "joint_fidelity")
    tr["capability_applicability"] = {
        k: sum(1 for r in trows if r[k] in ("yes", "no")) / len(trows) if trows else None
        for k in ("contradiction", "revision", "scope", "uncertainty")}
    tr["n_responses"] = len(trows)
    rep["transfer"] = tr

    # ---- Judge validation controls
    # A corruption can only be detected on items that actually carry the property it
    # destroys, so every rate is reported on its applicable subset, with the rate on the
    # inapplicable subset as a false-positive check.
    def applicable(it, variant):
        if variant == "scope_stripped":
            return bool(it.get("gold_method_slots") or it.get("gold_condition_slots"))
        if variant == "uncertainty_collapsed":
            return it["expert_answerability_label"] != "answerable"
        if variant == "contradiction_flattened":
            return it["category"] in ("contradiction_resolution", "uncertainty_abstention") \
                or it["primary_failure_mode"] in ("contradiction_blindness", "uncertainty_collapse")
        return True

    FIRE = {"scope_stripped": ("scope_preserved", "no"),
            "uncertainty_collapsed": ("uncertainty_preserved", "no"),
            "contradiction_flattened": ("contradiction_preserved", "no"),
            "provenance_swapped": ("provenance_correct", "no"),
            "unsupported_addition": ("unsupported_claim", True),
            "revision_lost": ("revision_preserved", "no"),
            "gold_verbatim": ("answer_fidelity", "correct")}
    ctrl = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    ctrl_n = collections.Counter()
    fired = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for c in load_jsonl("controlsv2_*.jsonl"):
        if not c.get("judgment"):
            continue
        jm = c["judge_model"]
        v = c["variant"]
        it = items.get(c["question_id"])
        if it is None:
            continue
        ctrl_n[(jm, v)] += 1
        J = c["judgment"]
        for k in ("answer_fidelity", "contradiction_preserved", "scope_preserved",
                  "uncertainty_preserved", "provenance_correct", "revision_preserved"):
            ctrl[jm][v + "|" + k][str(J.get(k)).lower()] += 1
        ctrl[jm][v + "|unsupported_claim"][str(J.get("unsupported_claim")).lower()] += 1
        field, want = FIRE[v]
        got = J.get(field)
        hit = (str(got).lower() == str(want).lower())
        bucket = "applicable" if applicable(it, v) else "inapplicable"
        fired[jm][v + "|" + bucket][0] += 1 if hit else 0
        fired[jm][v + "|" + bucket][1] += 1
    rep["judge_controls"] = {jm: {k: dict(v) for k, v in d.items()} for jm, d in ctrl.items()}
    rep["judge_controls_n"] = {"%s|%s" % k: v for k, v in ctrl_n.items()}
    rep["judge_controls_conditioned"] = {
        jm: {k: {"hits": v[0], "n": v[1], "rate": (v[0] / v[1]) if v[1] else None}
             for k, v in d.items()} for jm, d in fired.items()}
    # false-positive rate: how often each component fires on the unmodified gold answer,
    # restricted to the items where that component is applicable
    fp = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for c in load_jsonl("controlsv2_*.jsonl"):
        if not c.get("judgment") or c.get("variant") != "gold_verbatim":
            continue
        it = items.get(c["question_id"])
        if it is None:
            continue
        J = c["judgment"]
        for v, (field, want) in FIRE.items():
            if v == "gold_verbatim" or not applicable(it, v):
                continue
            hit = str(J.get(field)).lower() == str(want).lower()
            fp[c["judge_model"]][v][0] += 1 if hit else 0
            fp[c["judge_model"]][v][1] += 1
    rep["judge_controls_falsepos"] = {
        jm: {k: {"hits": v[0], "n": v[1], "rate": (v[0] / v[1]) if v[1] else None}
             for k, v in d.items()} for jm, d in fp.items()}

    # ---- Judge agreement (primary vs secondary)
    fields = ["answer_fidelity", "unsupported_claim", "contradiction_preserved",
              "revision_preserved", "scope_preserved", "uncertainty_preserved",
              "provenance_correct"]
    agree = {}
    pairs = [(r, r["judge2"]) for r in rows if r["judged"] and r.get("judge2")]
    for f in fields:
        A, B = [], []
        key = {"answer_fidelity": "fidelity", "unsupported_claim": "unsupported",
               "contradiction_preserved": "contradiction", "revision_preserved": "revision",
               "scope_preserved": "scope", "uncertainty_preserved": "uncertainty",
               "provenance_correct": "provenance"}[f]
        for r, j2 in pairs:
            a = r[key]
            b = j2.get(f)
            if isinstance(b, str):
                b = b.strip().lower()
            if isinstance(a, bool) or isinstance(b, bool):
                a, b = str(a).lower(), str(b).lower()
            if a is None or b is None:
                continue
            A.append(str(a))
            B.append(str(b))
        agree[f] = {"n": len(A),
                    "agreement": (sum(1 for x, y in zip(A, B) if x == y) / len(A)) if A else None,
                    "kappa": kappa(A, B) if A else None}
    rep["judge_agreement"] = agree

    # ---- judge test-retest reliability, from responses graded twice by the primary judge
    repeats = collections.defaultdict(list)
    for j in load_jsonl("judgments_*.jsonl"):
        if j.get("judgment"):
            repeats[j["target_record_id"]].append(j["judgment"])
    pairs2 = [(v[0], v[1]) for v in repeats.values() if len(v) >= 2]
    selfc = {}
    for f in fields:
        A = [str(x.get(f)).lower() for x, y in pairs2]
        B = [str(y.get(f)).lower() for x, y in pairs2]
        selfc[f] = {"n": len(A),
                    "agreement": (sum(1 for x, y in zip(A, B) if x == y) / len(A)) if A else None,
                    "kappa": kappa(A, B) if A else None}
    rep["judge_self_consistency"] = {"n_repeat_graded": len(pairs2), "fields": selfc}

    # ---- Annotation triage (scalability)
    tri = {}
    expert = {q: items[q] for q in items}
    allpool = {r["question_id"]: r for r in json.load(
        open(os.path.join(HERE, "data", "items.json"), encoding="utf-8"))}
    import csv as _csv
    sup = os.path.join(HERE, "..", "1036_Scientific_Memory_Is_Not__Supplementary Material (2)",
                       "neurips_position_supplement_final", "data",
                       "expert_review_sample_300_completed.csv")
    exp_rows = {r["question_id"]: r for r in
                _csv.DictReader(open(sup, encoding="utf-8-sig"))}
    for path in sorted(glob.glob(os.path.join(RAW, "triage_*.jsonl"))):
        model = os.path.basename(path)[len("triage_"):-len(".jsonl")]
        recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        dec_a, dec_b, sup_a, sup_b, ans_a, ans_b = [], [], [], [], [], []
        flagged = {}
        for r in recs:
            p = r.get("parsed") or {}
            e = exp_rows.get(r["question_id"])
            if not e:
                continue
            d = str(p.get("item_decision", "")).strip().lower()
            s = str(p.get("evidence_support", "")).strip().lower()
            a = str(p.get("answerability", "")).strip().lower()
            if d in ("accept", "revise", "reject"):
                dec_a.append(d)
                dec_b.append(e["expert_item_decision"])
                flagged[r["question_id"]] = (d != "accept") or (s != "fully_supported")
            if s:
                sup_a.append(s)
                sup_b.append(e["expert_evidence_support"])
            if a:
                ans_a.append(a)
                ans_b.append(e["expert_answerability_label"])
        need = {q: exp_rows[q]["expert_item_decision"] != "accept" for q in flagged}
        tp = sum(1 for q in flagged if flagged[q] and need[q])
        fp = sum(1 for q in flagged if flagged[q] and not need[q])
        fn = sum(1 for q in flagged if not flagged[q] and need[q])
        tri[model] = {
            "n": len(recs),
            "parse_rate": sum(1 for r in recs if r.get("parsed")) / len(recs) if recs else None,
            "item_decision": {"n": len(dec_a),
                              "agreement": sum(1 for x, y in zip(dec_a, dec_b) if x == y) / len(dec_a) if dec_a else None,
                              "kappa": kappa(dec_a, dec_b) if dec_a else None},
            "evidence_support": {"n": len(sup_a),
                                 "agreement": sum(1 for x, y in zip(sup_a, sup_b) if x == y) / len(sup_a) if sup_a else None,
                                 "kappa": kappa(sup_a, sup_b) if sup_a else None},
            "answerability": {"n": len(ans_a),
                              "agreement": sum(1 for x, y in zip(ans_a, ans_b) if x == y) / len(ans_a) if ans_a else None,
                              "kappa": kappa(ans_a, ans_b) if ans_a else None},
            "flag_screen": {"flagged": sum(1 for q in flagged if flagged[q]),
                            "needs_expert": sum(1 for q in need if need[q]),
                            "recall": tp / (tp + fn) if (tp + fn) else None,
                            "precision": tp / (tp + fp) if (tp + fp) else None,
                            "review_budget": sum(1 for q in flagged if flagged[q]) / len(flagged)
                            if flagged else None},
        }
    rep["triage"] = tri

    # ---- screening curve: combine both triage models into a flag score
    flags = collections.defaultdict(int)
    seen_models = []
    for path in sorted(glob.glob(os.path.join(RAW, "triage_*.jsonl"))):
        model = os.path.basename(path)[len("triage_"):-len(".jsonl")]
        seen_models.append(model)
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            pr = r.get("parsed") or {}
            q = r["question_id"]
            if q not in exp_rows:
                continue
            flags[q] += 0  # ensure key exists
            d = str(pr.get("item_decision", "")).strip().lower()
            sup = str(pr.get("evidence_support", "")).strip().lower()
            if d and d != "accept":
                flags[q] += 1
            if sup and sup != "fully_supported":
                flags[q] += 1
    need = {q: exp_rows[q]["expert_item_decision"] != "accept" for q in flags}
    total_need = sum(1 for q in need if need[q])
    curve = []
    for thr in range(0, 5):
        fwd = [q for q in flags if flags[q] >= thr]
        hit = sum(1 for q in fwd if need[q])
        curve.append({"threshold": thr, "budget": len(fwd) / len(flags) if flags else None,
                      "n_forwarded": len(fwd),
                      "recall": hit / total_need if total_need else None,
                      "precision": hit / len(fwd) if fwd else None})
    rep["triage_curve"] = {"n_items": len(flags), "n_need_expert": total_need,
                           "base_rate": total_need / len(flags) if flags else None,
                           "models": seen_models, "curve": curve}

    # ---- Noise floor: repeated generations under an unchanged condition ---------
    # A downward move between conditions only means something if it happens less often
    # than a downward move between two samples of the SAME condition.
    rep_rows = [r for r in rows if r["study"] == "noise" and r["judged"]]
    base_rows = {(r["question_id"], r["model"], r["condition"]): r
                 for r in rows if r["study"] == "main" and r["format"] == "structured"
                 and r["judged"]}
    samples = collections.defaultdict(dict)      # (qid, model, cond) -> {rep: phi}
    for r in rep_rows:
        samples[(r["question_id"], r["model"], r["condition"])][r["replicate"]] = r["joint_fidelity"]
    for k, r in base_rows.items():
        if k in samples:
            samples[k][0] = r["joint_fidelity"]

    def flip_stats(pairs):
        if not pairs:
            return None
        down = sum(1 for a, b in pairs if a and not b)
        up = sum(1 for a, b in pairs if b and not a)
        return {"n": len(pairs), "down": down / len(pairs), "up": up / len(pairs),
                "flip": (down + up) / len(pairs)}

    within = {}
    for cond in ("gold_source", "gold_evidence"):
        pairs = []
        for (q, m, c), d in samples.items():
            if c != cond:
                continue
            reps = [d[k] for k in sorted(d) if d[k] is not None]
            for i in range(len(reps)):
                for j in range(i + 1, len(reps)):
                    pairs.append((reps[i], reps[j]))
        st = flip_stats(pairs)
        if st:
            st["label"] = "Within %s (same condition, resampled)" % LADDER_LABEL[cond].split(" ", 1)[1]
            within["within_" + cond] = st
    # between-condition pairs, using every available replicate of each side
    bpairs = []
    for (q, m, c), d in samples.items():
        if c != "gold_source":
            continue
        other = samples.get((q, m, "gold_evidence"))
        if not other:
            continue
        for a in [v for v in d.values() if v is not None]:
            for b in [v for v in other.values() if v is not None]:
                bpairs.append((a, b))
    bst = flip_stats(bpairs)
    noise = dict(within)
    if bst:
        bst["label"] = "Between D4 and D6 (the monotonicity step)"
        noise["between_d4_d6"] = bst
    noise["pairs"] = sum(v["n"] for k, v in noise.items() if isinstance(v, dict) and "n" in v)
    if bst and within:
        wdown = statistics.mean([v["down"] for v in within.values()])
        wflip = statistics.mean([v["flip"] for v in within.values()])
        excess = bst["down"] - wdown
        noise["excess_down_over_floor"] = excess
        noise["within_down"] = wdown
        noise["within_flip"] = wflip
        noise["between_down"] = bst["down"]

    # the D4 -> D5 asymmetry, against the same floor, plus a paired CI on the rate gap
    d45 = []
    for (q, m, c), d in samples.items():
        if c != "gold_source":
            continue
        b5 = base_rows.get((q, m, "gold_memory_state"))
        if b5 is None:
            continue
        for a in [v for v in d.values() if v is not None]:
            d45.append((a, b5["joint_fidelity"]))
    st45 = flip_stats(d45)
    if st45:
        st45["label"] = "Between D4 and D5 (the state branch)"
        noise["between_d4_d5"] = st45

    # paired item-level bootstrap on the D4 minus D5 rate difference
    per_item_gap = collections.defaultdict(list)
    for (q, m, c), r in base_rows.items():
        if c != "gold_source":
            continue
        r5 = base_rows.get((q, m, "gold_memory_state"))
        if r5 is None:
            continue
        per_item_gap[q].append((1.0 if r["joint_fidelity"] else 0.0)
                               - (1.0 if r5["joint_fidelity"] else 0.0))
    keys = [k for k in per_item_gap if per_item_gap[k]]
    # The gate-sensitivity block already bootstrapped exactly this statistic under strict
    # Phi. Reuse its interval rather than drawing a second one: two independent bootstraps
    # of the same quantity round to different bounds, and the paper prints both.
    _branch_strict = (rep.get("phi_variants", {}).get("branch", {}) or {}).get("phi_strict")
    if _branch_strict:
        noise["d4_minus_d5_paired"] = dict(_branch_strict)
        noise["d4_minus_d5_paired"]["source"] = "phi_variants.branch.phi_strict"
    elif keys:
        flat = [x for k in keys for x in per_item_gap[k]]
        obs = sum(flat) / len(flat)
        reps_b = []
        for _ in range(BOOT):
            acc = cnt = 0
            for _ in range(len(keys)):
                v = per_item_gap[keys[RNG.randrange(len(keys))]]
                acc += sum(v)
                cnt += len(v)
            reps_b.append(acc / cnt if cnt else 0.0)
        reps_b.sort()
        noise["d4_minus_d5_paired"] = {
            "n": len(flat), "n_items": len(keys), "mean_diff": obs,
            "ci_lo": reps_b[int(0.025 * BOOT)], "ci_hi": reps_b[int(0.975 * BOOT)]}

    # the same paired CI for the D6 minus D4 step, so the chain claim gets one too
    per_item_step = collections.defaultdict(list)
    for (q, m, c), r in base_rows.items():
        if c != "gold_evidence":
            continue
        r4 = base_rows.get((q, m, "gold_source"))
        if r4 is None:
            continue
        per_item_step[q].append((1.0 if r["joint_fidelity"] else 0.0)
                                - (1.0 if r4["joint_fidelity"] else 0.0))
    keys = [k for k in per_item_step if per_item_step[k]]
    if keys:
        flat = [x for k in keys for x in per_item_step[k]]
        obs = sum(flat) / len(flat)
        reps_b = []
        for _ in range(BOOT):
            acc = cnt = 0
            for _ in range(len(keys)):
                v = per_item_step[keys[RNG.randrange(len(keys))]]
                acc += sum(v)
                cnt += len(v)
            reps_b.append(acc / cnt if cnt else 0.0)
        reps_b.sort()
        noise["d6_minus_d4_paired"] = {
            "n": len(flat), "n_items": len(keys), "mean_diff": obs,
            "ci_lo": reps_b[int(0.025 * BOOT)], "ci_hi": reps_b[int(0.975 * BOOT)]}

    # one sentence carrying both verdicts: the step that survives and the one that does not
    w_d = noise.get("within_down")
    b46 = noise.get("between_d4_d6")
    b45 = noise.get("between_d4_d5")
    g45 = noise.get("d4_minus_d5_paired")
    g64 = noise.get("d6_minus_d4_paired")
    if w_d is not None and b46 and b45 and g45 and g64:
        noise["sentence"] = (
            "Two samples of an unchanged condition disagree on $\\Phi$ %.0f\\%% of the time, "
            "%.0f\\%% of it downward: that is the floor. Downward moves at D4$\\rightarrow$D6 "
            "occur at %.0f\\%%, indistinguishable from it, so we withdraw item-level "
            "non-monotonicity as a standalone finding and read the trajectory figure only as a "
            "noise-inclusive upper bound; the \\emph{net} step survives at %+.1f points "
            "[%+.1f, %+.1f]. The branch behaves differently --- D4$\\rightarrow$D5 falls at "
            "%.0f\\%% against %.0f\\%% upward, roughly twice the floor, paired gap %+.1f "
            "[%+.1f, %+.1f] --- so it is separable from sampling noise."
            % (100 * noise["within_flip"], 100 * w_d, 100 * b46["down"],
               100 * g64["mean_diff"], 100 * g64["ci_lo"], 100 * g64["ci_hi"],
               100 * b45["down"], 100 * b45["up"],
               100 * g45["mean_diff"], 100 * g45["ci_lo"], 100 * g45["ci_hi"]))

    rep["noise_floor"] = noise

    # ---- Protocol controls: curator note, and instruction parity -----------------
    controls = {}
    for study, conds in (("nocaveat", ("online_history", "gold_source")),
                         ("parity", ("gold_source", "gold_memory_state", "gold_evidence"))):
        srows = [r for r in rows if r["study"] == study and r["judged"]]
        if not srows:
            continue
        by_cond = {}
        for c in conds:
            pairs = []
            for r in srows:
                if r["condition"] != c:
                    continue
                b = base_rows.get((r["question_id"], r["model"], c))
                if b is None:
                    continue
                pairs.append((b["joint_fidelity"], r["joint_fidelity"]))
            if not pairs:
                continue
            base = sum(1 for a, _ in pairs if a) / len(pairs)
            ctrl = sum(1 for _, b in pairs if b) / len(pairs)
            by_cond[c] = {"n": len(pairs), "base": base, "control": ctrl,
                          "delta": ctrl - base}
        controls[study] = {"by_condition": by_cond}

    # Difference-in-differences: the D4->X step under parity framing minus the same
    # step under the main framing, on the (item, model) cells present in both arms.
    # This is what separates "the effect is framing" from "the effect survives framing".
    par_rows = {(r["question_id"], r["model"], r["condition"]): r["joint_fidelity"]
                for r in rows if r["study"] == "parity" and r["judged"]
                and r["joint_fidelity"] is not None}
    did = {}
    for target in ("gold_memory_state", "gold_evidence"):
        cells = []
        for (q, m, c) in par_rows:
            if c != target:
                continue
            p4 = par_rows.get((q, m, "gold_source"))
            p5 = par_rows.get((q, m, target))
            b4 = base_rows.get((q, m, "gold_source"))
            b5 = base_rows.get((q, m, target))
            if None in (p4, p5) or b4 is None or b5 is None:
                continue
            if b4["joint_fidelity"] is None or b5["joint_fidelity"] is None:
                continue
            cells.append((q, [p4, p5, b4["joint_fidelity"], b5["joint_fidelity"]]))
        if not cells:
            continue
        byq = {}
        for q, v in cells:
            byq.setdefault(q, []).append(v)
        qs = sorted(byq)

        def _stat(sample_qs, _byq=byq):
            v = [x for q in sample_qs for x in _byq[q]]
            n = float(len(v))
            d_par = (sum(x[1] for x in v) - sum(x[0] for x in v)) / n
            d_main = (sum(x[3] for x in v) - sum(x[2] for x in v)) / n
            return d_par, d_main

        dp, dm = _stat(qs)
        reps_p, reps_m, reps_d = [], [], []
        for _ in range(BOOT):
            samp = [RNG.choice(qs) for _ in qs]
            a, b = _stat(samp)
            reps_p.append(a)
            reps_m.append(b)
            reps_d.append(a - b)

        def _ci(v):
            v = sorted(v)
            return v[int(0.025 * len(v))], v[int(0.975 * len(v))]

        plo, phi = _ci(reps_p)
        mlo, mhi = _ci(reps_m)
        dlo, dhi = _ci(reps_d)
        did[target] = {"cells": len(cells), "items": len(qs),
                       "parity_delta": dp, "parity_lo": plo, "parity_hi": phi,
                       "main_delta": dm, "main_lo": mlo, "main_hi": mhi,
                       "attenuation": dp - dm, "att_lo": dlo, "att_hi": dhi,
                       "separable": bool(dlo > 0 or dhi < 0)}
    if did:
        controls.setdefault("parity", {})["did"] = did

    if controls:
        bits = []
        nc = controls.get("nocaveat", {}).get("by_condition", {})
        if nc:
            worst = max(nc.values(), key=lambda d: abs(d["delta"]))
            bits.append("Removing the curator note moves $\\Phi$ by at most %.1f points on the "
                        "conditions that carry it, so systems were not reading the "
                        "benchmark's own commentary" % (100 * worst["delta"]))
        d5 = did.get("gold_memory_state")
        if d5:
            bits.append(
                "and equalising the instructions leaves the D4$\\rightarrow$D5 step at %+.1f "
                "[%+.1f, %+.1f] against %+.1f [%+.1f, %+.1f] on the same cells under the main "
                "wording --- a difference of %+.1f [%+.1f, %+.1f], not separable from zero, so "
                "wording does not account for the branch, though %d items cannot confirm it "
                "alone"
                % (100 * d5["parity_delta"], 100 * d5["parity_lo"], 100 * d5["parity_hi"],
                   100 * d5["main_delta"], 100 * d5["main_lo"], 100 * d5["main_hi"],
                   100 * d5["attenuation"], 100 * d5["att_lo"], 100 * d5["att_hi"],
                   d5["items"]))
        controls["sentence"] = ("; ".join(bits) + ".") if bits else ""
    rep["controls"] = controls

    # ---- Frontier-class check (one large model, same items, same judge, own block)
    frontier = {}
    fr_main = [r for r in frontier_rows if r["study"] == "main" and r["format"] == "structured"
               and r["judged"] and not r["is_transfer"]]
    pool_main = [r for r in judged if r["format"] == "structured"]
    if fr_main:
        fm = sorted(FRONTIER_MODELS)[0]
        frontier["model"] = fm
        frontier["n_judged_main"] = len(fr_main)

        def _cond_table(sub):
            out = {}
            for c in LADDER:
                cc = [r for r in sub if r["condition"] == c]
                out[c] = cell(cc, "joint_fidelity") if cc else {"mean": None, "n": 0}
            return out

        frontier["phi_by_condition"] = {"frontier": _cond_table(fr_main),
                                        "pool": _cond_table(pool_main)}
        frontier["phi_overall"] = {"frontier": cell(fr_main, "joint_fidelity"),
                                   "pool": cell(pool_main, "joint_fidelity")}

        # the prediction, part 1: uncertainty collapse on non-answerable items
        def _collapse(sub):
            u = [r for r in sub if r["gold_abstain"] and r["pred_answerability"]]
            return cell([dict(r, _v=(not r["abstained"])) for r in u], "_v") if u else {"mean": None, "n": 0}
        frontier["uncertainty_collapse"] = {"frontier": _collapse(fr_main), "pool": _collapse(pool_main)}

        # component preservation, pooled over conditions
        comp = {}
        for k in ("contradiction", "revision", "scope", "uncertainty"):
            def _pres(sub, k=k):
                a = [r for r in sub if r[k] in ("yes", "no")]
                return cell([dict(r, _v=(r[k] == "yes")) for r in a], "_v") if a else {"mean": None, "n": 0}
            comp[k] = {"frontier": _pres(fr_main), "pool": _pres(pool_main)}
        for k in ("answer_correct", "grounding_ok", "provenance_ok", "answerability_correct"):
            comp[k] = {"frontier": cell(fr_main, k), "pool": cell(pool_main, k)}
        frontier["components"] = comp

        # the branch, paired, frontier alone
        cells_f = {(r["question_id"], r["condition"]): r["joint_fidelity"] for r in fr_main}
        byq = collections.defaultdict(list)
        for (q, c) in list(cells_f):
            if c == "gold_source" and (q, "gold_memory_state") in cells_f:
                byq[q].append((1.0 if cells_f[(q, c)] else 0.0)
                              - (1.0 if cells_f[(q, "gold_memory_state")] else 0.0))
        if byq:
            qs = sorted(byq)
            flat = [x for q in qs for x in byq[q]]
            obs = sum(flat) / len(flat)
            _rng = random.Random(20260915)
            reps = []
            for _ in range(BOOT):
                smp = [x for q in (_rng.choice(qs) for _ in qs) for x in byq[q]]
                reps.append(sum(smp) / len(smp))
            reps.sort()
            frontier["d4_minus_d5"] = {"n": len(flat), "mean_diff": obs,
                                       "ci_lo": reps[int(0.025 * BOOT)],
                                       "ci_hi": reps[int(0.975 * BOOT)]}

        # the prediction, part 2: pushback
        fr_base = {r["question_id"]: r for r in fr_main if r["condition"] == "gold_source"}
        fr_arms = collections.defaultdict(dict)
        for r in frontier_rows:
            if r["condition"] in ("pushback_control", "pushback_pushback") and r["judged"]:
                fr_arms[r["question_id"]][r["condition"]] = r
        fr_pairs = {q: v for q, v in fr_arms.items()
                    if "pushback_control" in v and "pushback_pushback" in v and q in fr_base}
        if fr_pairs:
            pdiff = {}
            for metric, fn in [("unsupported", lambda b, r: bool(r["unsupported"])),
                               ("lost_fidelity", lambda b, r: bool(b["answer_correct"] and not r["answer_correct"])),
                               ("answer_correct", lambda b, r: bool(r["answer_correct"])),
                               ("joint_fidelity", lambda b, r: bool(r["joint_fidelity"]))]:
                per = {}
                for q, v in fr_pairs.items():
                    bb = fr_base[q]
                    per[q] = (1.0 if fn(bb, v["pushback_pushback"]) else 0.0) -                              (1.0 if fn(bb, v["pushback_control"]) else 0.0)
                qs = sorted(per)
                obs = sum(per[q] for q in qs) / len(qs)
                _rng = random.Random(20260915)
                reps = []
                for _ in range(BOOT):
                    smp = [per[_rng.choice(qs)] for _ in qs]
                    reps.append(sum(smp) / len(smp))
                reps.sort()
                pdiff[metric] = {"n": len(qs), "mean_diff": obs,
                                 "ci_lo": reps[int(0.025 * BOOT)],
                                 "ci_hi": reps[int(0.975 * BOOT)]}
            # absolute unsupported rate in each arm, for the level comparison
            for arm in ("pushback_control", "pushback_pushback"):
                a = [v[arm] for v in fr_pairs.values()]
                pdiff[arm + "_unsupported_rate"] = cell(
                    [dict(r, _v=bool(r["unsupported"])) for r in a], "_v")
            frontier["pushback"] = pdiff
            frontier["pushback_pool"] = rep.get("pushback", {}).get("paired_difference", {})
            # pool absolute unsupported rates in each arm, same comparator
            pool_arm = {}
            for arm in ("pushback_control", "pushback_pushback"):
                a = [r for r in rows if r["condition"] == arm and r["judged"] and r["model"] in ABL_MODELS]
                pool_arm[arm] = cell([dict(r, _v=bool(r["unsupported"])) for r in a], "_v")
            frontier["pushback_pool_arm_rates"] = pool_arm
    rep["frontier"] = frontier

    # ---- per-item release table
    per_item = []
    for r in rows:
        per_item.append({k: r[k] for k in
                         ["record_id", "question_id", "model", "condition", "format", "study",
                          "category", "domain", "gold_answerability", "parse_ok", "src_p", "src_r",
                          "src_f1", "pred_answerability", "answerability_correct", "status_correct",
                          "scope_cov", "fidelity", "unsupported", "contradiction", "revision",
                          "scope", "uncertainty", "provenance", "failure_mode", "joint_fidelity",
                          "all_components_ok"] if k in r})
    with open(os.path.join(OUT, "per_item_scores.jsonl"), "w", encoding="utf-8") as f:
        for p in per_item:
            f.write(json.dumps(p) + "\n")

    # ---- failure-mode distribution
    rep["failure_modes"] = {
        c: dict(collections.Counter(r["failure_mode"] for r in judged
                                    if r["condition"] == c and r["format"] == "structured"
                                    and r["failure_mode"]))
        for c in LADDER}

    json.dump(rep, open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: rep[k] for k in ("coverage", "monotonicity", "compositional_gap")
                      if k in rep}, indent=1)[:6000])
    print("\nwrote results/report.json and results/per_item_scores.jsonl")


if __name__ == "__main__":
    main()
