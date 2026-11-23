# Scientific Memory Is Not Chat History

## Repository map

```
code/                           Construction, inference, scoring, analysis and table scripts
data/                           160-item evaluation set, transcripts, transfer items, judge controls
prompts/                        Rendered prompts, one JSON object per (item, setting, format)
scores/                         Per-response scores and aggregate summaries
  raw/                          Stored model responses and judge outputs, as returned
human_calibration/              Blinded grading sheet, annotation protocol and calibration results
construction/
  audit/                        Source arcs, candidate pool, expert-review records, guidelines
  provenance/                   Item-level provenance map for the selected evaluation set
  pilot_12q/                    Earlier 12-question pilot, archived (not pooled with the evaluation)
README.md                       Setup and folder-by-folder run guide
```

The evaluation set contains 160 items drawn from 30 evidence arcs and a usable reviewed pool of 287 candidates,
plus 24 author-constructed transfer items. Items span chemistry (54), computational biology (51) and materials
science (55). Every item is posed under six settings that differ only in the information supplied to the model:

| Setting | Information supplied |
|---|---|
| D1 | Question alone |
| D2 | Top-3 sessions from a deterministic BM25 retriever |
| D3 | Complete interleaved multi-session transcript |
| D4 | Gold source identifiers and evidence text |
| D5 | Information-state record without source text |
| D6 | Information-state record and gold evidence |

The stored responses come from five evaluated models, graded by a primary and a secondary judge:

| Role | Models |
|---|---|
| Evaluated | `openai/gpt-oss-20b`, `meta/llama-3.2-11b-vision-instruct`, `mistralai/mistral-nemotron`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Primary judge | `nvidia/nemotron-3-super-120b-a12b` |
| Secondary judge, triage and controls | `poolside/laguna-xs-2.1` |

API keys (`keys.txt`), the paper sources and the original supplement directory are excluded from the source
tree. The released files under `data/`, `prompts/`, `scores/` and `human_calibration/` are the outputs of the
pipeline below.

## 1. Prepare the Environment

Clone the repository and run every command from the repository root.

```
export REPOSITORY_URL=https://github.com/Abdullah4152/position_iclr.git
git clone "$REPOSITORY_URL" position_iclr
cd position_iclr
python3 --version
```

Use Python 3.11 or newer. The build, inference, scoring and analysis scripts use only the standard library;
`make_figure.py` additionally requires `matplotlib`. There is no dependency lockfile. Install `matplotlib` in a
virtual environment rather than globally:

```
python3 -m venv .venv
source .venv/bin/activate
pip install matplotlib
```

## 2. Recreate the Working Layout

The scripts resolve paths relative to `code/` (`data/`, `raw/` and `results/` alongside the scripts) and to the
original supplement directory next to it. Copy the released files into that layout:

```
mkdir -p code/data code/raw code/results
cp data/items_160.json code/data/items.json
cp data/transcripts.json data/transfer_items_built.json data/build_report.json data/review_build_report.json code/data/
cp prompts/payload.jsonl prompts/payload_review.jsonl code/data/
cp scores/raw/*.jsonl code/raw/

SUP="1036_Scientific_Memory_Is_Not__Supplementary Material (2)/neurips_position_supplement_final/data"
mkdir -p "$SUP"
cp construction/audit/expert_review_300.csv "$SUP/expert_review_sample_300_completed.csv"
cp construction/audit/source_arcs_30.jsonl "$SUP/expert_reviewed_source_arcs_30.jsonl"
```

These copies are local working files; do not commit them. Check the evaluation set:

```
sha256sum data/items_160.json
python3 -c "import json,collections; d=json.load(open('data/items_160.json')); print(len(d), collections.Counter(i['domain'] for i in d))"
```

Expected `items_160.json` SHA-256: b61e5699f7443099b8cfbd5e467c7d7fd0f17c064590d53d57eb732acd23c8f7. Expected
counts: 160 items; chemistry 54, computational_biology 51, materials_science 55.

`prompts/payload.jsonl` holds 1,832 records (main 960, format_ablation 480, pushback 320, transfer 72).
`prompts/payload_review.jsonl` holds the 850 control-arm records:

| Arm | What it changes |
|---|---|
| `noise` | Two additional generations at D4 and D6 with conditions unchanged |
| `nocaveat` | Removes the closing curator note from transcript and evidence |
| `parity` | Renders D4, D5 and D6 with byte-identical instructions |

To rebuild the evaluation set, transcripts and prompts from the source arcs instead of using the released copies:

```
python3 code/build_items.py
python3 code/build_review_studies.py
python3 code/make_controls_v2.py
```

## 3. Generate Model Responses

`runner.py` calls an OpenAI-compatible chat-completions endpoint (NVIDIA NIM by default). It reads API keys
from `keys.txt`, one key per line; keep that file outside version control. Every subcommand is resumable:
record IDs already present in `--out` are skipped.

### Evaluated-model responses

