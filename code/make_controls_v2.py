#!/usr/bin/env python3
"""Build verified judge-validation corruptions.

Each corruption is applied only to items that carry the property it destroys, and each is
constructed so that the resulting text stays grammatical: the point is to test whether the
judge detects the named defect, not whether it dislikes mangled prose.
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(os.path.join(HERE, "data", "items.json"), encoding="utf-8"))

SENT = re.compile(r"(?<=[.;])\s+")
REFUSAL = re.compile(r"(?i)^\s*(no\b|not\b|we cannot|we can not|it is not|there is not|"
                     r"the (dialogue|evidence) does not|this cannot|one cannot)")
HEDGE = re.compile(r"(?i)\b(cannot|can not|does not|do not|not specified|unresolved|uncertain|"
                   r"insufficient|unclear|unknown|remains? open|not address|may|might)\b")


def sentences(t):
    return [x.strip() for x in SENT.split(t.strip()) if x.strip()]


def slots(it):
    d = {}
    d.update(it.get("gold_method_slots") or {})
    d.update(it.get("gold_condition_slots") or {})
    return d


def rec(it, variant, answer, note, **over):
    body = {"answer": " ".join(answer.split()),
            "status": over.get("status", it["gold_status"]),
            "answerability": over.get("answerability", it["expert_answerability_label"]),
            "source_ids": over.get("source_ids", it["gold_source_ids"]),
            "method_scope": over.get("method_scope", list((it.get("gold_method_slots") or {}).keys())),
            "condition_scope": over.get("condition_scope",
                                        list((it.get("gold_condition_slots") or {}).keys())),
            "contradiction_present": over.get("contradiction_present", True),
            "revision_occurred": over.get("revision_occurred", True)}
    return {"record_id": "%s|controlv2_%s" % (it["question_id"], variant),
            "question_id": it["question_id"], "variant": variant,
            "study": "judge_validation_v2", "note": note,
            "response_json": json.dumps(body)}


out = []
pools = collections.defaultdict(list)

# --- scope stripped ----------------------------------------------------------------
for it in items:
    sl = slots(it)
    if not sl:
        continue
    text = it["gold_final"]
    for v in sl.values():
        v = str(v).strip()
        if len(v) > 4 and v.lower() in text.lower():
            text = re.sub(re.escape(v), "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).replace(" ,", ",").replace(" .", ".")
    text = (text.rstrip(". ") + ". This conclusion applies generally, independent of the "
            "particular assay, protocol, material, or experimental conditions used.")
    out.append(rec(it, "scope_stripped", text,
                   "slot values deleted and a generality claim appended",
                   method_scope=[], condition_scope=[]))
    pools["scope_stripped"].append(it["question_id"])

# --- contradiction flattened -------------------------------------------------------
for it in items:
    if not (it["category"] in ("contradiction_resolution", "uncertainty_abstention")
            or it["primary_failure_mode"] in ("contradiction_blindness", "uncertainty_collapse")):
        continue
    ss = [x for x in sentences(it["gold_final"]) if len(x) >= 25]
    head = ss[0] if ss else it["gold_final"]
    text = (head.rstrip(". ") + ". The sources are consistent with one another on this point, so "
            "there is no unresolved conflict to carry forward.")
    out.append(rec(it, "contradiction_flattened", text,
                   "one side kept, agreement asserted",
                   status="supported", answerability="answerable",
                   contradiction_present=False))
    pools["contradiction_flattened"].append(it["question_id"])

# --- revision lost -----------------------------------------------------------------
for it in items:
    if it["category"] not in ("temporal_claim_revision", "hypothesis_tracking"):
        continue
    claim = it["arc_core_claim"].rstrip(". ")
    text = ("The position is unchanged: %s. This remains the accepted view, and no later result "
            "in the thread has revised it." % claim)
    out.append(rec(it, "revision_lost", text,
                   "superseded original claim presented as current",
                   status="supported", answerability="answerable",
                   contradiction_present=False, revision_occurred=False))
    pools["revision_lost"].append(it["question_id"])

# --- uncertainty collapsed ---------------------------------------------------------
for it in items:
    if it["expert_answerability_label"] == "answerable":
        continue
    ss = [x for x in sentences(it["gold_final"])
          if not REFUSAL.match(x) and not HEDGE.search(x) and len(x) >= 25]
    body = " ".join(ss)
    if len(body) < 40:
        body = "The cited sources determine the answer for the queried case"
    text = ("Yes. " + body[0].upper() + body[1:].rstrip(". ") +
            ". The available evidence is sufficient to settle this definitively; no residual "
            "uncertainty remains.")
    out.append(rec(it, "uncertainty_collapsed", text,
                   "refusal clause removed and a definitive verdict asserted",
                   status="supported", answerability="answerable"))
    pools["uncertainty_collapsed"].append(it["question_id"])

# --- provenance swapped ------------------------------------------------------------
for it in items:
    ids = it["gold_source_ids"]
    if not ids:
        continue
    wrong = ["ms10_p2" if not i.startswith("ms10") else "cb01_p1" for i in ids]
    out.append(rec(it, "provenance_swapped", it["gold_final"],
                   "source identifiers replaced with unrelated ones", source_ids=wrong))
    pools["provenance_swapped"].append(it["question_id"])

# --- unsupported addition ----------------------------------------------------------
for it in items:
    text = (it["gold_final"].rstrip(". ") + ". A subsequent multi-site replication confirmed this "
            "quantitatively, reporting agreement within 3 % across every condition tested.")
    out.append(rec(it, "unsupported_addition", text, "fabricated quantitative claim appended"))
    pools["unsupported_addition"].append(it["question_id"])

# --- gold verbatim, the acceptance baseline ----------------------------------------
covered = set()
for v, qs in pools.items():
    covered |= set(qs)
byid = {i["question_id"]: i for i in items}
for q in sorted(covered):
    it = byid[q]
    out.append(rec(it, "gold_verbatim", it["gold_final"], "unmodified expert gold answer"))

path = os.path.join(HERE, "data", "judge_controls_v2.jsonl")
with open(path, "w", encoding="utf-8") as f:
    for o in out:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
print(len(out), dict(collections.Counter(o["variant"] for o in out)))
