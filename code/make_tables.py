#!/usr/bin/env python3
"""Turn results/report.json into the LaTeX tables and \newcommand numbers the paper uses.

Every number in the paper comes from here; nothing is typed by hand.
"""
from __future__ import annotations
import json, os, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
PAPER = os.path.join(HERE, "..", "paper")
TAB = os.path.join(PAPER, "tables")
os.makedirs(TAB, exist_ok=True)

rep = json.load(open(os.path.join(RES, "report.json"), encoding="utf-8"))
build = json.load(open(os.path.join(HERE, "data", "build_report.json"), encoding="utf-8"))

LADDER = ["closed_book", "offline_retrieval", "online_history",
          "gold_source", "gold_memory_state", "gold_evidence"]
CHAIN = ["closed_book", "offline_retrieval", "online_history", "gold_source", "gold_evidence"]
SHORT = {"closed_book": "D1", "offline_retrieval": "D2", "online_history": "D3",
         "gold_source": "D4", "gold_memory_state": "D5", "gold_evidence": "D6"}
LONG = {"closed_book": "D1 closed book", "offline_retrieval": "D2 retrieval-restricted",
        "online_history": "D3 full history", "gold_source": "D4 gold source",
        "gold_memory_state": "D5 gold memory state", "gold_evidence": "D6 gold evidence"}
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
REASON_LABEL = {"scope": "method/condition scope dropped",
                "uncertainty": "uncertainty collapsed",
                "contradiction": "contradiction flattened",
                "revision": "revision lost",
                "answerability": "answerability wrong",
                "fidelity_partial": "answer only partially faithful"}

N = lambda x: "--" if x is None else ("%.1f" % (100 * x))
NP = lambda x: "--" if x is None else ("%.1f\\%%" % (100 * x))
CI = lambda c: "" if c.get("ci_lo") is None else (" {\\scriptsize[%.0f, %.0f]}" %
                                                 (100 * c["ci_lo"], 100 * c["ci_hi"]))


def cellstr(c, ci=True):
    if not c or c.get("mean") is None:
        return "--"
    s = "%.1f" % (100 * c["mean"])
    if ci and c.get("ci_lo") is not None:
        s += CI(c)
    return s


# Tables that appear in the 9-page main text; everything else lands in the appendix,
# where a table must set beside the text that explains it rather than drift to the top
# of a later page. appendix.tex additionally puts a \\FloatBarrier at each \\section.
MAIN_TEXT_TABLES = {"capability_table", "coverage_note", "ladder_results", "robustness_table"}


def w(name, text):
    if name not in MAIN_TEXT_TABLES:
        text = text.replace("\\begin{table}[t]", "\\begin{table}[!ht]")
        text = text.replace("\\begin{table}[h]", "\\begin{table}[!ht]")
        text = text.replace("\\begin{table*}[t]", "\\begin{table*}[!ht]")
    open(os.path.join(TAB, name + ".tex"), "w", encoding="utf-8").write(text)


nums = {}


def num(k, v):
    nums[k] = v


# ---------------------------------------------------------------- basics
cov = rep["coverage"]
judged_main = sum(v["judged"] for k, v in cov["main_cells"].items())
num("numItems", build["selected_items"])
num("numPoolItems", build["usable_after_filter"])
num("numArcs", build["arcs_covered"])
num("numModels", len(cov["models"]))
num("numResponses", cov["judged_total"])
num("numTransferItems", build.get("transfer_items", 24))
num("numTranscriptChars", "{:,}".format(build["transcript_chars_median"]))
num("numSessMin", build["transcript_sessions_min"])
num("numSessMax", build["transcript_sessions_max"])
num("numBoot", 2000)
num("numControlItems", build.get("judge_control_items", 40))
num("judgeModel", "Nemotron-3-Super-120B")

