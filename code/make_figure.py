#!/usr/bin/env python3
"""Figure 1: the diagnostic curve and the compositional gap, drawn from results/report.json."""
import json, os, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
rep = json.load(open(os.path.join(HERE, "results", "report.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "..", "paper", "figures")
os.makedirs(OUT, exist_ok=True)

CHAIN = ["closed_book", "offline_retrieval", "online_history", "gold_source", "gold_evidence"]
SHORT = {"closed_book": "D1\nclosed\nbook", "offline_retrieval": "D2\nretrieval-\nrestricted",
         "online_history": "D3\nfull\nhistory", "gold_source": "D4\ngold\nsource",
         "gold_evidence": "D6\ngold\nevidence"}
REASON_LABEL = {"uncertainty": "uncertainty collapsed", "scope": "scope dropped",
                "contradiction": "contradiction flattened", "revision": "revision lost",
                "answerability": "answerability wrong", "provenance": "provenance wrong"}
INK = "#1f2933"
ACCENT = "#2f6f9f"
WARN = "#b4451f"
MUTED = "#9aa5b1"
PALETTE = ["#b4451f", "#d08a3e", "#7a9e7e", "#4f7ca8", "#8c6f9e", "#a9a9a9"]

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": INK, "axes.linewidth": 0.6,
    "xtick.color": INK, "ytick.color": INK, "text.color": INK, "axes.labelcolor": INK,
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 1.95))

# ---- panel A: the diagnostic curve --------------------------------------------
lj = rep["ladder_joint_fidelity"]["ALL"]
xs = list(range(len(CHAIN)))
ys = [100 * lj[c]["mean"] for c in CHAIN]
lo = [100 * (lj[c]["mean"] - lj[c]["ci_lo"]) for c in CHAIN]
hi = [100 * (lj[c]["ci_hi"] - lj[c]["mean"]) for c in CHAIN]
ax1.errorbar(xs, ys, yerr=[lo, hi], color=ACCENT, marker="o", markersize=4.5,
             linewidth=1.5, capsize=2.5, elinewidth=0.8, zorder=3, label="nested chain")
d5 = lj["gold_memory_state"]
ax1.errorbar([3.5], [100 * d5["mean"]],
             yerr=[[100 * (d5["mean"] - d5["ci_lo"])], [100 * (d5["ci_hi"] - d5["mean"])]],
             color=WARN, marker="D", markersize=5, linestyle="none", capsize=2.5,
             elinewidth=0.8, zorder=4, label="D5 gold memory state (branch)")
ax1.annotate("D5\nstate without\nits evidence", xy=(3.5, 100 * d5["mean"]),
             xytext=(2.62, 100 * d5["mean"] - 1.5), color=WARN, fontsize=6.5,
             ha="center", va="top", linespacing=1.15)
ax1.set_xticks(xs)
ax1.set_xticklabels([SHORT[c] for c in CHAIN], linespacing=1.05)
ax1.set_ylabel("joint state fidelity $\\Phi$ (%)")
ax1.set_ylim(bottom=0)
ax1.set_title("(a) Removing work helps, up to a point", loc="left")
ax1.grid(axis="y", color=MUTED, alpha=0.25, linewidth=0.5)
ax1.set_axisbelow(True)
for sp in ("top", "right"):
    ax1.spines[sp].set_visible(False)
ax1.set_ylim(bottom=0, top=max(100 * lj[c]["ci_hi"] for c in CHAIN) * 1.28)
ax1.legend(frameon=False, loc="upper left", handlelength=1.4, borderpad=0.2,
           labelspacing=0.25)

# ---- panel B: the compositional gap -------------------------------------------
g = rep["compositional_gap"]["by_condition"]
conds = [c for c in ["offline_retrieval", "online_history", "gold_source",
                     "gold_memory_state", "gold_evidence"] if g.get(c, {}).get("n_component_pass")]
labels = {"offline_retrieval": "D2", "online_history": "D3", "gold_source": "D4",
          "gold_memory_state": "D5", "gold_evidence": "D6"}
reasons = collections.Counter()
for c in conds:
    for k, v in g[c]["reasons"].items():
        reasons[k] += v
order = [k for k, _ in reasons.most_common()]
xs = list(range(len(conds)))
passes = [g[c]["n_component_pass"] - g[c]["n_joint_fail"] for c in conds]
ax2.bar(xs, passes, color="#dfe6ec", edgecolor=INK, linewidth=0.4,
        label="also passes $\\Phi$")
bottom = list(passes)
for i, k in enumerate(order):
    vals = [g[c]["reasons"].get(k, 0) for c in conds]
    # normalise so segment heights sum to the number of failures
    scaled = []
    for c, v in zip(conds, vals):
        tot = sum(g[c]["reasons"].values()) or 1
        scaled.append(g[c]["n_joint_fail"] * v / tot)
    ax2.bar(xs, scaled, bottom=bottom, color=PALETTE[i % len(PALETTE)],
            edgecolor=INK, linewidth=0.4, label=REASON_LABEL.get(k, k))
    bottom = [b + s for b, s in zip(bottom, scaled)]
ax2.set_xticks(xs)
ax2.set_xticklabels([labels[c] for c in conds])
ax2.set_ylabel("responses passing every\ncomponent check")
ax2.set_title("(b) What the component checks miss", loc="left")
ax2.grid(axis="y", color=MUTED, alpha=0.25, linewidth=0.5)
ax2.set_axisbelow(True)
for sp in ("top", "right"):
    ax2.spines[sp].set_visible(False)
ax2.set_ylim(0, max(g[c]["n_component_pass"] for c in conds) * 1.85)
ax2.legend(frameon=False, loc="upper center", ncol=2, handlelength=1.0,
           borderpad=0.2, labelspacing=0.2, columnspacing=0.8, handletextpad=0.4)

fig.tight_layout(pad=0.6, w_pad=1.6)
fig.savefig(os.path.join(OUT, "fig1_gap.pdf"), bbox_inches="tight")
print("wrote paper/figures/fig1_gap.pdf")
