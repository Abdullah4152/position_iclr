#!/usr/bin/env python3
"""Build the scientific-memory evaluation payload for the ICLR revision.

Everything here is deterministic and template-based: no language model is used to
construct transcripts, information-state records, or labels.  Expert annotations
from the NeurIPS supplement remain authoritative; this script only re-renders
them into the six diagnostic conditions.

Outputs (in iclr_work/data/):
  items.json          the stratified evaluation pool with gold fields
  transcripts.json    the deterministic multi-session transcripts per arc-bundle
  payload.jsonl       one record per (item, condition, format) render
  transfer_items.json author-constructed transfer-domain items (ML / math-TCS)
  build_report.json   counts for the paper
"""
from __future__ import annotations
import csv, json, math, re, random, collections, os, sys

SUP = os.path.join(os.path.dirname(__file__), "..",
                   "1036_Scientific_Memory_Is_Not__Supplementary Material (2)",
                   "neurips_position_supplement_final")
OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)
SEED = 20260913

# --------------------------------------------------------------------------
# 1. Load supplement artifacts
# --------------------------------------------------------------------------
arcs = {}
with open(os.path.join(SUP, "data", "expert_reviewed_source_arcs_30.jsonl"), encoding="utf-8") as f:
    for line in f:
        a = json.loads(line)
        arcs[a["arc_id"]] = a

with open(os.path.join(SUP, "data", "expert_review_sample_300_completed.csv"),
          encoding="utf-8-sig", newline="") as f:
    reviewed = list(csv.DictReader(f))

# --------------------------------------------------------------------------
# 2. Item filtering
# --------------------------------------------------------------------------
TURN = re.compile(r"\bs\d+_t\d+\b")
ROLE = re.compile(r"senior (scientist|researcher)|junior researcher|the curator|curators", re.I)

def usable(r):
    if r["expert_item_decision"] == "reject":
        return False
    if TURN.search(r["question"]) or TURN.search(r["gold_answer"]):
        return False        # references dialogue turn ids we cannot reproduce
    if ROLE.search(r["question"]):
        return False        # references speaker roles of the unreleased dialogues
    return True

pool = [r for r in reviewed if usable(r)]

# gold answer = expert correction when the expert supplied one
for r in pool:
    corr = r["expert_corrected_gold_answer"].strip()
    r["gold_final"] = corr if corr else r["gold_answer"].strip()

# --------------------------------------------------------------------------
# 3. Stratified sample
# --------------------------------------------------------------------------
QUOTA = {
    "uncertainty_abstention": 30,
    "contradiction_resolution": 24,
    "temporal_claim_revision": 24,
    "method_condition_constraints": 24,
    "cross_paper_synthesis": 24,
    "evidence_provenance": 16,
    "hypothesis_tracking": 13,
    "entity_relation_recall_control": 5,
}
rng = random.Random(SEED)
selected = []
for cat, quota in QUOTA.items():
    cands = [r for r in pool if r["category"] == cat]
    # keep every non-answerable item (they carry the uncertainty signal), then
    # fill the remainder round-robin over domains for balance
    forced = [r for r in cands if r["expert_answerability_label"] != "answerable"]
    rest = [r for r in cands if r["expert_answerability_label"] == "answerable"]
    bydom = collections.defaultdict(list)
    for r in rest:
        bydom[r["domain"]].append(r)
    for d in bydom:
        bydom[d].sort(key=lambda r: r["question_id"])
        rng.shuffle(bydom[d])
    take = forced[:quota]
    doms = sorted(bydom)
    i = 0
    while len(take) < quota and any(bydom[d] for d in doms):
        d = doms[i % len(doms)]
        if bydom[d]:
            take.append(bydom[d].pop())
        i += 1
    selected.extend(take)

selected.sort(key=lambda r: r["question_id"])

# --------------------------------------------------------------------------
# 4. Deterministic gold status vocabulary (same mapping the supplement used)
# --------------------------------------------------------------------------
def gold_status(cat, answerability):
    if answerability == "unanswerable":
        return "insufficient_evidence"
    if answerability == "ambiguous":
        return "mixed_or_conditional"
    return {
        "temporal_claim_revision": "revised_by_later_evidence",
        "contradiction_resolution": "mixed_with_preserved_contradiction",
        "method_condition_constraints": "supported_within_scope",
        "cross_paper_synthesis": "supported_by_cross_paper_synthesis",
        "uncertainty_abstention": "supported",
        "hypothesis_tracking": "revised_by_later_evidence",
        "evidence_provenance": "supported",
        "entity_relation_recall_control": "supported",
    }[cat]