```
python3 code/runner.py sut --model openai/gpt-oss-20b --payload prompts/payload.jsonl --out responses_gptoss20b.jsonl
```

Generation uses temperature 0. The completion budget is 1,500 tokens by default, 4,000 for reasoning models
(`nemotron`, `gpt-oss`, `kimi`, `deepseek`, `glm`) and 6,500 for `lightning` and `nano-omni` models; override
it with `--max-tokens`. Restrict to one study with `--studies main,transfer`.

### Judging

```
python3 code/runner.py judge --model nvidia/nemotron-3-super-120b-a12b --responses responses_gptoss20b.jsonl \
    --items data/items_160.json --transfer-items data/transfer_items_built.json --out judgments_gptoss20b.jsonl
```

The judge runs at temperature 0 with a 2,500-token budget. Pass `--no-think` to disable judge reasoning,
`--subsample` to grade a random fraction of responses, and `--tag` to label a repeated pass.

### Judge-validation controls and annotation triage

```
python3 code/runner.py controls --model poolside/laguna-xs-2.1 --payload data/judge_controls_v2.jsonl \
    --items data/items_160.json --out controlsv2_laguna.jsonl
python3 code/runner.py triage --model poolside/laguna-xs-2.1 --payload prompts/triage_payload.jsonl --out triage_laguna.jsonl
```

`data/judge_controls_v2.jsonl` contains 633 synthetic responses: the gold answer verbatim and six targeted
single-component corruptions. Place new output files in `code/raw/` before scoring.

## 4. Metric Settings

Use these definitions; each is computed per graded response in `scores/per_item_scores.csv`:

- **Answer correct:** the judge rates answer fidelity `correct`; `partial` counts only under the lenient verdict.
- **Grounding:** the judge reports no unsupported claim.
- **Provenance:** the judge does not mark the cited provenance as incorrect.
- **Preservation:** none of contradiction, revision, scope or uncertainty preservation is marked `no`;
  not-applicable fields do not count as failures.
- **Joint fidelity:** answer correct, grounded, correct provenance and preservation all hold, and, for structured
  outputs, the predicted answerability matches the expert label.
- **Source-ID precision / recall / F1:** set comparison of predicted and gold source identifiers.

`code/det_rules.py` contains the judge-free decision rule for each component.

## 5. Score Responses and Build Aggregates

```
python3 code/analyze.py
```

This writes `code/results/per_item_scores.jsonl` and `code/results/report.json` and takes about a minute.
Run on the released raw files, it reproduces `scores/aggregate_report.json` except for the `frontier`,
`judge_self_consistency` and pushback arm-balance sections, which rely on runs whose raw files are not included.

## 6. Reproduce Tables and Figure

```
python3 code/make_tables.py
python3 code/make_tables_review.py
python3 code/make_tables_calibration.py
python3 code/make_figure.py
```

Tables are written to `paper/tables/` and the figure to `paper/figures/fig1_gap.pdf`. `make_tables.py` writes its
LaTeX tables and then stops before writing `paper/numbers.tex`, because it imports `make_tables_robustness`,
which is not included in this repository.

## 7. Reproduce Human Calibration

`human_calibration/` contains the blinded grading sheet, the protocol given to annotators
(`HUMAN_CALIBRATION_PROTOCOL.md`), the two completed annotator sheets and the computed output. To print the
agreement report against the frozen key:

```
python3 code/analyze_human_calibration.py human_calibration/results/grader_a.csv human_calibration/results/grader_b.csv \
    --key human_calibration/results/key_and_judge_verdicts_FROZEN.jsonl
```

To regenerate `human_calibration.json`, place the frozen files where `calibration_deep.py` expects them; this
requires `code/results/per_item_scores.jsonl` from Step 5:

```
R=code/data/human_calibration_results
mkdir -p "$R"
cp human_calibration/results/grader_a.csv "$R/STUDENT_A.csv"
cp human_calibration/results/grader_b.csv "$R/STUDENT_B.csv"
cp human_calibration/results/key_and_judge_verdicts_FROZEN.jsonl "$R/"
python3 code/calibration_deep.py
```

The output `code/results/human_calibration.json` is identical to `human_calibration/results/human_calibration.json`.

## 8. Archived 12-Question Pilot

`construction/pilot_12q/` is an earlier pilot and is not pooled with the evaluation. Audit its released artifacts:

```
cd construction/pilot_12q
python3 score.py audit --gold scoring_reference_by_question.csv --responses visible_responses_blinded.csv \
    --audit response_audit_sanitized.jsonl
```

Score a system's structured predictions with
`python3 score.py compute --gold scoring_reference_by_question.csv --predictions my_predictions.jsonl --by category`;
the predictions format is documented at the top of `score.py`.

## Notes

Item labels come from expert review of the source material. Each item carries one expert decision; the agreement
coefficients in `construction/audit/` compare model-assisted triage with expert labels rather than two independent
experts. The evaluation set is drawn from a pool enriched for revision, contradiction and conditional evidence.