# ---------------------------------------------------------------- capability table
CAPROWS = [
    ("Long-term dialogue, episodic and agent memory "
     "\\citep{wu2025longmemeval,maharana2024locomo,he2026memoryarena,hu2026memoryagentbench,shu2026remem}",
     ["\\cmark", "\\xmark", "\\xmark", "\\xmark", "\\pmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("Long-context QA \\citep{bai2024longbench,hsieh2024ruler,liu2024lostinthemiddle}",
     ["\\pmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark", "\\pmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("RAG / citation \\citep{lewis2020rag,gao2023alce,katsis2025mtrag}",
     ["\\xmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark", "\\pmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("Claim verification \\citep{wadden2020scifact,thorne2018fever}",
     ["\\xmark", "\\cmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark", "\\pmark", "\\xmark", "\\xmark"]),
    ("Evidence inference \\citep{lehman2019evidence,deyoung2020evidence}",
     ["\\xmark", "\\cmark", "\\xmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("Multi-document synthesis \\citep{lu2020multixscience,jain2020scirex}",
     ["\\xmark", "\\pmark", "\\pmark", "\\xmark", "\\xmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("Selective / calibrated QA \\citep{rajpurkar2018squad2,kamath2020selectiveqa,guo2017calibration}",
     ["\\xmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark", "\\cmark", "\\xmark", "\\xmark"]),
    ("Time-sensitive / fresh QA \\citep{chen2021dataset,kasai2023realtimeqa,vu2024freshllms}",
     ["\\pmark", "\\xmark", "\\xmark", "\\xmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("Scientific-agent benchmarks \\citep{zhao2026papermind,varvarigos2026litbench,moussa2025scholareval}",
     ["\\pmark", "\\cmark", "\\pmark", "\\pmark", "\\pmark", "\\cmark", "\\xmark", "\\xmark", "\\xmark"]),
    ("\\textbf{\\scimem{} (this paper)}",
     ["\\cmark", "\\cmark", "\\cmark", "\\cmark", "\\cmark", "\\cmark", "\\cmark", "\\cmark", "\\cmark"]),
]
cap = ["\\begin{table}[t]",
       "\\caption{Component coverage of adjacent benchmark families. \\cmark~scored directly, "
       "\\pmark~partially or incidentally, \\xmark~not scored. The last two columns are the ones "
       "the position turns on: whether the components are scored \\emph{jointly} within one "
       "evolving state, and whether failures are localised to retrieval, memory update, or "
       "reasoning/provenance.}",
       "\\label{tab:capabilities}", "\\centering", "\\scriptsize",
       "\\setlength{\\tabcolsep}{3.2pt}",
       "\\begin{tabular}{p{0.315\\textwidth}ccccccccc}", "\\toprule",
       "\\textbf{Benchmark family} & \\rotatebox{90}{Multi-session} & \\rotatebox{90}{Provenance} & "
       "\\rotatebox{90}{Contradiction} & \\rotatebox{90}{Method/cond.\\ scope} & "
       "\\rotatebox{90}{Revision} & \\rotatebox{90}{Synthesis} & \\rotatebox{90}{Uncertainty} & "
       "\\rotatebox{90}{\\textbf{Joint state}} & \\rotatebox{90}{\\textbf{Failure loc.}} \\\\",
       "\\midrule"]
for name, marks in CAPROWS:
    cap.append(name + " & " + " & ".join(marks) + " \\\\")
cap += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("capability_table", "\n".join(cap))

# ---------------------------------------------------------------- ladder definition table
lad = ["\\begin{table}[t]",
       "\\caption{The diagnostic conditions. D1--D4 and D6 form a nested chain in which each step "
       "removes one failure source; D5 supplies the information state \\emph{instead of} the "
       "evidence text and is therefore a branch, not a rung.}",
       "\\label{tab:ladder}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
       "\\begin{tabularx}{\\textwidth}{p{0.165\\textwidth}YY}", "\\toprule",
       "\\textbf{Condition} & \\textbf{What is supplied} & \\textbf{What the comparison isolates} \\\\",
       "\\midrule",
       "D1 closed book & Question only. & Parametric recall: how much of the state is guessable "
       "without the thread. \\\\",
       "D2 retrieval-restricted & Top-$k$ sessions from the stored session memory, returned by a "
       "deterministic retriever. & D2 vs.\\ D3: retrieval failure. \\\\",
       "D3 full history & The complete interleaved multi-session transcript. & D3 vs.\\ D4: "
       "selection failure --- the evidence was present but had to be found. \\\\",
       "D4 gold source & Gold source identifiers and gold evidence text. & D4 vs.\\ D6: "
       "memory-update failure --- the system has the evidence but must build $\\E_t$. \\\\",
       "D6 gold evidence & The gold evidence \\emph{and} the information-state record. & Residual "
       "failure here is reasoning/provenance, or verbalisation. \\\\",
       "\\midrule",
       "D5 gold memory state \\emph{(branch)} & The information-state record only: status, "
       "answerability, provenance, scope, revision trace; no source text. & D4 vs.\\ D5: state "
       "usability --- is a correct state, without its evidence, enough? \\\\",
       "\\bottomrule", "\\end{tabularx}", "\\end{table}"]
w("ladder_table", "\n".join(lad))

# ---------------------------------------------------------------- coverage note
cells = cov["main_cells"]
per_cell = sorted(v["judged"] for v in cells.values())
note = ("\\noindent\\textbf{Coverage.} Every cell below reports its own $n$ and a 95\\%% item-level "
        "bootstrap interval. The main grid is %d systems $\\times$ 6 rungs $\\times$ %d items; "
        "%s graded responses enter the analysis in total across the main grid, the format "
        "ablation, the cross-user probe, and the transfer pilot, and per-item scores for all of "
        "them are released. Structured-output parse success was %s across responses that "
        "requested a JSON state.\\medskip" %
        (len(cov["models"]), build["selected_items"], "{:,}".format(cov["judged_total"]),
         NP(cov["parse_rate_structured"])))
w("coverage_note", note)

# ---------------------------------------------------------------- gap table
g = rep["compositional_gap"]
rows = []
for c in LADDER:
    d = g["by_condition"].get(c, {})
    reasons = d.get("reasons", {})
    top = sorted(reasons.items(), key=lambda kv: -kv[1])[:3]
    topstr = ", ".join("%s (%d)" % (REASON_LABEL.get(k, k), v) for k, v in top) if top else "--"
    rows.append("%s & %d & %d & %s & %s \\\\" %
                (LONG[c], d.get("n_component_pass", 0), d.get("n_joint_fail", 0),
                 NP(d.get("rate")), topstr))
ov = g["overall"]
gl = rep.get("compositional_gap_lenient", {}).get("overall", {})
rows.append("\\midrule\\textbf{All rungs} & \\textbf{%d} & \\textbf{%d} & \\textbf{%s} & \\\\" %
            (ov["n_component_pass"], ov["n_joint_fail"], NP(ov["rate"])))
gap = ["\\begin{table}[t]",
       "\\caption{The compositional gap (conservative reading). Rows count only responses that "
       "\\emph{pass} all three component-style checks --- gold sources retrieved, nothing "
       "unsupported asserted, and the answer graded fully correct --- so that a failure can only "
       "come from a dimension the component checks do not score. The last column names those "
       "dimensions.}",
       "\\label{tab:gap}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
       "\\begin{tabularx}{\\textwidth}{p{0.20\\textwidth}rrrY}", "\\toprule",
       "\\textbf{Rung} & \\textbf{Pass all} & \\textbf{Fail} & \\textbf{Gap} & "
       "\\textbf{Dominant causes} \\\\", "\\textbf{} & \\textbf{components} & $\\Phi$ & & \\\\",
       "\\midrule"] + rows + ["\\bottomrule", "\\end{tabularx}", "\\end{table}"]
w("gap_table", "\n".join(gap))
num("numGapOverallPct", "%.0f" % (100 * ov["rate"]) if ov["rate"] is not None else "--")
num("numGapLenientPct", "%.0f" % (100 * gl["rate"]) if gl.get("rate") is not None else "--")

allreasons = collections.Counter()
for c in LADDER:
    for k, v in g["by_condition"].get(c, {}).get("reasons", {}).items():
        allreasons[k] += v
top2 = [REASON_LABEL.get(k, k) for k, _ in allreasons.most_common(2)]
d4 = g["by_condition"].get("gold_source", {})
d6 = g["by_condition"].get("gold_evidence", {})
num("numGapSentence",
    "Table~\\ref{tab:gap} answers H1 directly. Counting only responses the judge graded as "
    "\\emph{fully} correct --- so that nothing here follows from a stricter bar on the answer "
    "itself --- %s of %s responses that also retrieve the gold sources and assert nothing "
    "unsupported still fail joint information-state fidelity, a rate of %s (95\\%% CI %s). The "
    "rate is %s at D4, where the gold sources are handed to the system, and %s at D6, where the "
    "state and the evidence spans are both supplied. The dominant causes are %s. Under the more "
    "permissive reading a question-answering benchmark would actually apply --- crediting "
    "partially correct answers --- the gap rises to %s." %
    ("{:,}".format(ov["n_joint_fail"]), "{:,}".format(ov["n_component_pass"]), NP(ov["rate"]),
     ("[%.0f, %.0f]" % (100 * ov["ci_lo"], 100 * ov["ci_hi"])) if ov.get("ci_lo") is not None else "--",
     NP(d4.get("rate")), NP(d6.get("rate")), " and ".join(top2) if top2 else "mixed",
     NP(gl.get("rate"))))

# ---------------------------------------------------------------- ladder results
lj = rep["ladder_joint_fidelity"]
comp = rep["ladder_components"]
models = [m for m in lj if m != "ALL"]
models.sort(key=lambda m: -(lj[m]["gold_evidence"]["mean"] or 0))
rows = []
for m in models:
    cells_ = [cellstr(lj[m][c], ci=False) for c in LADDER]
    rows.append("%s & %s \\\\" % (MODEL_LABEL.get(m, m), " & ".join(cells_)))
allrow = "\\midrule\\textbf{All systems} & %s \\\\" % " & ".join(
    cellstr(lj["ALL"][c]) for c in LADDER)
extra = []
for key, label in [("answer_correct", "Answer fidelity (correct)"),
                   ("provenance_ok", "Provenance correct"),
                   ("answerability_correct", "Answerability correct"),
                   ("status_correct", "Status correct"),
                   ("preservation_ok", "All preservation components"),
                   ("all_components_ok", "All component checks")]:
    extra.append("%s & %s \\\\" % (label, " & ".join(
        cellstr(comp[c][key], ci=False) for c in LADDER)))
extra.append("Source-id F1 & %s \\\\" % " & ".join(N(comp[c]["src_f1"]["mean"]) for c in LADDER))
extra.append("Scope coverage & %s \\\\" % " & ".join(N(comp[c]["scope_cov"]["mean"]) for c in LADDER))

lr = ["\\begin{table}[t]",
      "\\caption{Joint information-state fidelity $\\Phi$ (\\%) by system and condition; the "
      "aggregate row carries 95\\% item-level bootstrap intervals. D5 supplies the state instead "
      "of the evidence and is not a rung of the chain (\\S\\ref{sec:ladder}). The same cells "
      "broken out by component are in Table~\\ref{tab:app-ladder}.}",
      "\\label{tab:ladder-results}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
      "\\begin{tabular}{lcccccc}", "\\toprule",
      "\\textbf{System} & " + " & ".join(SHORT[c] for c in LADDER) + " \\\\", "\\midrule"]
lr += rows + [allrow]
lr += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("ladder_results", "\n".join(lr))

w("app_ladder_components", "\n".join(
    ["\\begin{table}[h]",
     "\\caption{Component metrics by condition, all systems pooled, structured format (\\%).}",
     "\\label{tab:app-components}", "\\centering", "\\small",
     "\\setlength{\\tabcolsep}{4pt}", "\\begin{tabular}{lcccccc}", "\\toprule",
     "\\textbf{Measure} & " + " & ".join(SHORT[c] for c in LADDER) + " \\\\", "\\midrule"]
    + extra + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

means = [lj["ALL"][c]["mean"] for c in CHAIN]
num("numLadderTrend",
    "rises along the chain, from %s\\%% at D1 to %s\\%% at D2, %s\\%% at D3, %s\\%% at D4 "
    "and %s\\%% at D6" % tuple(N(m) for m in means))

mono = rep["monotonicity"]
viol = mono["violating"]
tot = mono["trajectories"]
num("numMonoViolPct", "%.0f" % (100 * viol / tot) if tot else "--")
drops = []
for a, b in zip(CHAIN, CHAIN[1:]):
    k = "%s->%s" % (a, b)
    d = mono["per_step"][k]
    drops.append((k, d["down"], d["up"], d["same"]))
worst = max(drops, key=lambda x: x[1])
nonmono_models = [MODEL_LABEL.get(m, m) for m, d in mono["per_model"].items() if not d["monotone"]]
num("numMonoSentence",
    "The aggregate curve is %s. Counted naively, %d of %d complete item-by-system trajectories "
    "(%s\\%%) contain at least one step at which removing work \\emph{cost} the system a "
    "previously correct state, the worst being %s$\\rightarrow$%s (%d downward against %d upward "
    "moves), and %s of %d systems have a non-monotone mean curve%s --- but that count is an upper "
    "bound that includes resampling noise." %
    ("monotone" if mono.get("aggregate_monotone") else "not monotone",
     viol, tot, "%.0f" % (100 * viol / tot) if tot else "--",
     SHORT[worst[0].split("->")[0]], SHORT[worst[0].split("->")[1]], worst[1], worst[2],
     len(nonmono_models), len(mono["per_model"]),
     (" (" + ", ".join(nonmono_models) + ")") if nonmono_models else ""))

sb = mono.get("state_branch", {})
d45 = mono.get("d4_vs_d5_items", {})
num("numStateBranchSentence",
    "Joint fidelity at D5, where the information-state record is supplied without the evidence "
    "text, is %s\\%% against %s\\%% at D4 and %s\\%% at D6 --- a drop of %s points relative "
    "to gold evidence alone; item by item, %d item-system pairs pass at D4 and fail at D5 while "
    "only %d do the reverse." %
    (N(sb.get("d5_gold_memory_state")), N(sb.get("d4_gold_source")), N(sb.get("d6_gold_evidence")),
     ("%.1f" % (-100 * sb["d5_minus_d4"])) if sb.get("d5_minus_d4") is not None else "--",
     d45.get("d4_pass_d5_fail", 0), d45.get("d4_fail_d5_pass", 0)))

# ---------------------------------------------------------------- per-model table
bm = rep["by_model"]
order = sorted(bm, key=lambda m: -(bm[m]["joint_fidelity"]["mean"] or 0))
cols = [("joint_fidelity", "$\\Phi$"), ("answer_correct", "Answer"),
        ("provenance_ok", "Prov."), ("contradiction_preserved", "Contr."),
        ("revision_preserved", "Revis."), ("scope_preserved", "Scope"),
        ("uncertainty_preserved", "Uncert."), ("answerability_correct", "Answ.ability"),
        ("status_correct", "Status"), ("uncertainty_collapse", "U-collapse$\\downarrow$")]
rows = []
for m in order:
    vals = []
    for k, _ in cols:
        vals.append(cellstr(bm[m].get(k, {}), ci=False))
    _n = (bm[m].get("joint_fidelity") or {}).get("n") or 0
    rows.append("%s & %d & %s \\\\" % (MODEL_LABEL.get(m, m), _n, " & ".join(vals)))
mt = ["\\begin{table}[t]",
      "\\caption{Capability-wise metrics by system (\\%), pooled over rungs. Preservation columns "
      "are computed only on the items that exercise the component. Rankings differ across columns: "
      "if these metrics measured one underlying ability the orderings would coincide.}",
      "\\label{tab:models}", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3.5pt}",
      "\\begin{tabular}{lr" + "c" * len(cols) + "}", "\\toprule",
      "\\textbf{System} & $n$ & " + " & ".join(c[1] for c in cols) + " \\\\",
      "\\midrule"] + rows + \
     ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("model_table", "\n".join(mt))

inv = rep["rank_inversions"]["vs_joint"]
tot_pairs = max((v["pairs"] for v in inv.values()), default=0)
worst_metric = max(inv.items(), key=lambda kv: kv[1]["inversions_vs_joint"]) if inv else None
any_inv = sum(v["inversions_vs_joint"] for v in inv.values())
num("numInversionSentence",
    "across %d capability metrics the system ordering disagrees with the joint-fidelity ordering in "
    "%d of %d pairwise comparisons, and the metric that reorders systems most is %s "
    "(%d of %d pairs inverted)." %
    (len(inv), any_inv, tot_pairs * len(inv) if tot_pairs else 0,
     worst_metric[0].replace("_", " ") if worst_metric else "--",
     worst_metric[1]["inversions_vs_joint"] if worst_metric else 0,
     worst_metric[1]["pairs"] if worst_metric else 0))

# ---------------------------------------------------------------- format ablation
fa = rep["format_ablation"]
rows = []
for c in ["online_history", "gold_source", "gold_memory_state"]:
    for f, flabel in [("structured", "structured state"), ("plain", "prose only")]:
        d = fa[c][f]
        rows.append("%s & %s & %s & %s & %s & %s & %s & %s \\\\" %
                    (LONG[c] if f == "structured" else "", flabel,
                     ("%.0f" % fa[c]["answer_words"][f]["median"])
                     if fa[c].get("answer_words", {}).get(f, {}).get("median") is not None else "--",
                     cellstr(d["joint_fidelity"], ci=False),
                     cellstr(d["answer_correct"], ci=False),
                     cellstr(d["grounding_ok"], ci=False),
                     cellstr(d["provenance_ok"], ci=False),
                     cellstr(d["failure_localizable"], ci=False)))
ft = ["\\begin{table}[t]",
      "\\caption{Output-format ablation (\\%), paired by item, model and condition. \\emph{Words} is "
      "the median length of the answer prose under a 120-word ceiling shared by both formats. "
      "\\emph{Localisable} is the fraction of responses on which at least one preservation "
      "component could be graded at all.}",
      "\\label{tab:format}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
      "\\begin{tabular}{llcccccc}", "\\toprule",
      "\\textbf{Condition} & \\textbf{Format} & \\textbf{Words} & $\\Phi$ & \\textbf{Answer} & "
      "\\textbf{Grounded} & \\textbf{Prov.} & \\textbf{Localisable} \\\\", "\\midrule"] + rows + \
     ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("format_table", "\n".join(ft))

ds = fa["gold_source"]
delta = None
if (ds["structured"]["joint_fidelity"]["mean"] is not None
        and ds["plain"]["joint_fidelity"]["mean"] is not None):
    delta = ds["structured"]["joint_fidelity"]["mean"] - ds["plain"]["joint_fidelity"]["mean"]
loc = ds.get("paired_localisability", {})
aw = ds.get("answer_words", {})
num("numFormatSentence",
    "The structured format is worse for the system and barely better for the measurement. At D4, "
    "requiring a JSON state costs %s points of joint fidelity relative to prose (%s versus %s) and "
    "%s points of answer fidelity, and the reason is visible in the text: the prose inside the "
    "JSON field is half as long (median %s words against %s), although both prompts set the same "
    "120-word ceiling, and the half that disappears is where qualifications live. What it buys is "
    "small: of the %d preservation components the judge could grade on a structured response, %s "
    "became ungradable when the same system answered the same item in prose, while %d components "
    "were gradable only in the prose condition." %
    (("%+.1f" % (100 * delta)) if delta is not None else "--",
     NP(ds["structured"]["joint_fidelity"]["mean"]), NP(ds["plain"]["joint_fidelity"]["mean"]),
     ("%+.1f" % (100 * (ds["structured"]["answer_correct"]["mean"]
                        - ds["plain"]["answer_correct"]["mean"])))
     if (ds["structured"]["answer_correct"]["mean"] is not None
         and ds["plain"]["answer_correct"]["mean"] is not None) else "--",
     ("%.0f" % aw.get("structured", {}).get("median", 0)) if aw.get("structured") else "--",
     ("%.0f" % aw.get("plain", {}).get("median", 0)) if aw.get("plain") else "--",
     loc.get("components_graded_in_structured", 0),
     NP(loc.get("rate_lost")), loc.get("gradable_only_in_prose", 0)))

# ---------------------------------------------------------------- pushback
pb = rep["pushback"]
pd = pb.get("paired_difference", {})
rows = []
for arm, label in [("pushback_control", "neutral restatement"),
                   ("pushback_pushback", "evidence-free pushback")]:
    d = pb[arm]
    rows.append("%s & %d & %s & %s & %s & %s \\\\" %
                (label, d["n"], cellstr(d["joint_fidelity"], ci=False),
                 cellstr(d["lost_fidelity"], ci=False),
                 cellstr(d["became_unsupported"], ci=False),
                 cellstr(d["answerability_flip"], ci=False)))
DIFF_ROWS = [("joint_fidelity", "joint fidelity $\\Phi$"),
             ("answer_correct", "answer fully correct"),
             ("unsupported", "asserts something unsupported"),
             ("preservation_failed", "a preservation component fails"),
             ("lost_fidelity", "loses a previously correct answer")]
drows = []
for k, label in DIFF_ROWS:
    d = pd.get(k) or {}
    if not d.get("n"):
        continue
    sig = "\\textbf{" if (d.get("ci_lo") is not None and
                          (d["ci_lo"] > 0 or d["ci_hi"] < 0)) else "{"
    drows.append("%s & %d & %s%+.1f} & [%+.1f, %+.1f] \\\\" %
                 (label, d["n_items"], sig, 100 * d["mean_diff"],
                  100 * d["ci_lo"], 100 * d["ci_hi"]))
pt = ["\\begin{table}[t]",
      "\\caption{Cross-user stability. Turn~1 is the D4 prompt; turn~2 is either a neutral "
      "restatement request or a colleague asserting the thread's superseded claim with no new "
      "evidence. Upper block: outcome rates per arm (\\%). Lower block: the paired "
      "pushback-minus-control difference in percentage points with a 95\\% item-level bootstrap "
      "interval; bold marks intervals that exclude zero.}",
      "\\label{tab:pushback}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
      "\\begin{tabular}{lrcccc}", "\\toprule",
      "\\textbf{Turn-2 message} & $n$ & $\\Phi$ & \\textbf{Lost answer} & "
      "\\textbf{Unsupported} & \\textbf{Answ.\\ flip} \\\\", "\\midrule"] + rows + \
     ["\\midrule",
      "\\textbf{Paired difference} & \\textbf{items} & \\textbf{pp} & \\textbf{95\\% CI} & & \\\\",
      "\\midrule"] + [r.replace(" \\\\", " & & \\\\") for r in drows] + \
     ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("pushback_table", "\n".join(pt))

uns = pd.get("unsupported", {})
jf = pd.get("joint_fidelity", {})
lf = pd.get("lost_fidelity", {})
ac = pd.get("answer_correct", {})


def pp(d):
    if not d or d.get("mean_diff") is None:
        return "--"
    return "%+.1f points [%+.1f, %+.1f]" % (100 * d["mean_diff"], 100 * d["ci_lo"],
                                            100 * d["ci_hi"])


_ab = pb.get("arm_balance", {})
num("numArmBalanceSentence", _ab.get("sentence", ""))
num("numPushLossPct",
    ("%.0f" % (-100 * jf["mean_diff"])) if jf.get("mean_diff") is not None else "--")
num("numPushSentence",
    "It moves, but not where one would expect. The verdict mostly holds: relative to the neutral "
    "control, pushback changes the rate of losing a previously correct answer by %s and the rate "
    "of answering correctly by %s, neither distinguishable from zero. What degrades is the "
    "justification. The rate at which a response asserts something the evidence does not support "
    "rises by %s, comfortably clear of zero (sign test $p=%s$). Joint state fidelity falls by "
    "%s, but that interval sits on the zero boundary and its upper bound is not stable across "
    "resamples (sign test $p=%s$), so we report the fidelity drop as suggestive only and rest "
    "the finding on the unsupported-assertion rise. Systems under evidentially empty pressure "
    "do not capitulate on the answer; they defend it with material they do not have." %
    (pp(lf), pp(ac), pp(uns), ("%.3f" % uns.get("p_two_sided_sign", float("nan"))),
     pp(jf), ("%.3f" % jf.get("p_two_sided_sign", float("nan")))))

# ---------------------------------------------------------------- transfer
tr = rep["transfer"]
rows = []
for c in ["online_history", "gold_source", "gold_memory_state"]:
    r = ["%s" % LONG[c]]
    for k in ["machine_learning", "theoretical_cs", "TRANSFER_ALL", "ORIGINAL_ALL"]:
        r.append(cellstr(tr.get("%s|%s" % (k, c), {}), ci=False))
    rows.append(" & ".join(r) + " \\\\")
tt = ["\\begin{table}[t]",
      "\\caption{Transfer pilot: joint fidelity $\\Phi$ (\\%) on author-constructed items in "
      "machine learning and theoretical computer science, against the expert-validated "
      "natural-science items at the same rungs. Transfer items are \\emph{not} expert-validated.}",
      "\\label{tab:transfer}", "\\centering", "\\small",
      "\\begin{tabular}{lcccc}", "\\toprule",
      "\\textbf{Rung} & \\textbf{ML} & \\textbf{Theory/TCS} & \\textbf{Transfer (all)} & "
      "\\textbf{Natural sciences} \\\\", "\\midrule"] + rows + \
     ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("transfer_table", "\n".join(tt))

app = tr.get("capability_applicability", {})
num("numTransferSentence",
    "Joint fidelity on the transfer items is %s at D4 against %s on the natural-science items over "
    "the same four systems, and "
    "the preservation components remain applicable at comparable rates (contradiction %s, revision "
    "%s, scope %s, uncertainty %s of transfer responses)." %
    (cellstr(tr.get("TRANSFER_ALL|gold_source", {}), ci=False) + "\\%",
     cellstr(tr.get("ORIGINAL_ALL|gold_source", {}), ci=False) + "\\%",
     NP(app.get("contradiction")), NP(app.get("revision")),
     NP(app.get("scope")), NP(app.get("uncertainty"))))

# ---------------------------------------------------------------- triage
tri = rep["triage"]
tri = {k: v for k, v in tri.items() if (v.get("parse_rate") or 0) > 0.5}
TRIAGE_LABEL = {"super120b": "Nemotron-3-Super-120B", "laguna": "Laguna-XS-2.1"}
rows = []
for m in sorted(tri):
    d = tri[m]
    rows.append("%s & %d & %s & %s & %s & %s & %s \\\\" %
                (TRIAGE_LABEL.get(m, m), d["item_decision"]["n"],
                 N(d["item_decision"]["agreement"]), "%.2f" % (d["item_decision"]["kappa"] or 0),
                 N(d["evidence_support"]["agreement"]),
                 "%.2f" % (d["evidence_support"]["kappa"] or 0),
                 N(d["answerability"]["agreement"])))
curve = rep.get("triage_curve", {})
crows = []
base = curve.get("base_rate")
for c in curve.get("curve", []):
    if c["n_forwarded"] == 0:
        continue
    lift = (c["recall"] / c["budget"]) if (c["recall"] and c["budget"]) else None
    crows.append("$\\geq %d$ flags & %d & %s & %s & %s & %s & \\\\" %
                 (c["threshold"], c["n_forwarded"], NP(c["budget"]), NP(c["recall"]),
                  NP(c["precision"]), ("%.2f$\\times$" % lift) if lift else "--"))
trt = ["\\begin{table}[t]",
       "\\caption{Model-assisted annotation triage against expert decisions on the full usable "
       "pool ($n=%d$; %s of items were not accepted as-is by an expert). Upper block: how well a "
       "screening model reproduces expert labels. Lower block: the screen itself --- forward an "
       "item to an expert when at least $k$ of the four model flags fire. \\emph{Lift} is recall "
       "divided by budget, where 1.00 is what random routing achieves.}" %
       (curve.get("n_items", 0), NP(base)),
       "\\label{tab:triage}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
       "\\begin{tabular}{lrccccc}", "\\toprule",
       "\\textbf{Screening model} & $n$ & \\textbf{Decision} & $\\kappa$ & "
       "\\textbf{Ev.\\ support} & $\\kappa$ & \\textbf{Answerability} \\\\", "\\midrule"] + rows + \
      ["\\midrule",
       "\\textbf{Screen} & \\textbf{fwd} & \\textbf{Budget} & \\textbf{Recall} & "
       "\\textbf{Precision} & \\textbf{Lift} & \\\\", "\\midrule"] + \
      [r.replace(" \\\\", " \\\\") for r in crows] + \
      ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("triage_table", "\n".join(trt))

best = None
for c in curve.get("curve", []):
    if c["n_forwarded"] and c["threshold"] >= 1:
        best = c
        break
if best and tri:
    anymodel = max(tri, key=lambda m: tri[m]["item_decision"]["kappa"] or 0)
    lift = best["recall"] / best["budget"] if best["budget"] else None
    num("numTriageSentence",
        "A screen built from model pre-annotations forwards %s of the pool to an expert and "
        "recovers %s of the items an expert would not have accepted as-is --- a lift of %s over "
        "random routing at the same budget. The models' own labels are much weaker than that: "
        "agreement with expert item decisions is %s ($\\kappa=%.2f$) and with expert "
        "evidence-support labels %s ($\\kappa=%.2f$), which is exactly why they belong in the "
        "routing step and not in the label (the stronger of the two screening models is quoted; "
        "both appear in Table~\\ref{tab:triage})." %
        (NP(best["budget"]), NP(best["recall"]),
         ("%.2f$\\times$" % lift) if lift else "--",
         NP(tri[anymodel]["item_decision"]["agreement"]),
         tri[anymodel]["item_decision"]["kappa"] or 0,
         NP(tri[anymodel]["evidence_support"]["agreement"]),
         tri[anymodel]["evidence_support"]["kappa"] or 0))
else:
    num("numTriageSentence", "Triage results are reported in Appendix~\\ref{app:triage}.")

# ---------------------------------------------------------------- judge controls
jc = rep["judge_controls"]
prim = None
for k in jc:
    if "nemotron" in k:
        prim = k
VARIANTS = ["gold_verbatim", "scope_stripped", "uncertainty_collapsed", "provenance_swapped",
            "unsupported_addition", "contradiction_flattened"]
VLAB = {"gold_verbatim": "gold answer verbatim", "scope_stripped": "scope stripped",
        "uncertainty_collapsed": "uncertainty collapsed", "provenance_swapped": "provenance swapped",
        "unsupported_addition": "unsupported addition",
        "contradiction_flattened": "contradiction flattened"}


def pct_of(d, key, want):
    tot_ = sum(d.get(key, {}).values())
    if not tot_:
        return None
    return d[key].get(want, 0) / tot_


rows = []
if prim:
    d = jc[prim]
    for v in VARIANTS:
        rows.append("%s & %s & %s & %s & %s & %s \\\\" % (
            VLAB[v],
            NP(pct_of(d, v + "|answer_fidelity", "correct")),
            NP(pct_of(d, v + "|scope_preserved", "no")),
            NP(pct_of(d, v + "|uncertainty_preserved", "no")),
            NP(pct_of(d, v + "|provenance_correct", "no")),
            NP(pct_of(d, v + "|unsupported_claim", "true"))))
jt = ["\\begin{table}[t]",
      "\\caption{Judge validation. Each row is a synthetic response built from the gold answer by "
      "destroying exactly one component; columns report how often the judge fires on each "
      "component. A valid instrument accepts row~1 and fires on the diagonal.}",
      "\\label{tab:judge}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
      "\\begin{tabular}{lccccc}", "\\toprule",
      "\\textbf{Synthetic response} & \\textbf{Fidelity=correct} & \\textbf{Scope=no} & "
      "\\textbf{Uncert.=no} & \\textbf{Prov.=no} & \\textbf{Unsupported} \\\\", "\\midrule"] + \
     rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("judge_table", "\n".join(jt))

if prim:
    d = jc[prim]
    num("numJudgeSentence",
        "The judge accepts the verbatim gold answer as faithful %s of the time, and fires on the "
        "matching component for each targeted corruption: scope stripping raises a scope failure "
        "on %s of items, uncertainty collapse raises an uncertainty failure on %s, provenance "
        "swapping raises a provenance failure on %s, and an appended unsupported sentence is "
        "flagged as unsupported on %s." %
        (NP(pct_of(d, "gold_verbatim|answer_fidelity", "correct")),
         NP(pct_of(d, "scope_stripped|scope_preserved", "no")),
         NP(pct_of(d, "uncertainty_collapsed|uncertainty_preserved", "no")),
         NP(pct_of(d, "provenance_swapped|provenance_correct", "no")),
         NP(pct_of(d, "unsupported_addition|unsupported_claim", "true"))))
else:
    num("numJudgeSentence", "Judge-validation controls are reported in Appendix~\\ref{app:tables}.")

sc = rep.get("judge_self_consistency", {})
scf = sc.get("fields", {})
ja = rep["judge_agreement"]
fid = ja.get("answer_fidelity", {})
unc = ja.get("uncertainty_preserved", {})
num("numJudgeAgreementSentence",
    "a second judge on $n=%d$ responses agrees on answer fidelity only %s of the time "
    "($\\kappa=%.2f$, uncertainty %s, $\\kappa=%.2f$), while the primary judge regrading "
    "$n=%d$ responses agrees with itself %s on fidelity ($\\kappa=%.2f$), %s on unsupported-claim "
    "($\\kappa=%.2f$) and %s on provenance ($\\kappa=%.2f$) --- self-consistent, not "
    "interchangeable" %
    (fid.get("n", 0), NP(fid.get("agreement")), fid.get("kappa") or 0,
     NP(unc.get("agreement")), unc.get("kappa") or 0,
     sc.get("n_repeat_graded", 0),
     NP(scf.get("answer_fidelity", {}).get("agreement")),
     scf.get("answer_fidelity", {}).get("kappa") or 0,
     NP(scf.get("unsupported_claim", {}).get("agreement")),
     scf.get("unsupported_claim", {}).get("kappa") or 0,
     NP(scf.get("provenance_correct", {}).get("agreement")),
     scf.get("provenance_correct", {}).get("kappa") or 0))

# ---------------------------------------------------------------- appendix tables
# full ladder with CIs and n
rows = []
for c in LADDER:
    d = comp[c]
    rows.append("%s & %d & %s & %s & %s & %s & %s & %s \\\\" %
                (LONG[c], d["joint_fidelity"]["n"], cellstr(d["joint_fidelity"]),
                 cellstr(d["answer_correct"], ci=False), cellstr(d["grounding_ok"], ci=False),
                 cellstr(d["provenance_ok"], ci=False), cellstr(d["preservation_ok"], ci=False),
                 N(d["src_f1"]["mean"])))
w("app_ladder_full", "\n".join(
    ["\\begin{table}[h]", "\\caption{Ladder results with per-cell $n$ and 95\\% intervals "
     "(all systems pooled, structured format).}", "\\label{tab:app-ladder}", "\\centering",
     "\\small", "\\begin{tabular}{lrcccccc}", "\\toprule",
     "\\textbf{Rung} & $n$ & $\\Phi$ & \\textbf{Answer} & \\textbf{Grounded} & \\textbf{Prov.} & "
     "\\textbf{Preserv.} & \\textbf{Src F1} \\\\", "\\midrule"] + rows +
    ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

cb = rep["capability_by_condition"]
rows = []
_thin = []
for cat in sorted(cb, key=lambda k: CAP_LABEL.get(k, k)):
    cells = [cb[cat][c] for c in LADDER]
    nit = max((d.get("n_items") or 0) for d in cells) if cells else 0
    nres = sum((d.get("n") or 0) for d in cells)
    thin = bool(nit and nit < 20)
    if thin:
        _thin.append("%s (%d)" % (CAP_LABEL.get(cat, cat).lower(), nit))
    _cells = " & ".join(cellstr(d, ci=False) for d in cells)
    if thin:
        rows.append("\\textcolor{gray}{%s$^\\dagger$} & \\textcolor{gray}{%d} & \\textcolor{gray}{%d} & %s \\\\" % (
            CAP_LABEL.get(cat, cat), nit, nres,
            " & ".join("\\textcolor{gray}{%s}" % cellstr(d, ci=False) for d in cells)))
    else:
        rows.append("%s & %d & %d & %s \\\\" % (CAP_LABEL.get(cat, cat), nit, nres, _cells))
_warn = ("" if not _thin else
         " Rows set in grey with a dagger have fewer than 20 items (%s) and are reported "
         "for completeness only; at that size a one-item change moves the cell by several "
         "points, so they should not be read as system-level differences." % ", ".join(_thin))
w("app_capability", "\n".join(
    ["\\begin{table}[h]",
     "\\caption{Joint fidelity $\\Phi$ (\\%%) by capability and rung, with the number of "
     "distinct items in each capability and the total graded responses behind the row.%s}" % _warn,
     "\\label{tab:app-capability}", "\\centering", "\\small",
     "\\begin{tabular}{lrrcccccc}",
     "\\toprule", "\\textbf{Capability} & \\textbf{items} & $n$ & "
     + " & ".join(SHORT[c] for c in LADDER) + " \\\\",
     "\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

fm = rep["failure_modes"]
modes = sorted({k for c in fm for k in fm[c] if k and k != "none"})
rows = []
for m in modes:
    rows.append("%s & %s \\\\" % (m.replace("_", " "),
                                  " & ".join(str(fm[c].get(m, 0)) for c in LADDER)))
rows.append("\\midrule none & %s \\\\" % " & ".join(str(fm[c].get("none", 0)) for c in LADDER))
w("app_failuremodes", "\n".join(
    ["\\begin{table}[h]", "\\caption{Judge-assigned primary failure mode by rung (counts).}",
     "\\label{tab:app-failures}", "\\centering", "\\small", "\\begin{tabular}{lcccccc}", "\\toprule",
     "\\textbf{Failure mode} & " + " & ".join(SHORT[c] for c in LADDER) + " \\\\", "\\midrule"] +
    rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

rows = []
for jm in sorted(jc):
    d = jc[jm]
    for v in VARIANTS:
        rows.append("%s & %s & %s & %s & %s & %s & %s \\\\" % (
            jm.replace("_", "\\_"), VLAB[v],
            NP(pct_of(d, v + "|answer_fidelity", "correct")),
            NP(pct_of(d, v + "|scope_preserved", "no")),
            NP(pct_of(d, v + "|uncertainty_preserved", "no")),
            NP(pct_of(d, v + "|provenance_correct", "no")),
            NP(pct_of(d, v + "|contradiction_preserved", "no"))))
w("app_judge_controls", "\n".join(
    ["\\begin{table}[h]", "\\caption{Judge-validation confusion for both judges.}",
     "\\label{tab:app-judge}", "\\centering", "\\scriptsize", "\\begin{tabular}{llccccc}",
     "\\toprule", "\\textbf{Judge} & \\textbf{Corruption} & \\textbf{Fid.=correct} & "
     "\\textbf{Scope=no} & \\textbf{Uncert.=no} & \\textbf{Prov.=no} & \\textbf{Contr.=no} \\\\",
     "\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

rows = []
for k in sorted(tr):
    if "|" in k:
        dom, cond = k.split("|", 1)
        dom_lab = {"TRANSFER_ALL": "Transfer (all)", "ORIGINAL_ALL": "Natural sciences",
                   "machine_learning": "Machine learning",
                   "theoretical_cs": "Theoretical CS"}.get(dom, dom.replace("_", " "))
        rows.append("%s & %s & %s & %s \\\\" % (dom_lab, SHORT.get(cond, cond),
                                               tr[k].get("n", 0), cellstr(tr[k])))
w("app_transfer_full", "\n".join(
    ["\\begin{table}[h]", "\\caption{Transfer pilot, full cells with $n$ and intervals.}",
     "\\label{tab:app-transfer}", "\\centering", "\\small", "\\begin{tabular}{llrc}", "\\toprule",
     "\\textbf{Item set} & \\textbf{Cond.} & $n$ & $\\Phi$ \\\\", "\\midrule"] + rows +
    ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

rows = []
for m in sorted(tri):
    d = tri[m]
    rows.append("%s & %d & %s & %s & %s & %s & %s & %s \\\\" %
                (m.replace("_", "\\_"), d["n"], NP(d["parse_rate"]),
                 N(d["item_decision"]["agreement"]), "%.2f" % (d["item_decision"]["kappa"] or 0),
                 N(d["evidence_support"]["agreement"]),
                 "%.2f" % (d["evidence_support"]["kappa"] or 0),
                 N(d["answerability"]["agreement"])))
w("app_triage", "\n".join(
    ["\\begin{table}[h]",
     "\\caption{Annotation-triage detail: how closely each screening model reproduces the expert "
     "labels it is meant to route around.}", "\\label{tab:app-triage}",
     "\\centering", "\\small", "\\begin{tabular}{lrcccccc}", "\\toprule",
     "\\textbf{Model} & $n$ & \\textbf{Parse} & \\textbf{Dec.} & $\\kappa_{\\text{dec}}$ & "
     "\\textbf{Ev.} & $\\kappa_{\\text{ev}}$ & \\textbf{Answ.} \\\\",
     "\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

pool = ["\\begin{table}[h]",
        "\\caption{Item pool composition.}", "\\label{tab:app-pool}", "\\centering", "\\small",
        "\\begin{tabular}{lr}", "\\toprule", "\\textbf{Property} & \\textbf{Count} \\\\",
        "\\midrule"]
pool.append("Expert-reviewed source items & %d \\\\" % build["reviewed_rows"])
pool.append("Usable after filtering & %d \\\\" % build["usable_after_filter"])
pool.append("Selected for evaluation & %d \\\\" % build["selected_items"])
pool.append("Evidence arcs covered & %d \\\\" % build["arcs_covered"])
pool.append("\\midrule")
for k, v in sorted(build["by_category"].items()):
    pool.append("\\quad %s & %d \\\\" % (CAP_LABEL.get(k, k), v))
pool.append("\\midrule")
for k, v in sorted(build["by_domain"].items()):
    pool.append("\\quad %s & %d \\\\" % (k.replace("_", " "), v))
pool.append("\\midrule")
for k, v in sorted(build["by_answerability"].items()):
    pool.append("\\quad expert answerability: %s & %d \\\\" % (k, v))
pool.append("\\midrule")
pool.append("Transfer items (author-constructed) & %d \\\\" % build.get("transfer_items", 0))
pool += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
w("pool_table", "\n".join(pool))


# ---------------------------------------------------------------- systems table
SYS_INFO = {
    "openai/gpt-oss-20b": ("GPT-OSS-20B", "mixture-of-experts, reasoning", "system under test"),
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning":
        ("Nemotron-3-Nano-30B-A3B", "mixture-of-experts, reasoning", "system under test"),
    "nvidia/nemotron-3.5-lightning-30b-a3b":
        ("Nemotron-3.5-Lightning-30B-A3B", "mixture-of-experts, reasoning", "system under test"),
    "mistralai/mistral-nemotron": ("Mistral-Nemotron", "dense, non-reasoning", "system under test"),
    "meta/llama-3.2-11b-vision-instruct":
        ("Llama-3.2-11B-Instruct", "dense, non-reasoning", "system under test"),
    "nvidia/nemotron-3-super-120b-a12b":
        ("Nemotron-3-Super-120B-A12B", "mixture-of-experts, reasoning",
         "primary judge; excluded as a system under test"),
    "poolside/laguna-xs-2.1":
        ("Laguna-XS-2.1", "dense, non-reasoning",
         "secondary judge and triage; excluded as a system under test"),
    "nvidia/nemotron-3-ultra-550b-a55b":
        ("Nemotron-3-Ultra-550B-A55B", "mixture-of-experts, reasoning",
         "frontier-class check (Appendix~\\ref{app:frontier}); excluded from the pool"),
}
rows = []
for m in sorted(cov["models"]):
    name, arch, role = SYS_INFO.get(m, (m, "--", "system under test"))
    rows.append("%s & \\raggedright\\ttfamily\\scriptsize %s & %s & %s \\\\" %
                (name, m.replace("_", "\\_").replace("-", "-\\-").replace("/", "/\\-"),
                 arch, role))
# Derive the non-SUT rows from the judges that actually appear in the report, so the
# roster can never disagree with the tables built from the same run.
_judges = sorted(set(rep.get("judge_controls", {}))
                 | set(rep.get("judge_controls_falsepos", {}))
                 | ({rep["frontier"]["model"]} if rep.get("frontier", {}).get("model") else set()))
for m in _judges:
    if m in cov["models"]:
        continue
    if m not in SYS_INFO:
        print("  WARNING: judge %r has no roster entry" % m)
        continue
    name, arch, role = SYS_INFO[m]
    rows.append("%s & \\raggedright\\ttfamily\\scriptsize %s & %s & %s \\\\" %
                (name, m.replace("_", "\\_").replace("-", "-\\-").replace("/", "/\\-"), arch, role))
w("systems_table", "\n".join(
    ["\\begin{table}[h]", "\\caption{Models used in the study and their role.}",
     "\\label{tab:app-systems}", "\\centering", "\\scriptsize",
     "\\setlength{\\tabcolsep}{4pt}",
     "\\begin{tabular}{p{0.155\\textwidth}p{0.255\\textwidth}p{0.20\\textwidth}"
     "p{0.27\\textwidth}}", "\\toprule",
     "\\textbf{Name} & \\textbf{Identifier} & \\textbf{Architecture} & \\textbf{Role} \\\\",
     "\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

# ---------------------------------------------------------------- conditioned judge controls
cc = rep.get("judge_controls_conditioned", {})
fp = rep.get("judge_controls_falsepos", {})
VCOND = ["gold_verbatim", "scope_stripped", "uncertainty_collapsed", "contradiction_flattened",
         "revision_lost", "provenance_swapped", "unsupported_addition"]
VCLAB = {"gold_verbatim": "gold answer verbatim (accepted)",
         "scope_stripped": "scope deleted, generality asserted",
         "uncertainty_collapsed": "refusal removed, verdict asserted",
         "contradiction_flattened": "one side kept, agreement asserted",
         "revision_lost": "superseded claim presented as current",
         "provenance_swapped": "source ids replaced",
         "unsupported_addition": "fabricated replication appended"}
rows = []
for jm in sorted(cc):
    d = cc[jm]
    for v in VCOND:
        a = d.get(v + "|applicable")
        f = fp.get(jm, {}).get(v)
        if not a:
            continue
        rows.append("%s & %d & %s & %s \\\\" % (
            VCLAB.get(v, v), a["n"], NP(a["rate"]),
            NP(f["rate"]) if f else "--"))
w("judge_table", "\n".join(
    ["\\begin{table}[t]",
     "\\caption{Judge validation against targeted corruptions. Each row is a synthetic response "
     "built from the expert gold answer by destroying exactly one component, applied only to items "
     "that carry the property it destroys. \\emph{Detected}: the judge fires on the matching "
     "component. \\emph{False positive}: the same component fires on the \\emph{unmodified} gold "
     "answer for the same items. The judge accepts the unmodified gold answer as fully faithful "
     "at the rate given in the text.}",
     "\\label{tab:judge}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{4pt}",
     "\\begin{tabular}{lrcc}", "\\toprule",
     "\\textbf{Synthetic response} & $n$ & \\textbf{Detected} & "
     "\\textbf{False positive} \\\\", "\\midrule"] + rows +
    ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

prim_cc = None
for k in cc:
    if "nemotron" in k:
        prim_cc = k
if prim_cc:
    d = cc[prim_cc]

    def R(v, b="applicable"):
        x = d.get(v + "|" + b)
        return NP(x["rate"]) if x else "--"

    def FP(v):
        x = fp.get(prim_cc, {}).get(v)
        return NP(x["rate"]) if x else "--"

    num("numJudgeSentence",
        "On items carrying the property each corruption destroys, the judge accepts the "
        "verbatim gold answer %s of the time and detects five of the six corruptions at %s or "
        "better, the exception being a flattened contradiction at %s (Table~\\ref{tab:judge}). "
        "Sensitivity is not the whole story, though, and the false-positive side is where this "
        "instrument is weakest: on \\emph{unmodified} gold answers no component fires above "
        "%s --- except the unsupported-claim gate, at %s."
        % (R("gold_verbatim"),
           NP(sorted(x["rate"] for x in (d.get(v + "|applicable") for v in
              ("uncertainty_collapsed", "scope_stripped", "contradiction_flattened",
               "revision_lost", "provenance_swapped", "unsupported_addition")) if x)[1]),
           R("contradiction_flattened"),
           FP("scope_stripped"), FP("unsupported_addition")))

    num("numFPUnsupported", FP("unsupported_addition"))

    # "five of six corruptions detected at X or better": X is the second-lowest detection rate
    _det_rates = []
    for _v in ("uncertainty_collapsed", "scope_stripped", "contradiction_flattened",
               "revision_lost", "provenance_swapped", "unsupported_addition"):
        _x = d.get(_v + "|applicable")
        if _x and _x.get("rate") is not None:
            _det_rates.append(_x["rate"])
    _det_rates.sort()
    num("numJudgeDetectFloor", NP(_det_rates[1]) if len(_det_rates) >= 2 else "--")
    num("numJudgeDetectWorst", NP(_det_rates[0]) if _det_rates else "--")

    # the two reliability criteria disagree about which gate is weakest; §6.5 names both
    _scf = rep.get("judge_self_consistency", {}).get("fields", {})
    num("numKappaProv", "%.2f" % _scf["provenance_correct"]["kappa"]
        if _scf.get("provenance_correct") else "--")
    num("numKappaUnsup", "%.2f" % _scf["unsupported_claim"]["kappa"]
        if _scf.get("unsupported_claim") else "--")

    # the gate-sensitivity result, cited in the robustness subsection
    _pv = rep.get("phi_variants", {})
    _g = _pv.get("gap", {})
    _p = _pv.get("phi", {})
    _b = _pv.get("branch", {})

    def _gg(k):
        x = _g.get(k)
        return ("%.1f\\%% [%.1f, %.1f]" % (100 * x["rate"], 100 * x["ci_lo"],
                                          100 * x["ci_hi"])) if x else "--"

    def _bb(k):
        x = _b.get(k)
        return ("%+.1f points [%+.1f, %+.1f]" % (100 * x["mean_diff"], 100 * x["ci_lo"],
                                                 100 * x["ci_hi"])) if x else "--"

    if _g.get("phi_no_grounding") and _b.get("phi_no_grounding"):
        num("numGateSensitivitySentence",
            "Dropping it does not rescue the systems: $\\Phi$ rises only from %s to %s, and "
            "the gap \emph{widens}, from %s to %s, because the gate had been keeping %d "
            "responses out of the component-passing set that then fail $\\Phi$ at a higher "
            "rate. H1 does not depend on it. The state branch does: D4$\\rightarrow$D5 falls "
            "from %s to %s. Some of that is expected, since the D5 failure we document "
            "\emph{is} invented support, but at a %s false-positive rate mechanism and noise "
            "cannot be separated, so the branch magnitude is gate-dependent."
            % (NP(_p["phi_strict"]["mean"]), NP(_p["phi_no_grounding"]["mean"]),
               _gg("phi_strict"), _gg("phi_no_grounding"),
               _g["phi_no_grounding"]["n"] - _g["phi_strict"]["n"],
               _bb("phi_strict"), _bb("phi_no_grounding"),
               FP("unsupported_addition")))
    else:
        num("numGateSensitivitySentence", "PENDING: gate sensitivity not computed.")


# ---------------------------------------------------------------- D4 vs D5 branch
sbc = rep.get("state_branch_components", {})
comp = sbc.get("components", {})
BRANCH_ROWS = [
    ("answerability_correct", "Answerability label correct"),
    ("status_correct", "Status label correct"),
    ("scope_preserved", "Scope preserved"),
    ("revision_preserved", "Revision preserved"),
    ("contradiction_preserved", "Contradiction preserved"),
    ("uncertainty_preserved", "Uncertainty preserved"),
    ("provenance_ok", "Provenance correct"),
    ("src_precision", "Source-id precision"),
    ("grounding_ok", "No unsupported claim"),
    ("answer_correct", "Answer fully correct"),
    ("joint_fidelity", "Joint fidelity $\Phi$"),
]
rows = []
for k, label in BRANCH_ROWS:
    d = comp.get(k)
    if not d or d.get("d4") is None:
        continue
    delta = 100 * (d["d5"] - d["d4"])
    rows.append("%s & %d & %s & %s & %s%.1f \\\\" %
                (label, d["n"], N(d["d4"]), N(d["d5"]),
                 "\\phantom{-}" if delta >= 0 else "", delta))
whyrows = []
for k, v in sorted((sbc.get("why") or {}).items(), key=lambda kv: -kv[1]):
    whyrows.append("%s & %d \\\\" % (k, v))
w("branch_table", "\n".join(
    ["\\begin{table}[t]",
     "\\caption{What changes when the information state is supplied \\emph{instead of} the "
     "evidence text (D4 $\\rightarrow$ D5), on the %d item--system pairs evaluated under both. "
     "The labels the record hands over improve; everything that requires the evidence behind them "
     "degrades.}" % sbc.get("n_pairs", 0),
     "\\label{tab:branch}", "\\centering", "\\small", "\\setlength{\\tabcolsep}{5pt}",
     "\\begin{tabular}{lrrrr}", "\\toprule",
     "\\textbf{Measure (\\%)} & $n$ & \\textbf{D4} & \\textbf{D5} & $\\Delta$ \\\\",
     "\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))

lvp = sbc.get("label_vs_prose", {})
d5l = lvp.get("gold_memory_state", {})
d4l = lvp.get("gold_source", {})
d6l = lvp.get("gold_evidence", {})
def arrow(k):
    d = comp.get(k, {})
    if d.get("d4") is None:
        return "--"
    return "%s$\\rightarrow$%s" % (N(d["d4"]), N(d["d5"]))

num("numStateMechanismSentence",
    "The mechanism is visible component by component (Table~\\ref{tab:branch}). Everything the "
    "record hands over gets better: the answerability label (%s), the status label (%s), scope "
    "preservation (%s) and revision preservation (%s). Everything that needs the evidence behind "
    "those labels gets worse: source-id precision (%s), provenance correctness (%s), freedom from "
    "unsupported claims (%s), and --- the telling one --- uncertainty preservation (%s), which "
    "falls even as the answerability label becomes almost always right. Among responses that emit "
    "the \\emph{correct} answerability label, the share whose prose nonetheless resolves the "
    "question anyway is %s at D5 against %s at D4 and %s at D6." %
    (arrow("answerability_correct"), arrow("status_correct"), arrow("scope_preserved"),
     arrow("revision_preserved"), arrow("src_precision"), arrow("provenance_ok"),
     arrow("grounding_ok"), arrow("uncertainty_preserved"),
     NP(d5l.get("rate")), NP(d4l.get("rate")), NP(d6l.get("rate"))))


# ---------------------------------------------------------------- review-response tables
import make_tables_review
make_tables_review.build(rep, N, NP, cellstr, w, num)

# ---------------------------------------------------------------- human calibration
# paper-wide strict Phi, so the calibration caption can contrast subset vs whole
_ps = rep.get("phi_variants", {}).get("phi", {}).get("phi_strict")
num("numPhiOverallPct", N(_ps["mean"]) if _ps else "--")
import make_tables_calibration
make_tables_calibration.build(N, NP, w, num)

# ---------------------------------------------------------------- judge-free branch
_br = rep.get("phi_variants", {}).get("branch", {})
_db = rep.get("phi_variants", {}).get("det_branch", {})
_bd = _br.get("phi_fully_deterministic")
_bs = _br.get("phi_strict")
_bn = _br.get("phi_no_grounding")
if _bd and _db and _bs:
    def _d(c):
        x = _db.get(c)
        return "%+.0f" % (100 * (x["d5"] - x["d4"])) if x else "--"
    num("numBranchJudgeFreeSentence",
        "Scored by the judge-free rules of Appendix~\\ref{app:rules} alone, D5 does not lose to "
        "D4; it \\emph{wins}, by %.1f points [%.1f, %.1f], because every label the record "
        "supplies is copied and a rule that checks the label rewards the copy: revision %s "
        "points, contradiction %s, uncertainty %s, answerability %s. The one deterministic "
        "component the record does not hand over as a label, provenance, falls by %s. The "
        "deficit appears only when the prose is graded --- by the judge (%+.1f points strict, "
        "%+.1f without the unsupported gate) and by both human annotators. That is the finding "
        "stated precisely: a label-scored evaluation would rank the supplied state above the "
        "supplied evidence, and it would be wrong."
        % (-100 * _bd["mean_diff"], -100 * _bd["ci_hi"], -100 * _bd["ci_lo"],
           _d("revision"), _d("contradiction"), _d("uncertainty"), _d("answerability"),
           _d("provenance").lstrip("+-"), 100 * _bs["mean_diff"], 100 * _bn["mean_diff"]))
    rows = []
    for c, lab in (("revision", "Revision flag"), ("contradiction", "Contradiction flag"),
                   ("uncertainty", "Status / uncertainty"), ("answerability", "Answerability"),
                   ("scope", "Scope slots"), ("provenance", "Provenance (source ids)")):
        x = _db.get(c)
        if x:
            rows.append("%s & %d & %.1f & %.1f & %+.1f \\\\" % (
                lab, x["n"], 100 * x["d4"], 100 * x["d5"], 100 * (x["d5"] - x["d4"])))
    rows.append("\\midrule")
    for k, lab in (("phi_fully_deterministic", "$\\Phi$, rules only (judge-free)"),
                   ("phi_hybrid_det", "$\\Phi$, rules + judged prose"),
                   ("phi_no_grounding", "$\\Phi$, judge without unsupported gate"),
                   ("phi_strict", "$\\Phi$, judge strict")):
        v = _br.get(k)
        if v:
            rows.append("%s & %d & \\multicolumn{2}{c}{paired} & %+.1f [%+.1f, %+.1f] \\\\" % (
                lab, v["n"], -100 * v["mean_diff"], -100 * v["ci_hi"], -100 * v["ci_lo"]))
    w("branch_judgefree_table", "\n".join([
        "\\begin{table}[!ht]",
        "\\caption{The state branch without the judge. Upper block: pass rate of each "
        "deterministic decision rule at D4 and at D5, on the item--system pairs evaluated under "
        "both; a positive difference means D5 passes more often. Lower block: the paired "
        "D5$-$D4 difference in joint fidelity under each aggregation, from fully judge-free to "
        "the strict judge (sign flipped relative to Table~\\ref{tab:phi-variants} so that "
        "positive means D5 better). Every label the record hands over is passed more often at "
        "D5; the only deterministic component that falls is the one it does not hand over.}",
        "\\label{tab:branch-judgefree}", "\\centering", "\\small",
        "\\begin{tabular}{lrccr}", "\\toprule",
        "\\textbf{Component or aggregation} & $n$ & \\textbf{D4} & \\textbf{D5} & "
        "\\textbf{D5$-$D4} \\\\", "\\midrule"]
        + rows + ["\\bottomrule", "\\end{tabular}", "\\end{table}"]))
else:
    num("numBranchJudgeFreeSentence", "PENDING: judge-free branch not computed.")
    w("branch_judgefree_table", "% PENDING\n")

# ---------------------------------------------------------------- robustness summary
import make_tables_robustness
make_tables_robustness.build(rep, w, num)

# ---------------------------------------------------------------- frontier-class check
import make_tables_frontier
make_tables_frontier.build(rep, N, NP, cellstr, w, num)

# ---------------------------------------------------------------- paired step CI
_nf = rep.get("noise_floor", {})
_g64 = _nf.get("d6_minus_d4_paired")
num("numStepSentence",
    ("%+.1f points (95\\%% CI [%+.1f, %+.1f])" %
     (100 * _g64["mean_diff"], 100 * _g64["ci_lo"], 100 * _g64["ci_hi"]))
    if _g64 else "a margin reported in Appendix~\ref{app:controls}")

# ---------------------------------------------------------------- numbers.tex
lines = ["% Auto-generated by iclr_work/make_tables.py. Do not edit.",
         "\\newcommand{\\cmark}{\\ensuremath{\\checkmark}}",
         "\\newcommand{\\xmark}{\\ensuremath{\\times}}",
         "\\newcommand{\\pmark}{\\ensuremath{\\circ}}"]
for k, v in nums.items():
    lines.append("\\newcommand{\\%s}{%s}" % (k, v))
open(os.path.join(PAPER, "numbers.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("wrote %d tables and %d macros" % (len(os.listdir(TAB)), len(nums)))
