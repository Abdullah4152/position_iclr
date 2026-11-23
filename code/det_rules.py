#!/usr/bin/env python3
"""Deterministic, judge-free decision rules for the components of Phi.

Every rule takes the gold record and the parsed structured response and returns
True (component preserved), False (component violated) or None (not applicable to
this item).  The point is that Phi can be recomputed without a language model for
the components where a rule suffices, so that a reader can reimplement the metric
and so that the least reliable judged component can be ablated.

Thresholds are stated here once and are the only place they are defined.
"""
from __future__ import annotations
import re

SRC_RECALL_MIN = 0.5          # fraction of gold source ids that must be cited
SRC_PRECISION_MIN = 0.5       # fraction of cited ids that must be gold
SCOPE_COVERAGE_MIN = 0.5      # fraction of gold scope slots that must surface

HEDGE = re.compile(
    r"(?i)\b(cannot|can not|can't|not (?:possible|determined|specified|clear|established)|"
    r"does not (?:specify|establish|determine|address)|do not (?:specify|establish)|"
    r"insufficient|unresolved|uncertain|unclear|unknown|indeterminate|ambiguous|"
    r"remains? open|no (?:definitive|conclusive)|not enough|neither confirm)\b")
DEFINITIVE = re.compile(
    r"(?i)\b(definitively|conclusively|settles?|settled|no residual uncertainty|"
    r"beyond doubt|it is certain|clearly establishes)\b")
CONTRAST = re.compile(
    r"(?i)\b(however|whereas|in contrast|by contrast|conflict|conflicting|contradict|"
    r"disagree|tension|inconsistent|but |although|while )")
REVISION = re.compile(
    r"(?i)\b(revis|superseded|no longer|updated|overturn|refuted|corrected|later (?:work|evidence|"
    r"result)|subsequent(?:ly)?|initially|originally|previously (?:held|thought|believed))")


def _f(x):
    return x if isinstance(x, (int, float)) else None


def phi_provenance(gold_ids, pred_ids):
    """Cited sources must cover the gold set and not be dominated by wrong ones."""
    if not gold_ids:
        return None
    if not pred_ids:
        return False
    tp = len(set(pred_ids) & set(gold_ids))
    recall = tp / len(set(gold_ids))
    precision = tp / len(set(pred_ids))
    return recall >= SRC_RECALL_MIN and precision >= SRC_PRECISION_MIN


def phi_answerability(gold_label, pred_label):
    """Three-way label must match the expert label exactly."""
    if pred_label is None:
        return False
    return pred_label == gold_label


def phi_status(gold_status, pred_status):
    if not isinstance(pred_status, str) or not pred_status.strip():
        return False
    return pred_status.strip() == gold_status


def phi_uncertainty(gold_label, pred_label, answer_text):
    """On items the experts marked ambiguous or unanswerable, the response must
    decline to resolve them: the label must not be `answerable`, the prose must
    carry a hedge, and it must not assert that the matter is settled."""
    if gold_label == "answerable":
        return None
    txt = answer_text or ""
    if pred_label == "answerable":
        return False
    if DEFINITIVE.search(txt):
        return False
    return bool(HEDGE.search(txt))


def phi_scope(gold_slots, coverage):
    """Gold method/condition slots must surface in the scope fields or the prose."""
    if not gold_slots:
        return None
    c = _f(coverage)
    if c is None:
        return False
    return c >= SCOPE_COVERAGE_MIN


def phi_contradiction(gold_flag, pred_flag, answer_text):
    """Where the gold record carries a conflict, the response must mark it, either
    in the structured flag or with an explicit contrast in the prose."""
    if not gold_flag:
        return None
    if pred_flag is True:
        return True
    return bool(CONTRAST.search(answer_text or ""))


def phi_revision(gold_flag, pred_flag, answer_text):
    """Where the gold record carries a revision, the response must mark it."""
    if not gold_flag:
        return None
    if pred_flag is True:
        return True
    return bool(REVISION.search(answer_text or ""))


def score_response(item, parsed, answer_text, pred_ids, scope_cov):
    """Return the deterministic verdict for every component of one response."""
    p = parsed or {}
    return {
        "provenance": phi_provenance([s.lower() for s in item["gold_source_ids"]],
                                     [s.lower() for s in pred_ids]),
        "answerability": phi_answerability(item["expert_answerability_label"],
                                           p.get("_norm_answerability")),
        "status": phi_status(item["gold_status"], p.get("status")),
        "uncertainty": phi_uncertainty(item["expert_answerability_label"],
                                       p.get("_norm_answerability"), answer_text),
        "scope": phi_scope({**(item.get("gold_method_slots") or {}),
                            **(item.get("gold_condition_slots") or {})}, scope_cov),
        "contradiction": phi_contradiction(item.get("_contradiction_flag"),
                                           p.get("contradiction_present"), answer_text),
        "revision": phi_revision(item.get("_revision_flag"),
                                 p.get("revision_occurred"), answer_text),
    }
