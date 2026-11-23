#!/usr/bin/env python3
"""Build the three controlled studies the reviews asked for.

  noise     repeated independent generations at D4 and D6, so that the
            item-level non-monotonicity rate can be compared against a
            within-condition noise floor.
  nocaveat  D3 and D4 with the curator note removed from both the rendered
            transcript and the supplied evidence, testing whether systems
            were pattern-matching benchmark-construction commentary.
  parity    D4, D5 and D6 rendered with byte-identical instructions, so that
            the D5 branch effect cannot be attributed to instruction framing.

Writes iclr_work/data/payload_review.jsonl.
"""
from __future__ import annotations
import json, os, re, collections, random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SEED = 20260914

items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
transcripts = json.load(open(os.path.join(DATA, "transcripts.json"), encoding="utf-8"))
byid = {i["question_id"]: i for i in items}

# the exact strings the main build used, so the controls differ only where intended
PREAMBLE = ("You are a research assistant maintaining scientific memory across a multi-session "
            "literature dialogue. Source identifiers look like cb01_p2 or ch07_p3.")
RULES = ("Preserve what the evidence actually supports: keep contradictions unresolved when they are "
         "unresolved, keep method and condition scope attached to claims, keep revisions of earlier "
         "claims visible, and do not convert missing or conflicting evidence into a definitive answer.")
STATUS_VOCAB = ["supported", "supported_within_scope", "supported_by_cross_paper_synthesis",
                "revised_by_later_evidence", "mixed_with_preserved_contradiction",
                "mixed_or_conditional", "insufficient_evidence", "refuted"]
STRUCT_TAIL = (
    "\n\nRespond with a single JSON object and nothing else, using exactly these keys:\n"
    '{"answer": "<at most 120 words>", '
    '"status": "<one of: ' + " | ".join(STATUS_VOCAB) + '>", '
    '"answerability": "<answerable | ambiguous | unanswerable>", '
    '"source_ids": ["<source ids you rely on>"], '
    '"method_scope": ["<method constraints that bound the answer, [] if none>"], '
    '"condition_scope": ["<condition constraints that bound the answer, [] if none>"], '
    '"contradiction_present": <true|false>, '
    '"revision_occurred": <true|false>}'
)


def state_record(it, include_evidence):
    arc_claim = it["arc_core_claim"]
    rec = {
        "claim_topic": it["question"],
        "initial_hypothesis": arc_claim,
        "status": it["gold_status"],
        "answerability": it["expert_answerability_label"],
        "supporting_evidence_ids": it["gold_source_ids"],
        "contradiction_present": it["_contradiction_flag"],
        "revision_occurred": it["_revision_flag"],
        "method_scope": it["gold_method_slots"] or "not specified in dialogue",
        "condition_scope": it["gold_condition_slots"] or "not specified in dialogue",
        "revision_trace": it["_revision_trace"],
        "cross_session_required": it["requires_cross_session_memory"] == "True",
        "cross_paper_required": it["requires_cross_paper_reasoning"] == "True",
    }
    if include_evidence:
        rec["evidence_text"] = it["evidence_text"]
    return rec


# recover the flags and revision trace exactly as the main build produced them, by
# re-reading the record embedded in the already-rendered D5 prompts
main_payload = [json.loads(l) for l in
                open(os.path.join(DATA, "payload.jsonl"), encoding="utf-8")]
d5_by_item = {p["question_id"]: p["prompt"] for p in main_payload
              if p["condition"] == "gold_memory_state" and p["format"] == "structured"}
for it in items:
    prompt = d5_by_item.get(it["question_id"], "")
    m = re.search(r"Information-state record:\n(\{.*?\n\})\n\n", prompt, re.S)
    rec = json.loads(m.group(1)) if m else {}
    it["_contradiction_flag"] = rec.get("contradiction_present", False)
    it["_revision_flag"] = rec.get("revision_occurred", False)
    it["_revision_trace"] = rec.get("revision_trace", [])

# ---------------------------------------------------------------- caveat stripping
CAVEAT_Q = "Researcher: Any methodological caveat I should record for this thread?"


def strip_caveat_sessions(sessions):
    out = []
    for s in sessions:
        lines = [ln for ln in s.split("\n")
                 if CAVEAT_Q not in ln and "Noted for the record:" not in ln]
        out.append("\n".join(lines))
    return out


NOTE_LINE = re.compile(r"^source_arc:[^\n]*expert_note[^\n]*$", re.M)


def strip_note_evidence(evidence_text):
    return NOTE_LINE.sub("", evidence_text).strip()


CONTENT = re.compile(r"[a-z]{5,}")
STOP = {"which", "these", "their", "there", "where", "between", "because", "under", "about",
        "study", "studies", "evidence", "arc", "claim", "claims", "paper", "papers", "source"}


def note_dependence(it):
    """How much of the gold answer's vocabulary lives only in the curator note."""
    note = " ".join(NOTE_LINE.findall(it["evidence_text"])).lower()
    if not note.strip():
        return 0.0
    body = NOTE_LINE.sub("", it["evidence_text"]).lower()
    gold = set(CONTENT.findall(it["gold_final"].lower())) - STOP
    if not gold:
        return 0.0
    note_only = {w for w in gold if w in note and w not in body}
    return len(note_only) / len(gold)


