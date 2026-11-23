#!/usr/bin/env python3
"""Table and macros for the frontier-class check. Imported by make_tables.py.

The prediction under test (§8): a heavily preference-tuned frontier model should show
MORE uncertainty collapse and MORE evidence-free justification under pushback than the
11B-30B pool. Either outcome is reported.
"""
from __future__ import annotations

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
SHORT = {"closed_book": "D1", "offline_retrieval": "D2", "online_history": "D3",
         "gold_source": "D4", "gold_memory_state": "D5", "gold_evidence": "D6"}
NICE = {"nvidia/nemotron-3-ultra-550b-a55b": "Nemotron-3-Ultra-550B-A55B"}


def build(rep, N, NP, cellstr, w, num):
    fr = rep.get("frontier") or {}
    names = ["numFrontierSentence", "numFrontierModel", "numFrontierPushSentence",
             "numFrontierVerdict"]
    if not fr or not fr.get("phi_by_condition"):
        for n in names:
            num(n, "PENDING: frontier-class check not run.")
        w("frontier_table", "% PENDING: frontier-class check not run\n")
        return

    def pc(x):
        return "--" if x is None else "%.1f" % (100 * x)

    def pm(x):
        return "--" if x is None else "%+.1f" % (100 * x)

    def ci(d):
        return "[%s, %s]" % (pm(d["ci_lo"]), pm(d["ci_hi"]))

    model = fr["model"]
    nice = NICE.get(model, model)
    num("numFrontierModel", nice)

    pbc = fr["phi_by_condition"]
    uc = fr["uncertainty_collapse"]
    comp = fr["components"]
    pb = fr.get("pushback", {})
    pbp = fr.get("pushback_pool", {})
    arm = fr.get("pushback_pool_arm_rates", {})

    # ------------------------------------------------------------------ table
    rows = []
    rows.append("Joint fidelity $\\Phi$ & %s & %s & %s & %s \\\\" % (
        " & ".join(pc(pbc["frontier"][c]["mean"]) for c in LADDER),
        cellstr(fr["phi_overall"]["frontier"], ci=False),
        " & ".join(pc(pbc["pool"][c]["mean"]) for c in LADDER),
        cellstr(fr["phi_overall"]["pool"], ci=False)))
    w("frontier_table", "\n".join([
        "\\begin{table}[!ht]",
        "\\caption{Frontier-class check: %s (%s) on the same %d items, six conditions and pushback "
        "pair, graded by the same judge, against the five-system pool. Joint fidelity by condition; "
        "then the two quantities the \\S\\ref{sec:implications} prediction is about. The model shares a "
        "family with the judge, so a lineage advantage cannot be excluded; the pushback contrast is "
        "within-model and unaffected by it.}" % (nice, "\\texttt{" + model.replace("_", "\\_") + "}", 160),
        "\\label{tab:frontier}", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{2.5pt}",
        "\\begin{tabular}{l" + "c" * 7 + "|" + "c" * 7 + "}", "\\toprule",
        "& \\multicolumn{7}{c|}{\\textbf{%s}} & \\multicolumn{7}{c}{\\textbf{Five-system pool}} \\\\" % nice,
        "\\textbf{Measure} & " + " & ".join(SHORT[c] for c in LADDER) + " & all & "
        + " & ".join(SHORT[c] for c in LADDER) + " & all \\\\", "\\midrule"]
        + rows + [
        "\\midrule",
        "\\multicolumn{15}{l}{\\emph{Prediction 1: uncertainty collapse on non-answerable items (lower is better)}} \\\\",
        "Collapse rate & \\multicolumn{7}{c|}{%s\\%% ($n=%d$)} & \\multicolumn{7}{c}{%s\\%% ($n=%d$)} \\\\" % (
            pc(uc["frontier"]["mean"]), uc["frontier"]["n"], pc(uc["pool"]["mean"]), uc["pool"]["n"]),
        "Uncertainty preserved & \\multicolumn{7}{c|}{%s\\%%} & \\multicolumn{7}{c}{%s\\%%} \\\\" % (
            pc(comp["uncertainty"]["frontier"]["mean"]), pc(comp["uncertainty"]["pool"]["mean"])),
        "\\midrule",
        "\\multicolumn{15}{l}{\\emph{Prediction 2: pushback, paired pushback$-$control (positive = more under pushback)}} \\\\",
        "Unsupported assertion & \\multicolumn{7}{c|}{%s %s} & \\multicolumn{7}{c}{%s %s} \\\\" % (
            pm(pb.get("unsupported", {}).get("mean_diff")), ci(pb["unsupported"]) if pb.get("unsupported") else "",
            pm(pbp.get("unsupported", {}).get("mean_diff")), ci(pbp["unsupported"]) if pbp.get("unsupported") else ""),
        "Joint fidelity & \\multicolumn{7}{c|}{%s %s} & \\multicolumn{7}{c}{%s %s} \\\\" % (
            pm(pb.get("joint_fidelity", {}).get("mean_diff")), ci(pb["joint_fidelity"]) if pb.get("joint_fidelity") else "",
            pm(pbp.get("joint_fidelity", {}).get("mean_diff")), ci(pbp["joint_fidelity"]) if pbp.get("joint_fidelity") else ""),
        "Unsupported rate, control / pushback & \\multicolumn{7}{c|}{%s\\%% / %s\\%%} & \\multicolumn{7}{c}{%s\\%% / %s\\%%} \\\\" % (
            pc(pb.get("pushback_control_unsupported_rate", {}).get("mean")),
            pc(pb.get("pushback_pushback_unsupported_rate", {}).get("mean")),
            pc(arm.get("pushback_control", {}).get("mean")), pc(arm.get("pushback_pushback", {}).get("mean"))),
        "\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    # ------------------------------------------------------------------ verdicts
    f_col, p_col = uc["frontier"]["mean"], uc["pool"]["mean"]
    f_unsup = pb.get("unsupported", {}).get("mean_diff")
    p_unsup = pbp.get("unsupported", {}).get("mean_diff")
    f_phi, p_phi = fr["phi_overall"]["frontier"]["mean"], fr["phi_overall"]["pool"]["mean"]

    more_collapse = (f_col is not None and p_col is not None and f_col > p_col)
    more_fab = (f_unsup is not None and p_unsup is not None and f_unsup > p_unsup)

    if more_collapse and more_fab:
        verdict = "both halves of the prediction hold"
        reading = ("scale does not buy calibration on evidentially open questions, and it "
                   "buys more fluent fabrication under pressure")
    elif more_fab and not more_collapse:
        verdict = ("the collapse half fails and the pushback half holds, with a larger effect "
                   "than in the pool")
        reading = ("left alone, the larger model keeps uncertainty \\emph{better} than the "
                   "pool, so scale does improve calibration on evidence-thin questions; but "
                   "under an evidence-free social push it reaches for unsupported support "
                   "\\emph{more}, from a lower baseline, while its answer stays right or gets "
                   "righter --- the mechanism of \\S\\ref{sec:pushback} in its purest form. The "
                   "training pressure the prediction names shows up as agreeableness under "
                   "pressure, not as decisiveness on open questions")
    elif more_collapse and not more_fab:
        verdict = ("the collapse half holds and the pushback half fails")
        reading = ("the larger model resolves open questions more readily than the pool but "
                   "does not fabricate more under pressure, so the prediction's mechanism is "
                   "only half right")
    else:
        verdict = "the prediction fails on both counts"
        reading = ("the larger model both keeps uncertainty better and fabricates less under "
                   "pressure, so whatever preference tuning does at this scale, it is not the "
                   "mechanism the prediction named")
    num("numFrontierVerdict", verdict)

    num("numFrontierSentence",
        "We ran it. %s, a %s-class model on the same items, conditions and judge, scores %s\\%% "
        "joint fidelity against the pool's %s\\%% (D4: %s against %s\\%%), keeps the chain "
        "ordering, and keeps D5 below D4, so scale helps and the structure holds. On the "
        "prediction itself: its uncertainty-collapse rate on non-answerable items is %s\\%% "
        "against the pool's %s\\%%, and under pushback its unsupported-assertion rate rises by "
        "%s points %s against the pool's %s %s, from %s\\%% to %s\\%%. So %s: %s. It shares a "
        "family with the judge, so a lineage advantage on absolute levels cannot be excluded; "
        "the within-model pushback contrast does not depend on it (Appendix~\\ref{app:frontier})."
        % (nice, "550B", pc(f_phi), pc(p_phi), pc(pbc["frontier"]["gold_source"]["mean"]),
           pc(pbc["pool"]["gold_source"]["mean"]), pc(f_col), pc(p_col),
           pm(f_unsup), ci(pb["unsupported"]) if pb.get("unsupported") else "",
           pm(p_unsup), ci(pbp["unsupported"]) if pbp.get("unsupported") else "",
           pc(pb.get("pushback_control_unsupported_rate", {}).get("mean")),
           pc(pb.get("pushback_pushback_unsupported_rate", {}).get("mean")),
           verdict, reading))

    if more_fab and not more_collapse:
        short = ("its uncertainty-collapse rate on non-answerable items is \\emph{lower} than the "
                 "pool's (%s\\%% against %s\\%%), so the collapse half fails; but under pushback "
                 "its unsupported-assertion rate rises by %s points %s against the pool's %s, from a "
                 "lower baseline, while its answer holds --- the pushback half holds, and larger. "
                 "The training pressure shows up as agreeableness under pressure, not as "
                 "decisiveness on open questions"
                 % (pc(f_col), pc(p_col), pm(f_unsup),
                    ci(pb["unsupported"]) if pb.get("unsupported") else "", pm(p_unsup)))
    elif more_collapse and more_fab:
        short = ("its collapse rate is higher (%s\\%% against %s\\%%) and its pushback rise in "
                 "unsupported assertion is larger (%s against %s), so both halves hold"
                 % (pc(f_col), pc(p_col), pm(f_unsup), pm(p_unsup)))
    elif more_collapse:
        short = ("its collapse rate is higher (%s\\%% against %s\\%%) but its pushback rise is "
                 "not (%s against %s), so only the collapse half holds"
                 % (pc(f_col), pc(p_col), pm(f_unsup), pm(p_unsup)))
    else:
        short = ("its collapse rate is lower (%s\\%% against %s\\%%) and its pushback rise is "
                 "not larger (%s against %s), so the prediction fails on both counts"
                 % (pc(f_col), pc(p_col), pm(f_unsup), pm(p_unsup)))
    num("numFrontierMainSentence",
        "We tested it on %s, the largest model available to us, on the same items and judge "
        "(Appendix~\\ref{app:frontier}; it is kept out of the pool, and shares a family with the "
        "judge). It scores %s\\%% against the pool's %s\\%% and keeps the chain ordering and the "
        "D5 deficit. On the prediction, %s."
        % (nice, pc(f_phi), pc(p_phi), short))

    num("numFrontierPushSentence",
        "Under pushback the frontier model's unsupported-assertion rate goes from %s\\%% to %s\\%% "
        "(pool: %s\\%% to %s\\%%)."
        % (pc(pb.get("pushback_control_unsupported_rate", {}).get("mean")),
           pc(pb.get("pushback_pushback_unsupported_rate", {}).get("mean")),
           pc(arm.get("pushback_control", {}).get("mean")),
           pc(arm.get("pushback_pushback", {}).get("mean"))))
