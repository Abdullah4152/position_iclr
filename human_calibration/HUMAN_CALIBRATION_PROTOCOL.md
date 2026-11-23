# Human Calibration Pass — Annotator Protocol

**Study:** *Scientific Memory Is Not Chat History: Reframing Long-Term Memory Evaluation for Research Agents*
**Task:** grade 120 model responses on seven components, blind to system identity and to the model judge's verdicts.
**Effort:** roughly one annotator-day (6–8 hours) for one grader; see [Effort and pacing](#effort-and-pacing).
**Deliverable:** one filled CSV per grader, plus a short notes file.

---

## 1. Why this exists

Every preservation component in the paper is graded by a model judge (`nvidia/nemotron-3-super-120b-a12b`). That judge was validated against targeted corruptions and is reasonably self-consistent, but two facts make its absolute numbers untrustworthy as levels:

- It agrees only **moderately with a second judge** (answer fidelity 54.2%, κ = 0.32).
- On **verbatim expert gold answers** — text that is correct by construction — its unsupported-claim check fires **44.2% of the time**. No other component exceeds 5.0%.

Because of this the paper reports all absolute rates as *judge-relative* and rests its claims on comparisons made under one fixed instrument. **This pass is what converts those judge-relative levels into calibrated ones.** Concretely, your labels will be used to answer:

1. What is the joint-fidelity rate Φ under human grading, versus 13.7% under the judge?
2. Is the compositional gap (19.8% under the judge) a real phenomenon or an artifact of judge noise?
3. Is the unsupported-claim gate's 44.2% false-positive rate confirmed by humans? This decides whether that gate can be kept at all.
4. Which components can a future automatic scorer be trusted on, and which need a human?

Question 3 is the most consequential. **If you find the judge is flagging clean answers as unsupported, that is a finding, not a mistake on your part.** Do not adjust your grading to match what you imagine the judge said.

---

## 2. Who should do this

You need someone who can read a paragraph of computational biology, chemistry, or materials science and tell whether a claim overstates its evidence. That is the actual skill required. You do **not** need to be a specialist in all three domains, because every row gives you the expert gold answer and the gold evidence — you are judging the response *against supplied ground truth*, not against your own knowledge of the literature.

A graduate student or postdoc in any experimental science can do this well. Someone with no science background will struggle with `scope_preserved` and `unsupported_claim` in particular.

**Two graders are strongly preferred over one.** See [Quality control](#7-quality-control).

---

## 3. Files

| File | What it is | Open it? |
|---|---|---|
| `grading_sheet_blinded.csv` | 120 rows to grade. The seven `human_*` columns are empty and are yours to fill. | **Yes — this is your worksheet** |
| `key_and_judge_verdicts.jsonl` | System identity, condition, and the judge's verdict for each `blind_id` | **No. Not until you have finished and saved.** |
| `README.md` | Short orientation note | Optional |
| This file | Full protocol | Read once before starting |

The sheet is blinded deliberately. Knowing that a response came from the weakest system, or that the judge called it unsupported, measurably shifts grading. **Opening the key file before you finish invalidates the pass.**

### Columns you read

| Column | Meaning |
|---|---|
| `blind_id` | Row identifier (`H001`–`H120`). Keep it unchanged. |
| `question` | What the system was asked |
| `gold_answer` | The expert-validated correct answer. **This is your ground truth.** |
| `gold_answerability` | `answerable` / `ambiguous` / `unanswerable` — what the evidence actually supports |
| `gold_status` | Expert status label, e.g. `revised`, `mixed/conditional`, `insufficient` |
| `gold_source_ids` | Source identifiers the answer should attribute to, `\|`-separated |
| `gold_method_slots` | Method limits that must stay attached (assay, protocol, split…) |
| `gold_condition_slots` | Condition limits that must stay attached (pH, solvent, cohort…) |
| `evidence_text` | The underlying evidence |
| `response` | **The text you are grading.** Structured fields are appended in `[field=value]` form. |

> **Note on `response`:** some rows end with bracketed tags like `[status=revised] [source_ids=['ms09']]`. These are the system's own structured output, and they are part of the response. Grade them together with the prose. A response whose `[status]` tag says `insufficient` while its prose gives a confident answer is *not* preserving uncertainty — that mismatch is exactly the kind of failure this study is about.

---

## 4. The seven judgements

Fill one value per column. Definitions below are **verbatim the definitions given to the model judge**, so that human and machine labels are comparable — that comparability is the whole point of the exercise. Where the machine definition is ambiguous, the added guidance is marked *Clarification*.

### `human_answer_fidelity` → `correct` | `partial` | `incorrect`

- **`correct`** — the response conveys the gold conclusion *with the same strength and the same qualifications*.
- **`partial`** — the core conclusion is right, but a qualification, a scope limit, or one side of the evidence is missing or weakened.
- **`incorrect`** — it contradicts the gold conclusion, or answers a different question.

*Clarification.* "Same strength" is doing real work. If the gold answer says a mechanism is *likely* and the response says it *is* the mechanism, that is `partial`, not `correct`. Verbosity is not a fault; a long correct answer is `correct`. An answer that is right but buried in hedging is still `correct` if the gold conclusion is recoverable and not contradicted.

### `human_unsupported_claim` → `true` | `false`

`true` if the response asserts **any** specific fact, number, mechanism, condition, or attribution that the gold answer and gold evidence do not support.

*Clarification — read this one carefully, it is the component under the most suspicion.*

- The bar is **assertion of unsupported specifics**, not "said something not in the gold text". General framing, restatement of the question, and standard background that any practitioner would accept are **not** unsupported claims.
- Hedged statements (`this may suggest`, `one possibility is`) are **not** unsupported claims unless the hedge is cosmetic and the response proceeds to rely on the content as established.
- A **number, date, or citation** that appears nowhere in the gold evidence is the clearest `true`.
- Correctly declining to answer is never an unsupported claim.
- If you find yourself marking `true` on most rows, stop and re-read this section. The judge appears to do exactly that, and whether it is right is what we are measuring.

### `human_contradiction_preserved` → `yes` | `no` | `na`

- `yes` — conflicting or competing evidence is kept visible.
- `no` — it is flattened into agreement, or one side is silently dropped.
- `na` — **the gold record contains no conflict.** Check `gold_status` and `evidence_text`; if there is nothing to preserve, the answer is `na`, not `yes`.

### `human_revision_preserved` → `yes` | `no` | `na`

- `yes` — the response reflects that later evidence revised an earlier claim.
- `no` — it presents a superseded claim as current.
- `na` — the gold record contains no revision.

*Clarification.* The response does not have to narrate the revision history. It is `yes` if it asserts the *post-revision* state. It is `no` only if it asserts the superseded claim as though still standing.

### `human_scope_preserved` → `yes` | `no` | `na`

- `yes` — the method and condition limits in `gold_method_slots` / `gold_condition_slots` are attached to the claim.
- `no` — the claim is stated more generally than the gold scope allows.
- `na` — the gold record carries no scope limits (both slot fields empty or `{}`).

*Clarification.* Attachment can be paraphrase; exact slot wording is not required. "In aqueous solution at low pH" satisfies a pH condition slot. Naming *some* limits but dropping a decisive one is `no`.

### `human_uncertainty_preserved` → `yes` | `no` | `na`

- `yes` — unresolved, insufficient, or conditional evidence stays unresolved.
- `no` — it is converted into a definitive answer.
- `na` — the gold record is definitive.

*Clarification.* Cross-check `gold_answerability`. If it is `unanswerable` or `ambiguous` and the response commits to a determinate answer, that is `no` — **even if the determinate answer happens to be plausible.** This is the paper's central failure mode; be strict here.

### `human_provenance_correct` → `yes` | `no` | `na`

- `yes` — claims are attributed to the gold sources.
- `no` — attributed to the wrong source, or attributed without support.
- `na` — the response makes no attribution and none was required.

*Clarification.* Compare against `gold_source_ids`. Identifier format need not match exactly (`Sun 2009` for `ms09` is fine if unambiguous). A response that cites *nothing* where the question explicitly asks for an evidence identifier is `no`, not `na`.

### `human_notes` (free text, optional)

Use it for anything that does not fit: the row is malformed, the gold answer looks wrong to you, the response is empty or truncated, or you were genuinely torn. **Flag disagreement with the gold answer here rather than grading around it** — grade against the gold as given, and record your objection.

---

## 5. Procedure

For each row, in this order:

1. Read `question`.
2. Read `gold_answer`, `gold_answerability`, `gold_status`, and the two slot fields. **Form your expectation of what a correct answer must contain before reading the response.** This ordering matters; reading the response first anchors you.
3. Skim `evidence_text` for what is and is not supported.
4. Read `response` in full, including bracketed structured fields.
5. Fill all seven columns.
6. Move on. **Do not go back and revise earlier rows for consistency.**

That last rule is not a style preference. Retroactive consistency-fixing makes the agreement statistics unusable, because it correlates your errors across rows. Grade each row as it comes.

### Do not

- Do not open `key_and_judge_verdicts.jsonl` until you are finished.
- Do not look up the underlying papers. Grade against supplied gold and evidence only — the systems did not have literature access either.
- Do not try to infer which system produced a response, or grade "generously" for ones that seem weaker.
- Do not leave cells blank. If genuinely undecidable, pick the closest label and explain in `human_notes`.
- Do not use a language model to help you grade. The entire value of this pass is that it is not a model.

---

## 6. Effort and pacing

120 rows at roughly 3–4 minutes each is 6–8 hours. Do it in blocks of about 30 rows with real breaks. Fatigue shows up in the data as drift toward the middle label, and this sheet is small enough that a tired final block would be visible in the results.

If you have less time than that, **grade fewer rows completely rather than all rows quickly** — the analysis handles a partial pass fine as long as you grade `H001` onward in order, since the sheet is pre-shuffled and any prefix is a valid stratified sample. Note where you stopped.

---

## 7. Quality control

**Two graders, full overlap, is the recommended design.** Both grade all 120 rows independently, without discussion, from separate copies of the sheet. This gives inter-annotator agreement, which is what tells us whether *humans* can even agree on these components — a number the paper currently cannot report, and which bounds how good any automatic scorer could be.

If only one grader is available, have them **re-grade a random 25 rows at least three days later**, in a shuffled order, to produce a self-consistency estimate comparable to the judge's.

**Adjudication.** Do not reconcile disagreements by discussion before the agreement statistics are computed — that destroys the measurement. Compute agreement first, then optionally adjudicate a merged gold set as a separate artifact.

---

## 8. What gets computed afterwards

Save the filled sheet as `grading_sheet_completed__<grader>.csv`, preserving `blind_id`. Then run:

```
python code/analyze_human_calibration.py release/human_calibration/grading_sheet_completed__<grader>.csv
```

which does all of the following and prints a report. Pass two filled sheets to also get inter-annotator agreement.

1. **Join** to `key_and_judge_verdicts.jsonl` on `blind_id`, and to `scores/per_item_scores.csv` on `record_id` for the two deterministic gates.
2. **Per-component agreement and Cohen's κ**, human vs. judge, for all seven graded components. `na` is a real category and is included, not dropped.
3. **Joint fidelity Φ under human grading.** Φ is a conjunction of five things:
   `answer_fidelity == correct` **and** `unsupported_claim == false` **and** `provenance_correct != no` **and** no preservation component (`contradiction`, `revision`, `scope`, `uncertainty`) equal to `no` **and** answerability correct.
   The first four come from your labels. **Answerability is not yours to grade** — it is read deterministically from the system's structured `answerability` field against the gold label, needs no human, and is taken from the released per-item scores. That is why the sheet has no answerability column. Compare the result against the judge's 13.7%.
4. **The compositional gap under human grading** — of the responses passing every component-style check, the share that nonetheless fail Φ. The component-pass set is: gold-source recall ≥ 0.5 (deterministic, from the per-item scores) **and** `unsupported_claim == false` **and** `answer_fidelity == correct` (both yours). Compare against 19.8%.
5. **The unsupported-claim false-positive check** — the rate at which the *judge* marked `unsupported_claim = true` on rows you marked `correct` fidelity with `unsupported_claim = false`. This is the direct test of the 44.2% figure.
6. **Inter-annotator agreement**, if two graders.

The comparisons that matter most, in order: (3) and (4) tell us whether the headline numbers move; (5) decides the fate of a gate; (2) tells future work which components need a human at all.

---

## 9. Reporting the result honestly

Two outcomes are both publishable and neither should be suppressed:

- **The judge is roughly calibrated.** Absolute levels stand, with the human pass as evidence.
- **The judge is not calibrated.** Then the paper's absolute levels are wrong and must be restated, and the comparative claims need re-examining under human labels wherever n allows.

The paper has already withdrawn one finding (item-level non-monotonicity) and downgraded another (the D4→D5 magnitude) when its own controls said so. This pass is held to the same standard. **Report what you find.**

---

## 10. Provenance of this sheet

Built by `code/make_human_subset.py` with seed `20260914`: 20 responses per diagnostic condition (D1–D6), spread across the eight capability categories and all five evaluated systems, drawn only from rows that were successfully judged in the main structured-format study. Composition as built — by condition: 20 each for closed book, retrieval-restricted, full history, gold source, gold memory state, gold evidence. By capability: temporal claim revision 18, hypothesis tracking 18, cross-paper synthesis 16, evidence provenance 15, contradiction resolution 15, entity/relation recall control 13, uncertainty abstention 13, method/condition constraints 12.

Rebuild or resize with `python code/make_human_subset.py` after changing `N_PER_CONDITION`.
