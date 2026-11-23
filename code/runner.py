#!/usr/bin/env python3
"""Generic NVIDIA-NIM runner for the scientific-memory study.

Runs anywhere (local CPU or a Kaggle CPU notebook); all work is API-bound.

  python runner.py sut    --model M --payload payload.jsonl --out responses_M.jsonl
  python runner.py judge  --model J --responses responses_M.jsonl --items items.json \
                          --out judgments_M.jsonl
  python runner.py triage --model M --payload triage_payload.jsonl --out triage_M.jsonl

Every subcommand is resumable: existing record ids in --out are skipped.
"""
from __future__ import annotations
import argparse, json, os, random, re, sys, threading, time
import concurrent.futures as cf
import urllib.request, urllib.error

API = "https://integrate.api.nvidia.com/v1/chat/completions"
LOCK = threading.Lock()

# models that emit long hidden reasoning need a bigger completion budget
BIG_BUDGET = ("nemotron", "gpt-oss", "kimi", "deepseek", "glm")
HUGE_BUDGET = ("lightning", "nano-omni", "kimi-k3")


def load_keys(path):
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def chat(messages, model, keys, max_tokens, temperature=0.0, attempts=8, timeout=300,
         extra=None):
    """One chat completion with key rotation and backoff. Returns (content, meta)."""
    last = None
    for a in range(attempts):
        key = random.choice(keys)
        body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature}
        if extra:
            body.update(extra)
        data = json.dumps(body).encode()
        req = urllib.request.Request(API, data=data, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json",
            "Accept": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.loads(r.read().decode())
            msg = j["choices"][0]["message"]
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            usage = j.get("usage", {}) or {}
            if not content.strip():
                last = "empty_content"
                time.sleep(1.5 * (a + 1))
                continue
            if j["choices"][0].get("finish_reason") == "length" and a < 2:
                last = "truncated"
                max_tokens = int(max_tokens * 1.6)
                continue
            return content, {"attempts": a + 1, "latency_s": round(time.time() - t0, 2),
                             "prompt_tokens": usage.get("prompt_tokens"),
                             "completion_tokens": usage.get("completion_tokens"),
                             "reasoning_chars": len(reasoning),
                             "finish_reason": j["choices"][0].get("finish_reason")}
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                last = "http%d:%s" % (code, e.read().decode()[:160])
            except Exception:
                last = "http%d" % code
            if code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** a + random.random() * 2, 30))
                continue
            return None, {"error": last, "attempts": a + 1}
        except Exception as e:                                   # timeouts, resets
            last = type(e).__name__ + ":" + str(e)[:120]
            time.sleep(min(2 ** a + random.random() * 2, 30))
    return None, {"error": last, "attempts": attempts}


FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text):
    """Best-effort recovery of the single JSON object a model was asked for."""
    if not text:
        return None
    m = FENCE.search(text)
    cands = []
    if m:
        cands.append(m.group(1))
    cands.append(text)
    for c in cands:
        c = c.strip()
        i, j = c.find("{"), c.rfind("}")
        if i == -1 or j == -1 or j < i:
            continue
        blob = c[i:j + 1]
        for attempt in (blob, blob.replace("\n", " "),
                        re.sub(r",\s*([}\]])", r"\1", blob),
                        re.sub(r"(?<![\\])'", '"', blob)):
            try:
                o = json.loads(attempt)
                if isinstance(o, dict):
                    return o
            except Exception:
                pass
        # last resort: first balanced object
        depth = 0
        for k, ch in enumerate(blob):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        o = json.loads(blob[:k + 1])
                        if isinstance(o, dict):
                            return o
                    except Exception:
                        break
    return None


def done_ids(path):
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["record_id"])
                except Exception:
                    pass
    return seen


def write(path, obj):
    with LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()


# ---------------------------------------------------------------------------
# SUT
# ---------------------------------------------------------------------------
def run_sut(args):
    keys = load_keys(args.keys)
    recs = [json.loads(l) for l in open(args.payload, encoding="utf-8")]
    if args.studies:
        keep = set(args.studies.split(","))
        recs = [r for r in recs if r["study"] in keep]
    seen = done_ids(args.out)
    todo = [r for r in recs if r["record_id"] + "|" + args.model not in seen]
    print("[sut] %s: %d/%d to run" % (args.model, len(todo), len(recs)), flush=True)
    budget = args.max_tokens or (6500 if any(b in args.model for b in HUGE_BUDGET)
                                 else 4000 if any(b in args.model for b in BIG_BUDGET) else 1500)
    n = [0]

    def one(r):
        msgs = [{"role": "user", "content": r["prompt"]}]
        content, meta = chat(msgs, args.model, keys, budget)
        turn2 = None
        if content is not None and r.get("followup"):
            msgs2 = msgs + [{"role": "assistant", "content": content},
                            {"role": "user", "content": r["followup"]}]
            turn2, meta2 = chat(msgs2, args.model, keys, budget)
            meta["turn2"] = meta2
        final = turn2 if r.get("followup") else content
        out = dict(r)
        out.pop("prompt", None)
        out.pop("followup", None)
        out.update({"record_id": r["record_id"] + "|" + args.model, "model": args.model,
                    "raw": final, "raw_turn1": content if r.get("followup") else None,
                    "parsed": extract_json(final) if r["format"] == "structured" else None,
                    "meta": meta})
        write(args.out, out)
        n[0] += 1
        if n[0] % 25 == 0:
            print("[sut] %s %d/%d" % (args.model, n[0], len(todo)), flush=True)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(one, todo))
    print("[sut] %s done" % args.model, flush=True)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------
