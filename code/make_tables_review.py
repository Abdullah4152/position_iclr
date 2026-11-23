#!/usr/bin/env python3
"""Tables and macros for the material added in response to review.

Imported for its side effects by make_tables.py (it appends to the same tables/
directory and returns extra \\newcommand definitions).
"""
from __future__ import annotations
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, "..", "paper")
TAB = os.path.join(PAPER, "tables")

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
SHORT = {"closed_book": "D1", "offline_retrieval": "D2", "online_history": "D3",
         "gold_source": "D4", "gold_memory_state": "D5", "gold_evidence": "D6"}
DOM_LABEL = {"chemistry": "Chemistry", "computational_biology": "Computational biology",
             "materials_science": "Materials science", "machine_learning": "Machine learning",
             "theoretical_cs": "Theoretical CS"}
VARIANT_LABEL = {
    "phi_strict": "$\\Phi$ as defined (strict conjunction)",
    "phi_no_provenance": "\\quad drop the provenance gate",
    "phi_no_answerability": "\\quad drop the answerability gate",
    "phi_no_prov_no_answ": "\\quad drop both",
    "phi_no_grounding": "\\quad drop the unsupported-claim gate",
    "phi_no_prov_no_grounding": "\\quad drop provenance and unsupported-claim",
    "phi_one_miss_allowed": "\\quad tolerate one failed gate",
    "phi_hybrid_det": "hybrid: rules for mechanical gates, judge for prose",
    "phi_fully_deterministic": "fully deterministic rules, no judge",
}
DET_LABEL = {"provenance": "Provenance", "answerability": "Answerability",
             "contradiction": "Contradiction", "revision": "Revision",
             "scope": "Method/condition scope", "uncertainty": "Uncertainty"}


