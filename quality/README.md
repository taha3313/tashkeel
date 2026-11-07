# Arabic quality workflow

This is an offline development workflow. The website does not log user text or
upload examples to an LLM. Rawi remains the only inference model.

## Frozen first error set

`cases.jsonl` has **162 cases**: 150 published-reference Rawi mismatches, four
short grammar failures and eight correctly handled controls. All reference
labels start **pending review**. Published labels and assistant-authored labels
are not represented as independent human-approved corrections.

Splits are **126 development / 17 validation / 19 test**. The hash of normalized
bare text fixes its split before inference. Exact whitespace/diacritic variants
cannot cross splits. The 217 text groups used in the earlier general and context
benchmarks are excluded from the imported rows. Near-duplicate passages and
unknown model-training overlap remain limitations.

The dataset is deliberately enriched for failures. Its aggregate error rate is
not a population accuracy estimate. Keep `cases.jsonl` fixed while developing a
correction; use development cases for hypotheses, validation for selection, and
test only after the candidate is fixed. Do not mine the test reports for rules.
Correct controls protect already-correct outputs. See [attribution](ATTRIBUTION.md)
for the public reference subset's separate noncommercial license.

## Run a comparison

```bash
uv run python tools/arabic_quality.py evaluate \
  --cases quality/cases.jsonl --split validation \
  --output /tmp/arabic-quality.json --check
```

Without `--predictions`, this runs the current local application. An alternative
candidate can supply JSONL containing `id` and `output` with `--predictions`.
Missing predictions count as errors. `--check` fails on any per-case regression,
missing output, changed source characters, lost supplied marks or invalid marks;
a lower aggregate DER cannot hide one sentence getting worse.

Reports include total DER/WER, word-internal DER, a **word-ending proxy** (not a
morphological i'rab analysis), shadda/tanwin disagreements, per-case outcomes and
exact error positions. Vowel/shadda order and conventional fathatan placement
are normalized for scoring. Source-preservation checks remain exact and do not
permit spelling or Unicode-character rewriting. Pending references are scored
with their status visible; `ambiguous` and `rejected` cases are excluded.

## Review Arabic labels

```bash
mkdir -p quality/local
uv run python tools/arabic_quality.py review-csv \
  --cases quality/cases.jsonl --output quality/local/review.csv
uv run python tools/arabic_quality.py apply-review \
  --cases quality/cases.jsonl --csv quality/local/review.csv \
  --output quality/local/reviewed.jsonl
```

A reviewer edits `expected`, sets `status` to `approved`, `rejected`, `ambiguous`,
or `pending`, and provides a name for reviewed decisions. Use `ambiguous` when
multiple readings remain plausible. The importer preserves the original
reference and notes, rejects changes to source/baseline/split, and does not turn
published evaluation data into training data. Re-run comparisons with the
reviewed file. CI never claims the references have received human review.

## Add a real failure without collecting website text

Save a local JSON object with `input`, corrected `expected`, `categories`,
`source` (including `kind: user_example` or `original_example` and provenance),
and an explicit `training_allowed` boolean. Then:

```bash
uv run python tools/arabic_quality.py add \
  --cases quality/local/reviewed.jsonl --example quality/local/example.json \
  --output quality/local/with-example.jsonl
```

The current app produces its baseline locally. The example starts pending,
keeps the deterministic split, and is never uploaded. Its expected text must
preserve the original letters and supplied marks. Do not add private text to
tracked `quality/cases.jsonl`.

## Export for later fine-tuning

```bash
uv run python tools/arabic_quality.py export-training \
  --cases quality/local/reviewed.jsonl --output quality/local/training.jsonl
```

Only named-reviewer-approved, explicitly training-allowed **development** cases
from non-benchmark sources are exported. Validation/test and all published
benchmark rows are excluded. The current seed set produces **no training
export** because none of its original examples has received human approval.
This is intentional: fitting on evaluation labels would invalidate the quality
comparison. A small error set alone is not enough to train a replacement model.

The public Rawi Ensemble snapshot exposes ONNX inference graphs and vocabulary,
not a resumable training checkpoint. Actual fine-tuning therefore needs a
compatible trainable checkpoint/pipeline and a sufficiently large, appropriately
sourced training corpus. Keep that separate from the held-out tests. Neither a
new model nor a fine-tuning accuracy claim is part of this change.

## Rebuild a new dataset version

Use the cached Hugging Face rows response (JSON array of `row_idx`/`row` items)
and record its fingerprint. Initial dataset construction used the application
at `c237519`; the model and source hashes are frozen in the manifest. Rebuilding
under another model or rule produces a new challenge-set version, not the same
baseline. Do not rebuild automatically while tuning.

```bash
uv run python tools/arabic_quality.py build \
  --source quality/local/sadeed-rows.json \
  --revision aa311213e44e4cab6cc3f2848daacd753adc1ce1 \
  --exclude-groups quality/excluded-groups.json \
  --seed quality/diagnostics.json --output quality/local/new-cases.jsonl
```