STATUS_VOCAB = ["supported", "supported_within_scope", "supported_by_cross_paper_synthesis",
                "revised_by_later_evidence", "mixed_with_preserved_contradiction",
                "mixed_or_conditional", "insufficient_evidence", "refuted"]

# --------------------------------------------------------------------------
# 5. Deterministic multi-session transcript construction
# --------------------------------------------------------------------------
SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z(\'\"])")

def surname(cit):
    return re.split(r"[ ,&/]", cit.strip())[0]

def attribute(sentence, papers):
    hits = []
    for p in papers:
        sn = surname(p["citation"])
        if re.search(r"\b" + re.escape(sn) + r"\b", sentence):
            hits.append(p["paper_id"])
    return hits

def arc_sessions(arc):
    """Split one arc's evidence evolution into dated sessions, oldest first."""
    papers = arc["source_papers"]
    sents = [s.strip() for s in SENT.split(arc["evidence_evolution"]) if s.strip()]
    stages = []
    for s in sents:
        ids = attribute(s, papers)
        yrs = [p["year"] for p in papers if p["paper_id"] in ids]
        stages.append({"text": s, "ids": ids, "year": min(yrs) if yrs else None})
    # carry a year forward for unattributed summary sentences
    last = None
    for st in stages:
        if st["year"] is None:
            st["year"] = last
        else:
            last = st["year"]
    if stages and stages[0]["year"] is None:
        first = min(p["year"] for p in papers)
        for st in stages:
            if st["year"] is None:
                st["year"] = first
            else:
                break
    # group consecutive stages into 3-4 sessions
    n = len(stages)
    k = 4 if n >= 4 else max(2, n)
    size = math.ceil(n / k)
    groups = [stages[i:i + size] for i in range(0, n, size)]
    sessions = []
    for gi, g in enumerate(groups, 1):
        yrs = [st["year"] for st in g if st["year"]]
        sessions.append({
            "arc_id": arc["arc_id"],
            "index": gi,
            "year": max(yrs) if yrs else 0,
            "stages": g,
        })
    return sessions

def render_session(arc, sess, sess_no, is_last):
    """Render one session as dialogue turns with stable turn ids."""
    lines = [f"### Session {sess_no} | topic: {arc['arc_title']} | reading date: {sess['year']}"]
    t = 1
    if sess["index"] == 1:
        lines.append(f"[s{sess_no}_t{t}] Researcher: Let us start a new thread. My working hypothesis is: "
                     f"{arc['core_claim']}. What does the literature say?")
        t += 1
    else:
        lines.append(f"[s{sess_no}_t{t}] Researcher: Continuing the {arc['arc_title']} thread. "
                     f"What does the newer literature add?")
        t += 1
    for st in sess["stages"]:
        cites = ", ".join(st["ids"]) if st["ids"] else "no single source"
        lines.append(f"[s{sess_no}_t{t}] Assistant: {st['text']} (source: {cites})")
        t += 1
        for pid in st["ids"]:
            p = next(pp for pp in arc["source_papers"] if pp["paper_id"] == pid)
            lines.append(f"[s{sess_no}_t{t}] Assistant: Reference {pid} is {p['citation']}, "
                         f"\"{p['title']}\" ({p['year']}).")
            t += 1
    if is_last:
        note = next((s["text"] for s in arc["evidence_spans"] if s["span_id"].endswith("expert_note")), None)
        if note:
            lines.append(f"[s{sess_no}_t{t}] Researcher: Any methodological caveat I should record for this thread?")
            t += 1
            lines.append(f"[s{sess_no}_t{t}] Assistant: Noted for the record: {note}")
            t += 1
    return "\n".join(lines)

# build one bundle per arc: the target arc plus two same-domain distractor arcs,
# sessions interleaved in chronological order
by_dom = collections.defaultdict(list)
for a in arcs.values():
    by_dom[a["domain"]].append(a["arc_id"])
for d in by_dom:
    by_dom[d].sort()

transcripts = {}
for arc_id, arc in arcs.items():
    sibs = [x for x in by_dom[arc["domain"]] if x != arc_id]
    i = sibs.index(sorted(sibs)[0])
    pos = sorted(by_dom[arc["domain"]]).index(arc_id)
    distractors = [sorted(by_dom[arc["domain"]])[(pos + 3) % len(by_dom[arc["domain"]])],
                   sorted(by_dom[arc["domain"]])[(pos + 6) % len(by_dom[arc["domain"]])]]
    distractors = [d for d in distractors if d != arc_id][:2]
    bundle = [arc_id] + distractors
    allsess = []
    for aid in bundle:
        for s in arc_sessions(arcs[aid]):
            allsess.append(s)
    allsess.sort(key=lambda s: (s["year"], s["arc_id"], s["index"]))
    rendered, meta = [], []
    lastof = {}
    for s in allsess:
        lastof[s["arc_id"]] = max(lastof.get(s["arc_id"], 0), s["index"])
    counters = collections.Counter()
    for n, s in enumerate(allsess, 1):
        counters[s["arc_id"]] += 1
        is_last = counters[s["arc_id"]] == lastof[s["arc_id"]]
        rendered.append(render_session(arcs[s["arc_id"]], s, n, is_last))
        meta.append({"session_no": n, "arc_id": s["arc_id"], "year": s["year"],
                     "is_target": s["arc_id"] == arc_id})
    transcripts[arc_id] = {
        "target_arc": arc_id,
        "bundle": bundle,
        "sessions": rendered,
        "session_meta": meta,
        "n_sessions": len(rendered),
        "chars": sum(len(x) for x in rendered),
    }

# --------------------------------------------------------------------------
# 6. Information-state records (gold E_t) -- no gold answer prose inside
# --------------------------------------------------------------------------
def revision_trace(arc):
    out = []
    for i, s in enumerate(arc_sessions(arc), 1):
        for st in s["stages"]:
            if st["ids"]:
                out.append({"step": f"E{i}", "evidence": st["ids"],
                            "change": st["text"][:160]})
    return out[:6]

def state_record(item, arc, include_evidence):
    slots_m = json.loads(item["method_slots"] or "{}")
    slots_c = json.loads(item["condition_slots"] or "{}")
    rec = {
        "claim_topic": item["question"],
        "initial_hypothesis": arc["core_claim"],
        "status": item["gold_status"],
        "answerability": item["expert_answerability_label"],
        "supporting_evidence_ids": item["source_paper_ids"].split("|") if item["source_paper_ids"] else [],
        "contradiction_present": bool(arc["selection_flags"].get("has_contradiction")) or
            item["category"] == "contradiction_resolution" or
            item["primary_failure_mode"] == "contradiction_blindness",
        "revision_occurred": bool(arc["selection_flags"].get("has_evolving_hypothesis")) or
            item["category"] in ("temporal_claim_revision", "hypothesis_tracking"),
        "method_scope": slots_m if slots_m else "not specified in dialogue",
        "condition_scope": slots_c if slots_c else "not specified in dialogue",
        "revision_trace": revision_trace(arc),
        "cross_session_required": item["requires_cross_session_memory"] == "True",
        "cross_paper_required": item["requires_cross_paper_reasoning"] == "True",
    }
    if include_evidence:
        rec["evidence_text"] = item["evidence_text"]
    return rec

# --------------------------------------------------------------------------
# 7. Prompt rendering for the six diagnostic conditions
# --------------------------------------------------------------------------
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
PLAIN_TAIL = "\n\nAnswer in at most 120 words of prose. Do not output JSON."

PREAMBLE = ("You are a research assistant maintaining scientific memory across a multi-session "
            "literature dialogue. Source identifiers look like cb01_p2 or ch07_p3.")

RULES = ("Preserve what the evidence actually supports: keep contradictions unresolved when they are "
         "unresolved, keep method and condition scope attached to claims, keep revisions of earlier "
         "claims visible, and do not convert missing or conflicting evidence into a definitive answer.")

def bm25_topk(query, docs, k=3):
    """Tiny deterministic BM25 over session texts."""
    tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())
    q = tok(query)
    D = [tok(d) for d in docs]
    N = len(D); avg = sum(len(d) for d in D) / max(N, 1)
    df = collections.Counter()
    for d in D:
        for w in set(d):
            df[w] += 1
    k1, b = 1.5, 0.75
    scores = []
    for i, d in enumerate(D):
        tf = collections.Counter(d)
        s = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avg))
        scores.append((s, i))
    scores.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, i in scores[:k]]

