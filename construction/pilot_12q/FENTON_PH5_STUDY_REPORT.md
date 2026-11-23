# Fenton pH 5.0 Controlled Diagnostic Study Report

This report isolates the strongest qualitative result from the two-model no-GLM controlled diagnostic study. The item tests uncertainty preservation under condition scope: whether the model should answer definitively when the evidence describes a pH-dependent crossover but does not specify the exact behavior at pH 5.0.

## Item Metadata

- Question ID: `scientific_memory_chemistry_0007_q08`
- Domain: `chemistry`
- Category: `uncertainty_abstention`
- Answerability: `unanswerable`
- Expected status: `insufficient_evidence`
- Source IDs: `ch07_p1|ch07_p2|ch07_p3`
- Expected failure modes: `uncertainty_collapse; overclaim`

## Gold Answer

```text
No, the dialogue does not provide sufficient evidence to definitively state which oxidant dominates at pH 5.0; while Bataineh 2012 indicates a crossover near neutral pH and HO• dominance at low pH, the exact transition point and influence of ligand environment at pH 5.0 are not specified, creating uncertainty about the dominant species under these specific conditions.
```

## Full Evidence Reference

```text
source_arc:ch07:ch07:evidence_evolution [establishes_uncertainty] Walling 1975 codified the hydroxyl radical mechanism. Pestovsky 2005 spectroscopically identified aqueous Fe(IV)=O. Bataineh 2012 showed pH-dependent mechanistic crossover: hydroxyl radical at low pH, Fe(IV)=O at neutral pH. The 'just hydroxyl radicals' claim is incomplete; the active oxidant identity depends on pH and ligand environment.
source_arc:ch07:ch07:expert_note [scopes] Mechanism-revised arc with pH-dependent crossover. Excellent for condition-bounded mechanism QA.
```

## What We Gave The Models

### Condition: `partial-source`

```text
You are a research assistant answering a question about a multi-session scientific dialogue. A retrieval system returned the PARTIAL result below. Other relevant evidence may exist in the dialogue or in the cited sources but was not surfaced by retrieval this turn.

Retrieved source IDs (partial): ch07_p1
Retrieved evidence (partial):
source_arc:ch07:ch07:evidence_evolution [establishes_uncertainty] Walling 1975 codified the hydroxyl radical mechanism. Pestovsky 2005 spectroscopically identified aqueous Fe(IV)=O. Bataineh 2012 showed pH-dependent mechanistic crossover: hydroxyl radical at low pH, Fe(IV)=O at neutral pH.

Question: Based on the dialogue, can we definitively state whether Fe(IV)=O or HO• is the dominant oxidant in Fenton reactions at pH 5.0?

Answer using only the supplied partial evidence. If the available fragment is insufficient, appears one-sided, or omits relevant scope, contradicting evidence, or later revisions, reflect that explicitly rather than completing from priors. Do not extrapolate beyond what is supplied. Cite the supplied source IDs where applicable.
```
### Condition: `gold-source`

```text
You are a research assistant answering a question about a multi-session scientific dialogue. The relevant source evidence has been retrieved for you below.

Source IDs: ch07_p1, ch07_p2, ch07_p3
Evidence text:
source_arc:ch07:ch07:evidence_evolution [establishes_uncertainty] Walling 1975 codified the hydroxyl radical mechanism. Pestovsky 2005 spectroscopically identified aqueous Fe(IV)=O. Bataineh 2012 showed pH-dependent mechanistic crossover: hydroxyl radical at low pH, Fe(IV)=O at neutral pH. The 'just hydroxyl radicals' claim is incomplete; the active oxidant identity depends on pH and ligand environment.
source_arc:ch07:ch07:expert_note [scopes] Mechanism-revised arc with pH-dependent crossover. Excellent for condition-bounded mechanism QA.

Question: Based on the dialogue, can we definitively state whether Fe(IV)=O or HO• is the dominant oxidant in Fenton reactions at pH 5.0?

Answer using only the supplied evidence. If the evidence is mixed, contradictory, scoped to specific methods or conditions, or insufficient, reflect that in your answer. Cite the specific source IDs that support each part of your answer.
```
### Condition: `gold-memory-state`

```text
You are a research assistant answering a question about a multi-session scientific dialogue. Your persistent claim-state memory has been loaded for you below. You do not have access to raw source evidence in this turn; you must answer using the structured memory state.

Claim-state record:
{
  "claim_topic": "Based on the dialogue, can we definitively state whether Fe(IV)=O or HO• is the dominant oxidant in Fenton reactions at pH 5.0?",
  "current_assessment": "No, the dialogue does not provide sufficient evidence to definitively state which oxidant dominates at pH 5.0; while Bataineh 2012 indicates a crossover near neutral pH and HO• dominance at low pH, the exact transition point and influence of ligand environment at pH 5.0 are not specified, creating uncertainty about the dominant species under these specific conditions.",
  "status": "insufficient_evidence",
  "answerability": "unanswerable",
  "supporting_evidence_ids": [
    "ch07_p1",
    "ch07_p2",
    "ch07_p3"
  ],
  "method_scope": "not specified in dialogue",
  "condition_scope": "not specified in dialogue",
  "cross_session_required": true,
  "cross_paper_required": false
}

Question: Based on the dialogue, can we definitively state whether Fe(IV)=O or HO• is the dominant oxidant in Fenton reactions at pH 5.0?

Answer using only your claim-state memory. Preserve provenance, contradictions, scope, and uncertainty as recorded. If the answerability field indicates the question is unanswerable or ambiguous, your answer must reflect that rather than producing a determinate answer.
```

## What The Models Output