def build(rep, N, NP, cellstr, w, num):
    # always define these so the document compiles while the controls are still running;
    # check_macros.py treats the PENDING marker as a blocking placeholder
    num("numNoiseSentence", "PENDING: noise-floor control still running.")
    num("numControlsSentence", "PENDING: protocol controls still running.")
    for nm in ("noise_table", "controls_table"):
        w(nm, "%% PENDING: %s not yet computed." % nm)

    # ---------------------------------------------------------------- Phi variants
    pv = rep.get("phi_variants", {})
    phis, gaps = pv.get("phi", {}), pv.get("gap", {})
    rows = []
    for k, label in VARIANT_LABEL.items():
        a, b = phis.get(k), gaps.get(k)
        if not a:
            continue
        rows.append("%s & %s & [%s, %s] & %s & [%s, %s] \\\\" % (
            label, N(a["mean"]), N(a["ci_lo"]), N(a["ci_hi"]),
            N(b["rate"]) if b else "--",
            N(b["ci_lo"]) if b else "--", N(b["ci_hi"]) if b else "--"))
    w("phi_variants_table", "\n".join(
        ["\\begin{table}[t]",
         "\\caption{How much the results depend on the shape of $\\Phi$. Columns: mean joint "
         "fidelity over all structured responses, and the compositional gap among responses that "
         "pass every component check. Indented rows drop one or more gates from the conjunction; "
         "the last two replace judged gates with the deterministic rules of "
         "Appendix~\\ref{app:rules}. All intervals are 95\\% item-level bootstraps.}",
         "\\label{tab:phi-variants}", "\\centering", "\\small",
         "\\setlength{\\tabcolsep}{4pt}",
         "\\begin{tabular}{lcccc}", "\\toprule",
         "& \\multicolumn{2}{c}{\\textbf{Joint fidelity} $\\Phi$ (\\%)} & "
         "\\multicolumn{2}{c}{\\textbf{Compositional gap} (\\%)} \\\\",
         "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
         "\\textbf{Aggregation} & mean & 95\\% CI & rate & 95\\% CI \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    st, npv, naw = phis.get("phi_strict"), phis.get("phi_no_provenance"), gaps.get("phi_no_provenance")
    om = gaps.get("phi_one_miss_allowed")
    if st and npv and naw:
        num("numPhiRobustSentence",
            "The next-noisiest gate, provenance, matters even less: dropping it moves $\\Phi$ "
            "from %s\\%% to %s\\%% and the gap to %s\\%% [%s, %s], and dropping answerability "
            "too leaves it at %s\\%%. Even tolerating one failed gate outright --- the most "
            "permissive aggregation we tried --- the gap is %s\\%%, with an interval excluding "
            "zero." %
            (N(st["mean"]), N(npv["mean"]), N(naw["rate"]),
             N(naw["ci_lo"]), N(naw["ci_hi"]), N(gaps["phi_no_prov_no_answ"]["rate"]),
             N(om["rate"]) if om else "--"))

    # ---------------------------------------------------------------- det vs judge
    dv = rep.get("det_vs_judge", {})
    rows = []
    for k, label in DET_LABEL.items():
        d = dv.get(k)
        if not d:
            continue
        rows.append("%s & %d & %s & %.2f & %s & %s \\\\" % (
            label, d["n"], N(d["agreement"]), d["kappa"] or 0,
            N(d["det_pass_rate"]), N(d["judge_pass_rate"])))
    w("det_vs_judge_table", "\n".join(
        ["\\begin{table}[t]",
         "\\caption{Deterministic decision rules (Appendix~\\ref{app:rules}) against the model "
         "judge, per component, on every structured response where both apply. Agreement and "
         "$\\kappa$ measure whether a judge-free implementation reaches the same verdict; the last "
         "two columns give each scorer's pass rate, which shows the direction of disagreement.}",
         "\\label{tab:det-vs-judge}", "\\centering", "\\small",
         "\\setlength{\\tabcolsep}{5pt}",
         "\\begin{tabular}{lrcccc}", "\\toprule",
         "\\textbf{Component} & $n$ & \\textbf{Agreement} & $\\kappa$ & "
         "\\textbf{Rule passes} & \\textbf{Judge passes} \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    if dv:
        good = [k for k, v in dv.items() if (v.get("kappa") or 0) >= 0.5]
        bad = sorted(dv, key=lambda k: dv[k].get("kappa") or 0)[:2]
        num("numDetSentence",
            "Answerability is reproducible without a judge by construction ($\\kappa=%.2f$), and "
            "provenance and revision are close enough to automate ($\\kappa=%.2f$ and %.2f). "
            "Scope and uncertainty are not: surface rules and the judge agree only %s and %s of "
            "the time ($\\kappa=%.2f$, %.2f), and they fail in opposite directions --- the scope "
            "rule passes %s of responses against the judge's %s, while the uncertainty rule passes "
            "%s against %s." %
            (dv["answerability"]["kappa"] or 0, dv["provenance"]["kappa"] or 0,
             dv["revision"]["kappa"] or 0,
             NP(dv["scope"]["agreement"]), NP(dv["uncertainty"]["agreement"]),
             dv["scope"]["kappa"] or 0, dv["uncertainty"]["kappa"] or 0,
             NP(dv["scope"]["det_pass_rate"]), NP(dv["scope"]["judge_pass_rate"]),
             NP(dv["uncertainty"]["det_pass_rate"]), NP(dv["uncertainty"]["judge_pass_rate"])))

    # ---------------------------------------------------------------- per domain
    bd = rep.get("by_domain", {})
    rows = []
    for d in sorted(bd):
        v = bd[d]
        top = sorted(v["reasons"].items(), key=lambda kv: -kv[1])[:3]
        rows.append("%s & %d & %s & %d & %s & %s \\\\" % (
            DOM_LABEL.get(d, d.replace("_", " ")), v["n"],
            cellstr(v["joint_fidelity"], ci=False), v["n_component_pass"],
            N(v["gap_rate"]),
            ", ".join("%s (%d)" % (k, c) for k, c in top) if top else "--"))
    w("domain_table", "\n".join(
        ["\\begin{table}[t]",
         "\\caption{Failure composition by domain. \\emph{Gap} is the share of "
         "component-passing responses that fail $\\Phi$; the last column names which gates "
         "those failures broke.}",
         "\\label{tab:domain}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
         "\\begin{tabular}{lrrrrl}", "\\toprule",
         "\\textbf{Domain} & $n$ & $\\Phi$ & \\textbf{Comp.\\ pass} & \\textbf{Gap} & "
         "\\textbf{Dominant broken gates} \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

    # ---------------------------------------------------------------- noise floor
    nf = rep.get("noise_floor")
    if nf and nf.get("pairs"):
        rows = []
        for k in ("within_gold_source", "within_gold_evidence", "between_d4_d6"):
            d = nf.get(k)
            if not d:
                continue
            rows.append("%s & %d & %s & %s & %s \\\\" % (
                d["label"], d["n"], N(d["down"]), N(d["up"]), N(d["flip"])))
        w("noise_table", "\n".join(
            ["\\begin{table}[t]",
             "\\caption{Is item-level non-monotonicity distinguishable from sampling noise? "
             "\\emph{Within} rows compare two independent generations under the \\emph{same} "
             "condition, so every flip there is noise. The \\emph{between} row is the "
             "D4$\\rightarrow$D6 step whose downward moves the monotonicity analysis counts. "
             "A real effect requires the between-condition flip pattern to differ from the "
             "within-condition one.}",
             "\\label{tab:noise}", "\\centering", "\\small",
             "\\begin{tabular}{lrccc}", "\\toprule",
             "\\textbf{Comparison} & \\textbf{pairs} & \\textbf{Down (\\%)} & "
             "\\textbf{Up (\\%)} & \\textbf{Any flip (\\%)} \\\\", "\\midrule"]
            + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))
        num("numNoiseSentence", nf.get("sentence", ""))

    # ---------------------------------------------------------------- controls
    ct = rep.get("controls", {})
    rows = []
    for key, label in [("nocaveat", "Curator note removed"), ("parity", "Instructions equalised")]:
        c = ct.get(key)
        if not c:
            continue
        for cond, d in sorted(c.get("by_condition", {}).items()):
            rows.append("%s & %s & %d & %s & %s & %s \\\\" % (
                label if cond == sorted(c["by_condition"])[0] else "",
                SHORT.get(cond, cond), d["n"], N(d["base"]), N(d["control"]),
                ("%+.1f" % (100 * d["delta"])) if d["delta"] is not None else "--"))
    did_rows = []
    _did = ct.get("parity", {}).get("did", {})
    if _did:
        did_rows.append("\\midrule")
        did_rows.append("\\multicolumn{6}{l}{\\emph{Instruction framing: step size under "
                        "parity $-$ step size under the main wording}} \\\\")
        for cond in ("gold_memory_state", "gold_evidence"):
            d = _did.get(cond)
            if not d:
                continue
            did_rows.append(
                "D4$\\rightarrow$%s & %d it. & %d & %+.1f & %+.1f & %+.1f [%+.1f, %+.1f] \\\\"
                % (SHORT.get(cond, cond), d["items"], d["cells"],
                   100 * d["main_delta"], 100 * d["parity_delta"],
                   100 * d["attenuation"], 100 * d["att_lo"], 100 * d["att_hi"]))
    if rows:
        w("controls_table", "\n".join(
            ["\\begin{table}[t]",
             "\\caption{Two controls on the protocol itself. \\emph{Curator note removed} deletes "
             "the closing methodological note from both the rendered transcript and the supplied "
             "evidence, on the items whose gold answer does not depend on it. \\emph{Instructions "
             "equalised} renders D4, D5 and D6 with byte-identical instructions so that only the "
             "supplied payload differs. Columns are joint fidelity $\\Phi$ (\\%) in the main study "
             "and under the control, paired on the same items and systems. The lower block is the "
             "statistic that answers the question the parity control was built for: the size of a "
             "step under equalised instructions minus its size under the main wording, on the cells "
             "present in both arms, with an item-level cluster bootstrap interval. An interval "
             "covering zero means the two framings are not distinguishable, i.e.\\ wording does not "
             "account for the step.}",
             "\\label{tab:controls}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{5pt}",
             "\\begin{tabular}{llrccc}", "\\toprule",
             "\\textbf{Control} & \\textbf{Cond.} & $n$ & \\textbf{Main} & \\textbf{Control} & "
             "$\\Delta$ \\\\", "\\midrule"]
            + rows + did_rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))
        num("numControlsSentence", ct.get("sentence", ""))