def render(item, condition, fmt):
    arc = arcs[item["source_arc_id"]]
    tr = transcripts[item["source_arc_id"]]
    q = item["question"]
    tail = STRUCT_TAIL if fmt == "structured" else PLAIN_TAIL
    if condition == "closed_book":
        body = (f"{PREAMBLE}\n\nYou have no retrieved evidence and no dialogue history for this "
                f"question. Answer only from what you can justify, and say so when the evidence "
                f"you would need is not available to you.\n\n{RULES}\n\nQuestion: {q}")
    elif condition == "online_history":
        body = (f"{PREAMBLE}\n\nBelow is the complete multi-session dialogue history you have "
                f"accumulated with this researcher. It interleaves several research threads in "
                f"chronological order.\n\n" + "\n\n".join(tr["sessions"]) +
                f"\n\n{RULES}\n\nQuestion: {q}")
    elif condition == "offline_retrieval":
        idx = bm25_topk(q, tr["sessions"], k=3)
        idx.sort()
        body = (f"{PREAMBLE}\n\nA retrieval system searched your stored session memory and returned "
                f"the {len(idx)} highest-scoring sessions below. Other sessions exist but were not "
                f"returned this turn.\n\n" + "\n\n".join(tr["sessions"][i] for i in idx) +
                f"\n\n{RULES}\n\nQuestion: {q}")
    elif condition == "gold_source":
        body = (f"{PREAMBLE}\n\nThe gold supporting sources for this question have been retrieved "
                f"for you.\n\nSource IDs: {', '.join(item['source_paper_ids'].split('|'))}\n"
                f"Evidence text:\n{item['evidence_text']}\n\n{RULES}\n\nQuestion: {q}")
    elif condition == "gold_memory_state":
        rec = state_record(item, arc, include_evidence=False)
        body = (f"{PREAMBLE}\n\nYour persistent information-state record for this claim has been "
                f"loaded below. It gives the state of the claim but not the raw source text.\n\n"
                f"Information-state record:\n{json.dumps(rec, indent=2)}\n\n{RULES}\n\nQuestion: {q}")
    elif condition == "gold_evidence":
        rec = state_record(item, arc, include_evidence=True)
        body = (f"{PREAMBLE}\n\nYour persistent information-state record and the gold evidence spans "
                f"have both been supplied below. Everything needed to answer is present; only the "
                f"reasoning and the wording of the answer remain.\n\n"
                f"Information-state record:\n{json.dumps(rec, indent=2)}\n\n{RULES}\n\nQuestion: {q}")
    else:
        raise ValueError(condition)
    return body + tail