# ---------------------------------------------------------------- prompt builders
def render_main_style(it, condition):
    """The prompts as the main study rendered them (for the noise replicates)."""
    for p in main_payload:
        if (p["question_id"] == it["question_id"] and p["condition"] == condition
                and p["format"] == "structured" and p["study"] == "main"):
            return p["prompt"]
    raise KeyError((it["question_id"], condition))


def render_nocaveat(it, condition):
    tr = transcripts[it["source_arc_id"]]
    if condition == "online_history":
        body = (f"{PREAMBLE}\n\nBelow is the complete multi-session dialogue history you have "
                f"accumulated with this researcher. It interleaves several research threads in "
                f"chronological order.\n\n" + "\n\n".join(strip_caveat_sessions(tr["sessions"])) +
                f"\n\n{RULES}\n\nQuestion: {it['question']}")
    elif condition == "gold_source":
        body = (f"{PREAMBLE}\n\nThe gold supporting sources for this question have been retrieved "
                f"for you.\n\nSource IDs: {', '.join(it['gold_source_ids'])}\n"
                f"Evidence text:\n{strip_note_evidence(it['evidence_text'])}\n\n{RULES}\n\n"
                f"Question: {it['question']}")
    else:
        raise ValueError(condition)
    return body + STRUCT_TAIL


PARITY_FRAME = ("{p}\n\nThe following material has been supplied to you for this question. Use it, "
                "and nothing else, to answer.\n\n{payload}\n\n{r}\n\nQuestion: {q}")


def render_parity(it, condition):
    if condition == "gold_source":
        payload = ("Source IDs: %s\nEvidence text:\n%s"
                   % (", ".join(it["gold_source_ids"]), it["evidence_text"]))
    elif condition == "gold_memory_state":
        payload = ("Information-state record:\n%s"
                   % json.dumps(state_record(it, False), indent=2))
    elif condition == "gold_evidence":
        payload = ("Information-state record:\n%s"
                   % json.dumps(state_record(it, True), indent=2))
    else:
        raise ValueError(condition)
    return PARITY_FRAME.format(p=PREAMBLE, payload=payload, r=RULES,
                               q=it["question"]) + STRUCT_TAIL


# ---------------------------------------------------------------- sampling
rng = random.Random(SEED)


def stratified(pool, n):
    """Take n items spread evenly over capability categories, deterministically."""
    bycat = collections.defaultdict(list)
    for it in pool:
        bycat[it["category"]].append(it)
    for c in bycat:
        bycat[c].sort(key=lambda x: x["question_id"])
        rng.shuffle(bycat[c])
    out, cats = [], sorted(bycat)
    i = 0
    while len(out) < n and any(bycat[c] for c in cats):
        c = cats[i % len(cats)]
        if bycat[c]:
            out.append(bycat[c].pop())
        i += 1
    return sorted(out, key=lambda x: x["question_id"])


N_NOISE, N_NOCAVEAT, N_PARITY = 100, 90, 90

noise_items = stratified(items, N_NOISE)
# the caveat ablation must not use items whose gold answer depends on the note
clean = [it for it in items if note_dependence(it) <= 0.02]
nocaveat_items = stratified(clean, min(N_NOCAVEAT, len(clean)))
parity_items = stratified(items, N_PARITY)

payload = []
for it in noise_items:
    for cond in ("gold_source", "gold_evidence"):
        base = render_main_style(it, cond)
        for rep in (1, 2):
            payload.append({"record_id": "%s|%s|structured|rep%d" % (it["question_id"], cond, rep),
                            "question_id": it["question_id"], "condition": cond,
                            "format": "structured", "study": "noise", "replicate": rep,
                            "prompt": base})

for it in nocaveat_items:
    for cond in ("online_history", "gold_source"):
        payload.append({"record_id": "%s|%s|structured|nocaveat" % (it["question_id"], cond),
                        "question_id": it["question_id"], "condition": cond,
                        "format": "structured", "study": "nocaveat",
                        "prompt": render_nocaveat(it, cond)})

for it in parity_items:
    for cond in ("gold_source", "gold_memory_state", "gold_evidence"):
        payload.append({"record_id": "%s|%s|structured|parity" % (it["question_id"], cond),
                        "question_id": it["question_id"], "condition": cond,
                        "format": "structured", "study": "parity",
                        "prompt": render_parity(it, cond)})

with open(os.path.join(DATA, "payload_review.jsonl"), "w", encoding="utf-8") as f:
    for p in payload:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

report = {
    "seed": SEED,
    "noise_items": len(noise_items), "nocaveat_items": len(nocaveat_items),
    "parity_items": len(parity_items),
    "note_dependent_items_excluded": len(items) - len(clean),
    "records": len(payload),
    "records_by_study": dict(collections.Counter(p["study"] for p in payload)),
}
json.dump(report, open(os.path.join(DATA, "review_build_report.json"), "w",
                       encoding="utf-8"), indent=1)
print(json.dumps(report, indent=1))
