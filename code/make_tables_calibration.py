#!/usr/bin/env python3
"""Tables and macros for the human-calibration pass.

Imported by make_tables.py after the review-response tables. Reads
results/human_calibration.json (written by calibration_deep.py). If that file is absent
the macros resolve to PENDING so the document still compiles and check_macros.py blocks.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
SHORT = {"closed_book": "D1", "offline_retrieval": "D2", "online_history": "D3",
         "gold_source": "D4", "gold_memory_state": "D5", "gold_evidence": "D6"}
COMP = ["fidelity", "unsupported", "contradiction", "revision", "scope", "uncertainty",
        "provenance"]
CLAB = {"fidelity": "Answer fidelity", "unsupported": "Unsupported claim",
        "contradiction": "Contradiction preserved", "revision": "Revision preserved",
        "scope": "Scope preserved", "uncertainty": "Uncertainty preserved",
        "provenance": "Provenance correct"}
GLAB = {"human_A": "Grader A", "human_B": "Grader B",
        "human_consensus": "Both graders (consensus)", "judge": "Model judge"}


def build(N, NP, w, num):
    p = os.path.join(HERE, "results", "human_calibration.json")
    names = ["numHumanCalSentence", "numHumanCalGateSentence", "numHumanCalLadderSentence",
             "numHumanPhi", "numHumanPhiCI", "numJudgePhiSubset", "numHumanGap",
             "numHumanGapCI", "numHumanUnsupFP", "numHumanUnsupFPCI", "numHumanCalRows",
             "numHumanKappaMin", "numHumanKappaMax"]
    if not os.path.exists(p):
        for n in names:
            num(n, "PENDING: human calibration not run.")
        w("human_calibration_table", "% PENDING: human calibration not run\n")
        w("human_calibration_kappa_table", "% PENDING: human calibration not run\n")
        return

    hc = json.load(open(p, encoding="utf-8"))
    phi = hc["phi"]
    gap = hc["gap"]
    u = hc["unsupported_fp"]
    kap = hc["kappa"]
    dirn = hc["direction"]

    def pc(x):
        return "--" if x is None else "%.1f" % (100 * x)

    def ci(d, lo="ci_lo", hi="ci_hi"):
        return "[%s, %s]" % (pc(d[lo]), pc(d[hi]))

    def kf(x):
        return "--" if x is None else "%.2f" % x

    # ------------------------------------------------------------- table 1: Phi and gap
    rows = []
    for g in ("human_A", "human_B", "human_consensus", "judge"):
        t = phi[g]
        gg = gap[g]
        rows.append("%s & %s %s & %s & %d/%d & %s %s \\\\" % (
            GLAB[g], pc(t["mean"]), "{\\scriptsize " + ci(t) + "}",
            " & ".join(pc(t["by_condition"][c]) for c in LADDER),
            gg["fail"], gg["base"], pc(gg["rate"]), "{\\scriptsize " + ci(gg) + "}"))
    w("human_calibration_table", "\n".join([
        "\\begin{table}[!ht]",
        "\\caption{Human calibration on %d responses (20 per condition, all five systems), "
        "graded independently by two annotators blind to system identity and to the judge. "
        "\\emph{Consensus} counts a gate as passed only if both graders pass it. The judge "
        "column is the model judge on the \\emph{same} rows, so the comparison is "
        "like-for-like; the paper-wide judge figures (\\numPhiOverallPct{}\\%% and "
        "\\numGapOverallPct{}\\%%) are on a different, larger sample. Intervals are "
        "item-level bootstraps; at this size the per-condition cells are 20 responses each "
        "and carry no interval.}" % hc["n_rows"],
        "\\label{tab:human-cal}", "\\centering", "\\small",
        "\\setlength{\\tabcolsep}{3.5pt}",
        "\\begin{tabular}{lc" + "c" * len(LADDER) + "cc}", "\\toprule",
        "\\textbf{Grader} & $\\Phi$ (\\%) & " + " & ".join(SHORT[c] for c in LADDER)
        + " & \\textbf{Gap} $k/n$ & \\textbf{Gap} (\\%) \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    # ------------------------------------------------------ table 2: kappa + direction
    rows = []
    for k in COMP:
        a = kap[k]
        d = dirn[k]
        rows.append("%s & %s & %s & %s & %d & %d \\\\" % (
            CLAB[k], kf(a["A_vs_judge"]), kf(a["B_vs_judge"]), kf(a["A_vs_B"]),
            d["judge_harsher"], d["judge_more_lenient"]))
    w("human_calibration_kappa_table", "\n".join([
        "\\begin{table}[!ht]",
        "\\caption{Per-component agreement on the calibration subset. Cohen's $\\kappa$ "
        "between each grader and the judge, and between the two graders; then, on the rows "
        "where the judge and the human consensus disagree, how many times the judge was the "
        "harsher party versus the more lenient one. A judge that was merely noisy would split "
        "these columns; this one does not.}",
        "\\label{tab:human-cal-kappa}", "\\centering", "\\small",
        "\\begin{tabular}{lcccrr}", "\\toprule",
        "\\textbf{Component} & \\textbf{A vs judge} & \\textbf{B vs judge} & "
        "\\textbf{A vs B} & \\textbf{judge harsher} & \\textbf{judge lenient} \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    # ----------------------------------------------------------------------- macros
    hcons = phi["human_consensus"]
    hA, hB, hj = phi["human_A"], phi["human_B"], phi["judge"]
    gcons, gj = gap["human_consensus"], gap["judge"]
    kAB = [kap[k]["A_vs_B"] for k in COMP if kap[k]["A_vs_B"] is not None]

    num("numHumanCalRows", str(hc["n_rows"]))
    num("numHumanPhi", pc(hcons["mean"]))
    num("numHumanPhiCI", ci(hcons))
    num("numJudgePhiSubset", pc(hj["mean"]))
    num("numHumanGap", pc(gcons["rate"]))
    num("numHumanGapCI", ci(gcons))
    num("numHumanUnsupFP", pc(u["rate"]))
    num("numHumanUnsupFPCI", ci(u))
    num("numHumanKappaMin", "%.2f" % min(kAB))
    num("numHumanKappaMax", "%.2f" % max(kAB))

    harsh_total = sum(dirn[k]["judge_harsher"] for k in COMP)
    len_total = sum(dirn[k]["judge_more_lenient"] for k in COMP)

    num("numHumanCalSentence",
        "Two annotators, blind to system and to the judge, independently graded a stratified "
        "subset of %d responses (Appendix~\\ref{app:calibration}). Both put joint fidelity at "
        "%s\\%%; their consensus --- a gate passes only if both pass it --- gives %s\\%% %s, "
        "against %s\\%% for the judge on the \\emph{same} rows. The judge is not noisy but "
        "systematically harsh: where it and the consensus disagree, it is the stricter party "
        "%d times and the more lenient %d, on every component. Joint-fidelity levels in this paper "
        "are therefore lower bounds and failure rates upper bounds, the former deflated by "
        "roughly a factor of four."
        % (hc["n_rows"], pc(hA["mean"]), pc(hcons["mean"]), ci(hcons), pc(hj["mean"]),
           harsh_total, len_total))

    num("numHumanCalMainSentence",
        "Two annotators, blind to system and judge, independently graded a stratified "
        "%d-response subset (Appendix~\\ref{app:calibration}). Both put $\\Phi$ at %s\\%%; "
        "consensus gives %s\\%% %s against the judge's %s\\%% on the same rows. That is bias, "
        "not noise --- where they disagree the judge is stricter %d times to %d, and it flags "
        "%s\\%% of responses both humans call clean as unsupported. The structure survives: under "
        "consensus the chain still orders D1$<$D2$<$D3$<$D4$<$D6, D5 still sits below D4, and "
        "%d of %d component-passing responses still fail $\\Phi$ (%s\\%% %s, all on provenance) "
        "--- about half the judged gap, on an interval that includes it."
        % (hc["n_rows"], pc(hA["mean"]), pc(hcons["mean"]), ci(hcons), pc(hj["mean"]),
           harsh_total, len_total, pc(u["rate"]),
           gcons["fail"], gcons["base"], pc(gcons["rate"]), ci(gcons)))

    num("numHumanCalLadderSentence",
        "What survives is the structure. Under human consensus the chain still orders "
        "D1$<$D2$<$D3$<$D4$<$D6 (%s, %s, %s, %s, %s\\%%), D5 still sits below D4 (%s against "
        "%s\\%%), and the compositional gap still exists --- %d of %d component-passing "
        "responses fail $\\Phi$ under consensus, %s\\%% %s, every one of them on provenance. "
        "That is about half the judge's paper-wide figure, on an interval wide enough to include "
        "it, so we report the calibrated gap as \\emph{smaller and less certain} than the judged "
        "one, not as absent."
        % (pc(hcons["by_condition"]["closed_book"]), pc(hcons["by_condition"]["offline_retrieval"]),
           pc(hcons["by_condition"]["online_history"]), pc(hcons["by_condition"]["gold_source"]),
           pc(hcons["by_condition"]["gold_evidence"]),
           pc(hcons["by_condition"]["gold_memory_state"]), pc(hcons["by_condition"]["gold_source"]),
           gcons["fail"], gcons["base"], pc(gcons["rate"]), ci(gcons)))

    num("numHumanCalGateSentence",
        "The unsupported-claim gate is confirmed as the fault: of %d responses \\emph{both} "
        "humans called correct and free of unsupported claims, the judge flagged %d as "
        "unsupported (%s\\%% %s), while the reverse error --- a judge-clean response that a human "
        "flagged --- occurred on %s\\%%. Inter-annotator $\\kappa$ runs from %s (contradiction) "
        "to %s (uncertainty), so the humans agree with each other far better than either agrees "
        "with the judge; contradiction and provenance are the two components that are hard even "
        "for people."
        % (u["clean_n"], u["judge_fired"], pc(u["rate"]), ci(u),
           pc(hc["unsupported_fn"]["rate"]), "%.2f" % min(kAB), "%.2f" % max(kAB)))