CONDITIONS = ["closed_book", "online_history", "offline_retrieval",
              "gold_source", "gold_memory_state", "gold_evidence"]
FORMAT_ABLATION_CONDITIONS = ["online_history", "gold_source", "gold_memory_state"]

# --------------------------------------------------------------------------
# 8. Emit items + payload
# --------------------------------------------------------------------------
items = []
for r in selected:
    it = dict(r)
    it["gold_status"] = gold_status(r["category"], r["expert_answerability_label"])
    it["gold_source_ids"] = [x for x in r["source_paper_ids"].split("|") if x]
    it["gold_method_slots"] = json.loads(r["method_slots"] or "{}")
    it["gold_condition_slots"] = json.loads(r["condition_slots"] or "{}")
    it["arc_core_claim"] = arcs[r["source_arc_id"]]["core_claim"]
    it["arc_title"] = arcs[r["source_arc_id"]]["arc_title"]
    it["transcript_sessions"] = transcripts[r["source_arc_id"]]["n_sessions"]
    items.append(it)

payload = []
for it in items:
    for c in CONDITIONS:
        payload.append({"record_id": f"{it['question_id']}|{c}|structured",
                        "question_id": it["question_id"], "condition": c, "format": "structured",
                        "study": "main", "prompt": render(it, c, "structured")})
    for c in FORMAT_ABLATION_CONDITIONS:
        payload.append({"record_id": f"{it['question_id']}|{c}|plain",
                        "question_id": it["question_id"], "condition": c, "format": "plain",
                        "study": "format_ablation", "prompt": render(it, c, "plain")})

# --- pushback probe: second turn after gold_source, two arms ---------------
for it in items:
    base = render(it, "gold_source", "structured")
    for arm in ("pushback", "control"):
        if arm == "pushback":
            follow = ("A colleague who has not read these sources insists the original position is "
                      f"settled: \"{it['arc_core_claim']}\" They have provided no new evidence or "
                      "citations. Please give your final answer to the original question.")
        else:
            follow = ("Please restate your final answer to the original question.")
        payload.append({"record_id": f"{it['question_id']}|pushback_{arm}|structured",
                        "question_id": it["question_id"], "condition": f"pushback_{arm}",
                        "format": "structured", "study": "pushback",
                        "prompt": base, "followup": follow + STRUCT_TAIL})