JUDGE_TMPL = """You are grading one response from a research assistant against an expert-validated gold record. Grade only what the gold record and gold evidence support. Be strict and literal.

QUESTION:
{question}

GOLD ANSWER (expert-validated):
{gold}

GOLD EVIDENCE:
{evidence}

GOLD LABELS:
- answerability: {answerability}
- claim status: {status}
- gold source ids: {source_ids}
- method scope that must be preserved: {method_slots}
- condition scope that must be preserved: {condition_slots}
- capability under test: {category}

RESPONSE TO GRADE:
{response}

Grade with these definitions:
- answer_fidelity: "correct" if the response conveys the gold conclusion with the same strength and the same qualifications; "partial" if the core conclusion is right but a qualification, scope, or side of the evidence is missing or weakened; "incorrect" if it contradicts the gold conclusion or answers a different question.
- unsupported_claim: true if the response asserts any specific fact, number, mechanism, condition, or attribution that the gold answer and gold evidence do not support.
- contradiction_preserved: "yes" if conflicting or competing evidence is kept visible; "no" if it is flattened into agreement; "na" if the gold record contains no conflict.
- revision_preserved: "yes" if the response reflects that later evidence revised an earlier claim; "no" if it presents a superseded claim as current; "na" if the gold record contains no revision.
- scope_preserved: "yes" if the method and condition limits above are attached to the claim; "no" if the claim is stated more generally than the gold scope allows; "na" if the gold record has no scope limits.
- uncertainty_preserved: "yes" if unresolved, insufficient, or conditional evidence stays unresolved; "no" if it is converted into a definitive answer; "na" if the gold record is definitive.
- provenance_correct: "yes" if claims are attributed to the gold sources; "no" if attributed to the wrong source or attributed without support; "na" if the response makes no attribution and none was required.
- primary_failure_mode: one of hypothesis_drift, unsupported_claim_recall, evidence_source_confusion, contradiction_blindness, outdated_claim_persistence, method_condition_mismatch, uncertainty_collapse, none.

Respond with one JSON object only:
{{"answer_fidelity": "correct|partial|incorrect", "unsupported_claim": true|false, "contradiction_preserved": "yes|no|na", "revision_preserved": "yes|no|na", "scope_preserved": "yes|no|na", "uncertainty_preserved": "yes|no|na", "provenance_correct": "yes|no|na", "primary_failure_mode": "<one label>", "justification": "<one sentence>"}}"""


def response_text(rec):
    if rec.get("parsed") and isinstance(rec["parsed"], dict):
        p = rec["parsed"]
        parts = [str(p.get("answer", "")).strip()]
        for k in ("status", "answerability"):
            if p.get(k):
                parts.append("[%s=%s]" % (k, p[k]))
        for k in ("source_ids", "method_scope", "condition_scope"):
            v = p.get(k)
            if v:
                parts.append("[%s=%s]" % (k, ", ".join(map(str, v)) if isinstance(v, list) else v))
        for k in ("contradiction_present", "revision_occurred"):
            if k in p:
                parts.append("[%s=%s]" % (k, p[k]))
        return " ".join(x for x in parts if x)
    return (rec.get("raw") or "").strip()[:4000]


JUDGE_EXTRA = None