### Model: Kimi K2 Thinking (`moonshotai/kimi-k2-thinking`)

#### `partial-source` output

- Blind ID: `B052`
- Status: `ok`
- Visible response characters: `621`

```text
The partial evidence from ch07_p1 describes Bataineh 2012's pH-dependent mechanistic crossover, with HO• as the dominant oxidant at low pH and Fe(IV)=O at neutral pH. However, the fragment does not specify the quantitative pH threshold for this transition, making it impossible to determine whether pH 5.0 qualifies as "low pH" or falls within an intermediate crossover region. The evidence explicitly "[establishes_uncertainty]" rather than providing a definitive resolution for this specific condition. Consequently, based solely on the supplied fragment, we cannot definitively state which oxidant dominates at pH 5.0.
```
#### `gold-source` output

- Blind ID: `B072`
- Status: `ok`
- Visible response characters: `577`

```text
The evidence shows that the dominant oxidant in Fenton reactions is pH‑dependent: hydroxyl radicals (HO•) are favored at low pH, while Fe(IV)=O becomes dominant at neutral pH (Bataineh 2012; ch07_p1). Because the exact pH at which the crossover occurs is not defined, we cannot definitively state which oxidant prevails at pH 5.0. The oxidant identity also depends on the ligand environment (ch07_p1), and the expert note confirms that the mechanism is condition‑bounded (ch07_p2). Consequently, based on the supplied evidence, the dominant oxidant at pH 5.0 remains uncertain.
```
#### `gold-memory-state` output

- Blind ID: `B028`
- Status: `ok`
- Visible response characters: `534`

```text
Based on the dialogue, we cannot definitively state whether Fe(IV)=O or HO• is the dominant oxidant in Fenton reactions at pH 5.0. While Bataineh 2012 indicates a crossover near neutral pH with HO• dominance at low pH, the exact transition point is not specified. Additionally, the influence of the ligand environment at pH 5.0 remains unaddressed in the available evidence. This insufficient specification of both the pH threshold and ligand effects creates uncertainty, making the question unanswerable with the current information.
```
### Model: Nemotron/Llama 3.3 49B (`nvidia/llama-3.3-nemotron-super-49b-v1.5`)

#### `partial-source` output

- Blind ID: `B059`
- Status: `ok`
- Visible response characters: `725`

```text
The provided evidence indicates a pH-dependent mechanistic crossover in Fenton reactions, with HO• dominant at low pH and Fe(IV)=O at neutral pH (Bataineh 2012). However, the specific pH threshold for this transition is not defined in the retrieved fragment. Since pH 5.0 falls between "low" and "neutral" pH ranges (which are not explicitly quantified here), the available evidence does not definitively establish which oxidant is dominant at this exact pH. The uncertainty arises from the absence of precise pH boundaries in the cited study (Bataineh 2012) and the lack of additional context or later revisions in the partial retrieval. Thus, a conclusive determination cannot be made based solely on the supplied evidence.
```
#### `gold-source` output

- Blind ID: `B001`
- Status: `ok`
- Visible response characters: `652`

```text
Based on the provided evidence, Bataineh 2012 demonstrated a pH-dependent mechanistic crossover, where HO• is the dominant oxidant at low pH and Fe(IV)=O at neutral pH. Since pH 5.0 falls within the low pH range, the evidence supports HO• as the dominant oxidant under these conditions. However, the expert note [scopes] clarifies that the active oxidant identity also depends on ligand environment, which is not specified here. Thus, while the pH dependency points to HO• dominance at pH 5.0, the absence of ligand-specific data introduces some uncertainty. The conclusion is primarily anchored in Bataineh 2012 and the general pH-dependent framework.
```
#### `gold-memory-state` output

- Blind ID: `B036`
- Status: `ok`
- Visible response characters: `682`

```text
Based on the claim-state memory, the question of whether Fe(IV)=O or HO• dominates in Fenton reactions at pH 5.0 cannot be definitively answered. The dialogue indicates uncertainty due to insufficient evidence about the exact transition point between oxidant dominance and the influence of ligand environments at this specific pH. While Bataineh 2012 suggests a crossover near neutral pH and HO• dominance at low pH, the precise conditions at pH 5.0 remain unresolved, leaving the dominant species indeterminate under these parameters. The assessment explicitly flags this as "unanswerable" with "insufficient_evidence," requiring further clarification beyond the provided dialogue.
```

## Interpretation

The Fenton item is strong because it separates access to evidence from preservation of answerability. The evidence says that the Fenton oxidant identity changes with pH and ligand environment, but it does not provide the exact pH threshold or ligand context needed to decide pH 5.0. The faithful answer is therefore uncertainty, not a determinate oxidant identity.

Kimi preserved this uncertainty in all three conditions. Nemotron/Llama preserved it in `partial-source` and `gold-memory-state`, but in `gold-source` it made an over-specific inference: it inferred that pH 5.0 falls in the low-pH regime and therefore supports hydroxyl radical dominance. The relevant source text was present, but the model still converted scoped uncertainty into a confident answer.

The `gold-memory-state` condition fixed the issue because the structured state explicitly represented `answerability = unanswerable`, `status = insufficient_evidence`, and the unresolved scope. This is a compact qualitative demonstration of the paper's thesis: scientific memory is not just having source text; it is preserving the claim state, including scope and uncertainty.

## Position-Paper Use

Use this as a qualitative illustration, not as a benchmark result. The strongest phrasing is: "In a targeted controlled diagnostic study, a source-recall condition still produced uncertainty collapse on a Fenton pH-scope item, while the gold-memory-state condition preserved the unanswerable status." Avoid claiming model rankings or statistical significance until the blinded scoring sheet is manually completed.