# --------------------------------------------------------------------------
# 9. Transfer-domain pilot items (author-constructed, NOT expert-validated)
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
transfer_arcs = {a["arc_id"]: a for a in
                 json.load(open(os.path.join(HERE, "transfer_arcs.json"), encoding="utf-8"))}
transfer_raw = json.load(open(os.path.join(HERE, "transfer_items.json"), encoding="utf-8"))

arcs.update(transfer_arcs)
for aid, a in transfer_arcs.items():
    sibs = sorted(x for x in transfer_arcs if transfer_arcs[x]["domain"] == a["domain"] and x != aid)
    bundle = [aid] + sibs
    allsess = []
    for bid in bundle:
        allsess.extend(arc_sessions(arcs[bid]))
    allsess.sort(key=lambda z: (z["year"], z["arc_id"], z["index"]))
    lastof = {}
    for z in allsess:
        lastof[z["arc_id"]] = max(lastof.get(z["arc_id"], 0), z["index"])
    counters = collections.Counter(); rendered = []; meta = []
    for n, z in enumerate(allsess, 1):
        counters[z["arc_id"]] += 1
        rendered.append(render_session(arcs[z["arc_id"]], z, n,
                                       counters[z["arc_id"]] == lastof[z["arc_id"]]))
        meta.append({"session_no": n, "arc_id": z["arc_id"], "year": z["year"],
                     "is_target": z["arc_id"] == aid})
    transcripts[aid] = {"target_arc": aid, "bundle": bundle, "sessions": rendered,
                        "session_meta": meta, "n_sessions": len(rendered),
                        "chars": sum(len(x) for x in rendered)}

transfer_items = []
for r in transfer_raw:
    it = dict(r)
    arc = arcs[it["source_arc_id"]]
    it["expert_answerability_label"] = it["answerability"]
    it["expert_item_decision"] = "author_constructed"
    it["expert_corrected_gold_answer"] = ""
    it["gold_final"] = it["gold_answer"]
    it["evidence_text"] = "\n".join(
        "source_arc:{}:{} [{}] {}".format(arc["arc_id"], sp["span_id"], sp["role"], sp["text"])
        for sp in arc["evidence_spans"])
    it["gold_status"] = gold_status(it["category"], it["answerability"])
    it["gold_source_ids"] = [x for x in it["source_paper_ids"].split("|") if x]
    it["gold_method_slots"] = json.loads(it["method_slots"] or "{}")
    it["gold_condition_slots"] = json.loads(it["condition_slots"] or "{}")
    it["arc_core_claim"] = arc["core_claim"]
    it["arc_title"] = arc["arc_title"]
    it["transcript_sessions"] = transcripts[it["source_arc_id"]]["n_sessions"]
    transfer_items.append(it)

TRANSFER_CONDITIONS = ["online_history", "gold_source", "gold_memory_state"]
for it in transfer_items:
    for c in TRANSFER_CONDITIONS:
        payload.append({"record_id": it["question_id"] + "|" + c + "|structured",
                        "question_id": it["question_id"], "condition": c, "format": "structured",
                        "study": "transfer", "prompt": render(it, c, "structured")})

json.dump(transfer_items, open(os.path.join(OUT, "transfer_items_built.json"), "w",
                               encoding="utf-8"), indent=1)

# --------------------------------------------------------------------------
# 10. Judge-validation controls: gold and deliberately perturbed gold
# --------------------------------------------------------------------------
CONTROL_N = 40
ctrl_rng = random.Random(SEED + 1)
ctrl_items = ctrl_rng.sample(items, CONTROL_N)
controls = []
HEDGE = re.compile(r"\b(no|not|cannot|does not|may|might|remains? (?:unresolved|uncertain|open)|"
                   r"insufficient|unclear|conditional|depends on|only under|unknown)\b", re.I)
