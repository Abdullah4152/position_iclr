# 12-question pilot (archived, illustrative)

The original controlled pilot over 12 expert-reviewed construction-audit questions
under partial-source, gold-source and gold-memory-state conditions. Its state
condition supplied assessment information, so it is an illustrative trace rather
than an independently scored test of memory-update failure. **Its results are not
pooled with the later scored evaluation** reported in the rest of this supplement.

---

# Controlled Diagnostic Study Artifacts

This folder contains a no-GLM controlled diagnostic study for the position paper **Scientific Memory Is Not Chat History**.

The study is not a benchmark release or model leaderboard. It is a qualitative illustration showing how adjacent diagnostic conditions can localize failure modes.

## Study Setup

- Items: 12 expert-reviewed construction-audit questions.
- Conditions: `partial-source`, `gold-source`, `gold-memory-state`.
- Models: `moonshotai/kimi-k2-thinking` and `nvidia/llama-3.3-nemotron-super-49b-v1.5`.
- Expected calls: 72.
- Visible responses captured: 71.
- Non-scored rows: 1.

GLM-5.1 was excluded as a system-under-test because GLM was used as annotation-triage evidence elsewhere in the supplement.

## What To Open

| File | Rows/items | Purpose |
|---|---:|---|
| `scoring_reference_by_question.csv` | 12 questions | Gold diagnostic reference: question, gold answer, evidence, source IDs, answerability, and expected failure modes. |
| `diagnostic_prompts.jsonl` | 36 prompts | The exact prompts rendered from 12 questions under 3 diagnostic conditions. |
| `visible_responses_blinded.csv` | 72 response rows | Model outputs for 12 questions x 3 conditions x 2 systems, including one `NOT_SCORED` marker. |
| `response_audit_sanitized.jsonl` | 72 metadata rows | Sanitized run status, latency, attempt count, model, condition, and blind ID. |
| `fenton_ph5_study_data.json` and `FENTON_PH5_STUDY_REPORT.md` | 1 focal case | Detailed Fenton pH 5.0 qualitative analysis showing source access versus structured claim-state memory. |

This folder therefore contains the 12-question diagnostic reference, the rendered diagnostic prompts, and the visible output files needed to inspect the bounded 5DP-subset study. It is not presented as proof of the full five-condition protocol; it is a controlled qualitative instantiation of three diagnostic conditions.

## Relation to the Five-Condition Diagnostic Protocol

The study implements a bounded three-condition subset of the five-condition diagnostic protocol described in the paper.

| Study condition | Relation to paper 5DP | What it tests |
|---|---|---|
| `partial-source` | Degraded retrieval setting between free retrieval and gold-source retrieval | Whether a model recognizes incomplete, one-sided, or scope-limited evidence rather than over-completing from priors. |
| `gold-source` | Gold-source retrieval | Whether access to relevant source evidence is enough to preserve contradiction, scope, and uncertainty. |
| `gold-memory-state` | Gold-memory-state evaluation | Whether a structured claim-state record helps preserve answerability, uncertainty, provenance, and scope. |

The full online free retrieval, offline free retrieval, and gold-evidence reasoning conditions were not run in this bounded position-paper study. They are part of the proposed future benchmark protocol rather than this qualitative diagnostic exhibit.

## Files

- `locked_predictions.md`: pre-call predictions and condition definitions.
- `run_plan.json`: run metadata and no-GLM rationale.
- `diagnostic_prompts.jsonl`: exact prompts for 12 questions x 3 conditions.
- `scoring_reference_by_question.csv`: 12-row gold answer/evidence reference.
- `visible_responses_blinded.csv`: 72-row visible response file in blinded scoring format.
- `response_audit_sanitized.jsonl`: 72-row sanitized response metadata.
- `fenton_ph5_study_data.json`: Fenton study prompts and visible responses.
- `fenton_ph5_responses_table.csv`: compact Fenton response table.
- `FENTON_PH5_STUDY_REPORT.md`: detailed human-readable study report.

The scoring columns in `visible_responses_blinded.csv` are intentionally blank. The file is released as a blinded response sheet and audit artifact; the supplement does not claim completed blinded manual scoring or model-ranking results. The qualitative interpretation is provided in `FENTON_PH5_STUDY_REPORT.md`.

## How To Read The Fenton Case

The Fenton pH 5.0 question is an uncertainty-abstention item. The evidence says oxidant identity depends on pH and ligand environment, but it does not specify the exact pH threshold or ligand context at pH 5.0.

The diagnostic contrast is:

- `gold-source`: relevant evidence is supplied, but a model can still make an over-specific inference.
- `gold-memory-state`: answerability and status are explicit, helping preserve uncertainty.

This is why the case is useful for a position paper: it shows the difference between source access and scientific claim-state memory without claiming benchmark-scale results.