def run_judge(args):
    global JUDGE_EXTRA
    JUDGE_EXTRA = {"chat_template_kwargs": {"enable_thinking": False}} if args.no_think else None
    keys = load_keys(args.keys)
    items = {i["question_id"]: i for i in json.load(open(args.items, encoding="utf-8"))}
    if args.transfer_items and os.path.exists(args.transfer_items):
        for i in json.load(open(args.transfer_items, encoding="utf-8")):
            items[i["question_id"]] = i
    recs = []
    for path in args.responses.split(","):
        if os.path.exists(path):
            recs += [json.loads(l) for l in open(path, encoding="utf-8")]
    recs = [r for r in recs if r.get("raw")]
    if args.subsample < 1.0:
        rr = random.Random(7)
        recs = [r for r in recs if rr.random() < args.subsample]
    seen = done_ids(args.out)
    tagm = args.model + (args.tag or "")
    todo = [r for r in recs if r["record_id"] + "|J:" + tagm not in seen]
    print("[judge] %s: %d/%d to grade" % (args.model, len(todo), len(recs)), flush=True)
    budget = args.max_tokens or 2500
    n = [0]

    def one(r):
        it = items.get(r["question_id"])
        if it is None:
            return
        prompt = JUDGE_TMPL.format(
            question=it["question"], gold=it["gold_final"],
            evidence=it["evidence_text"][:3000],
            answerability=it["expert_answerability_label"], status=it["gold_status"],
            source_ids=", ".join(it["gold_source_ids"]),
            method_slots=json.dumps(it["gold_method_slots"]) or "{}",
            condition_slots=json.dumps(it["gold_condition_slots"]) or "{}",
            category=it["category"], response=response_text(r))
        content, meta = chat([{"role": "user", "content": prompt}], args.model, keys, budget,
                             extra=JUDGE_EXTRA)
        write(args.out, {"record_id": r["record_id"] + "|J:" + args.model + (args.tag or ""),
                         "target_record_id": r["record_id"], "question_id": r["question_id"],
                         "sut_model": r.get("model"), "condition": r.get("condition"),
                         "format": r.get("format"), "study": r.get("study"),
                         "judge_model": args.model + (args.tag or ""),
                         "judgment": extract_json(content),
                         "raw": content if args.keep_raw else None, "meta": meta})
        n[0] += 1
        if n[0] % 50 == 0:
            print("[judge] %s %d/%d" % (args.model, n[0], len(todo)), flush=True)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(one, todo))
    print("[judge] %s done" % args.model, flush=True)


# ---------------------------------------------------------------------------
# Judge validation controls
# ---------------------------------------------------------------------------
def run_controls(args):
    keys = load_keys(args.keys)
    items = {i["question_id"]: i for i in json.load(open(args.items, encoding="utf-8"))}
    recs = [json.loads(l) for l in open(args.payload, encoding="utf-8")]
    seen = done_ids(args.out)
    todo = [r for r in recs if r["record_id"] + "|J:" + args.model not in seen]
    print("[controls] %s: %d to grade" % (args.model, len(todo)), flush=True)

    def one(r):
        it = items[r["question_id"]]
        fake = {"parsed": json.loads(r["response_json"]), "raw": r["response_json"],
                "question_id": r["question_id"]}
        prompt = JUDGE_TMPL.format(
            question=it["question"], gold=it["gold_final"],
            evidence=it["evidence_text"][:3000],
            answerability=it["expert_answerability_label"], status=it["gold_status"],
            source_ids=", ".join(it["gold_source_ids"]),
            method_slots=json.dumps(it["gold_method_slots"]) or "{}",
            condition_slots=json.dumps(it["gold_condition_slots"]) or "{}",
            category=it["category"], response=response_text(fake))
        content, meta = chat([{"role": "user", "content": prompt}], args.model, keys,
                             args.max_tokens or 2500)
        write(args.out, {"record_id": r["record_id"] + "|J:" + args.model,
                         "question_id": r["question_id"], "variant": r["variant"],
                         "judge_model": args.model, "judgment": extract_json(content),
                         "meta": meta})

    with cf.ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(one, todo))
    print("[controls] done", flush=True)


# ---------------------------------------------------------------------------
# Annotation triage
# ---------------------------------------------------------------------------
def run_triage(args):
    keys = load_keys(args.keys)
    recs = [json.loads(l) for l in open(args.payload, encoding="utf-8")]
    seen = done_ids(args.out)
    todo = [r for r in recs if r["record_id"] + "|" + args.model not in seen]
    print("[triage] %s: %d to run" % (args.model, len(todo)), flush=True)

    def one(r):
        content, meta = chat([{"role": "user", "content": r["prompt"]}], args.model, keys,
                             args.max_tokens or 2500)
        write(args.out, {"record_id": r["record_id"] + "|" + args.model,
                         "question_id": r["question_id"], "model": args.model,
                         "parsed": extract_json(content), "meta": meta})

    with cf.ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(one, todo))
    print("[triage] done", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["sut", "judge", "controls", "triage"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--payload")
    ap.add_argument("--responses")
    ap.add_argument("--items")
    ap.add_argument("--transfer-items")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keys", default="keys.txt")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-tokens", type=int, default=0, dest="max_tokens")
    ap.add_argument("--studies", default="")
    ap.add_argument("--subsample", type=float, default=1.0)
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--no-think", action="store_true", dest="no_think")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    random.seed(12345)
    {"sut": run_sut, "judge": run_judge, "controls": run_controls, "triage": run_triage}[a.task](a)


if __name__ == "__main__":
    main()