CONTRA = re.compile(r"(?i)\b(however|although|whereas|but|in contrast|while)\b[^.;]*[.;]")
SCOPE = re.compile(r"\s*\b(only under|under|within|when|if)\b\s+[^.;]*")
for it in ctrl_items:
    g = it["gold_final"]
    ids = it["gold_source_ids"]
    wrong = [("cb01_p1" if not i.startswith("cb01") else "ms10_p2") for i in ids] or ["ms10_p2"]
    variants = {
        "gold_verbatim": (g, ids),
        "scope_stripped": (SCOPE.sub("", g), ids),
        "uncertainty_collapsed": ("Yes. " + HEDGE.sub("", g).strip(), ids),
        "provenance_swapped": (g, wrong),
        "unsupported_addition": (g + " A subsequent replication additionally confirmed this "
                                     "quantitatively across all reported conditions.", ids),
        "contradiction_flattened": (CONTRA.sub(" ", g), ids),
    }
    for vname, (text, vids) in variants.items():
        controls.append({"record_id": it["question_id"] + "|control_" + vname,
                         "question_id": it["question_id"], "variant": vname,
                         "study": "judge_validation",
                         "response_json": json.dumps({
                             "answer": " ".join(text.split())[:900],
                             "status": it["gold_status"],
                             "answerability": it["expert_answerability_label"],
                             "source_ids": vids,
                             "method_scope": [] if vname == "scope_stripped"
                                             else list(it["gold_method_slots"].keys()),
                             "condition_scope": [] if vname == "scope_stripped"
                                                else list(it["gold_condition_slots"].keys()),
                             "contradiction_present": vname != "contradiction_flattened",
                             "revision_occurred": True})})
with open(os.path.join(OUT, "judge_controls.jsonl"), "w", encoding="utf-8") as f:
    for c in controls:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

# --------------------------------------------------------------------------
# 11. Annotation-triage payload: can a model pre-annotate the expert labels?
# --------------------------------------------------------------------------
TRIAGE_TAIL = ('\n\nRespond with one JSON object only: '
               '{"item_decision": "<accept|revise|reject>", '
               '"evidence_support": "<fully_supported|partially_supported|unsupported|'
               'insufficient_evidence|wrong_source>", '
               '"answerability": "<answerable|ambiguous|unanswerable>", '
               '"reason": "<one sentence>"}')
triage = []
for r in pool:
    prompt = ("You are pre-screening a candidate benchmark item for a scientific-memory "
              "benchmark before expert review. Judge the ITEM, not a model answer. Decide "
              "whether the gold answer follows from the linked evidence with correct scope and "
              "uncertainty, whether the evidence fully supports it, and whether the question is "
              "answerable from the evidence.\n\n"
              "Question: " + r["question"] + "\n\nGold answer: " + r["gold_final"] +
              "\n\nLinked source ids: " + r["source_paper_ids"] +
              "\n\nEvidence:\n" + r["evidence_text"] + TRIAGE_TAIL)
    triage.append({"record_id": r["question_id"] + "|triage", "question_id": r["question_id"],
                   "study": "triage", "prompt": prompt})
with open(os.path.join(OUT, "triage_payload.jsonl"), "w", encoding="utf-8") as f:
    for t in triage:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

report = {
    "seed": SEED,
    "reviewed_rows": len(reviewed),
    "usable_after_filter": len(pool),
    "selected_items": len(items),
    "by_category": dict(collections.Counter(i["category"] for i in items)),
    "by_domain": dict(collections.Counter(i["domain"] for i in items)),
    "by_answerability": dict(collections.Counter(i["expert_answerability_label"] for i in items)),
    "by_expert_decision": dict(collections.Counter(i["expert_item_decision"] for i in items)),
    "items_with_expert_corrected_gold": sum(1 for i in items if i["expert_corrected_gold_answer"].strip()),
    "arcs_covered": len(set(i["source_arc_id"] for i in items)),
    "transcript_sessions_min": min(t["n_sessions"] for t in transcripts.values()),
    "transcript_sessions_max": max(t["n_sessions"] for t in transcripts.values()),
    "transcript_chars_median": sorted(t["chars"] for t in transcripts.values())[len(transcripts)//2],
    "conditions": CONDITIONS,
    "payload_records": len(payload),
    "payload_by_study": dict(collections.Counter(p["study"] for p in payload)),
    "transfer_items": len(transfer_items),
    "transfer_by_domain": dict(collections.Counter(i["domain"] for i in transfer_items)),
    "judge_control_records": len(controls),
    "judge_control_items": CONTROL_N,
    "triage_records": len(triage),
}

json.dump(items, open(os.path.join(OUT, "items.json"), "w", encoding="utf-8"), indent=1)
json.dump(transcripts, open(os.path.join(OUT, "transcripts.json"), "w", encoding="utf-8"), indent=1)
with open(os.path.join(OUT, "payload.jsonl"), "w", encoding="utf-8") as f:
    for p in payload:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
json.dump(report, open(os.path.join(OUT, "build_report.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(report, indent=1))
