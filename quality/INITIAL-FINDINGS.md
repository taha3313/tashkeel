# First accuracy iteration — 2 November 2026

This iteration builds the error/review workflow and proposes one narrow,
context-independent correction. Rawi remains the only model. No LLM calls,
training job or deployment is included.

## Error set

The frozen seed contains **162 cases**: 150 released-reference mismatches and
12 original grammar diagnostics (four failures, eight correct controls).
All labels are pending independent human Arabic review. Split sizes:
126 development, 17 validation, 19 test. The earlier 180-paragraph general
benchmark and 37-paragraph context set are excluded from the imported groups.

The initial longer-context Rawi baseline disagrees with the references at
1,177 letter positions: **510 word-ending positions** and **667 word-internal
positions**. Shadda differs at 128 positions and tanwin at 163; these overlap
the previous categories. Word ending is a spelling-position proxy, not a
morphological analysis of i'rab. This deliberately failure-enriched set is not
representative of public website accuracy.

Repeated bare words such as من, أن, علم, الله and أي have different reference
vocalizations depending on context. A blanket replacement dictionary would
therefore introduce errors. Ambiguous readings need review rather than
mechanical relabeling.

## Narrow correction: explicitly written إ

The source letter إ itself encodes hamza below. When the source supplies no
ordinary mark on it, predict kasra rather than allowing the model to leave it
bare or assign an incompatible vowel. Any supplied marks remain authoritative,
even if contradictory. This does not restore or change spelling, normalize
letters, or alter other hamza forms such as أ. The additional work is constant
per source character and adds no model, dependency, request or persistent data.

This rule was first inspected on development cases, then checked on validation
and the previously fixed general benchmark. The final held-out challenge test
was evaluated once after the rule was fixed.

| Set | Before → after incorrect positions | Improved / regressed cases |
| --- | --- | --- |
| Development, 126 | 930 → 901 | 23 / 0 |
| Validation, 17 | 105 → 105 | 0 / 0 |
| Held-out challenge test, 19 | 142 → 139 | 2 / 0 |
| All challenge cases, 162 | 1,177 → 1,145 | 25 / 0 |
| Earlier general sample, 180 paragraphs | 1,164 → 1,102 | 30 / 0 |

On the general sample, DER moved **3.406% → 3.224%**, and WER
**12.234% → 11.481%**. No source-character or supplied-mark violations were found.
These are local comparisons against existing references, with unknown training
contamination and reference-style uncertainty. They do not establish a universal
accuracy improvement or constitute independent Arabic review. General-set
comparison used the recorded 1,024-token baseline outputs, the same model hash,
and the exact post-processing rule; the full challenge run exercised the changed
application directly.

Reports are in `results/`. Their error-position details are retained so a reviewer
can audit gains rather than relying only on aggregate percentages. No changes
to case endings are attributed to this rule.

## What remains before fine-tuning

The CSV review/import workflow is ready; user examples can be added locally.
No seed example has been approved by an independent human reviewer. The exporter
therefore refuses to create a training file today. Released benchmark rows are
always excluded, even after review; validation/test rows and unapproved or
training-disallowed user examples are excluded too.

The pinned Rawi Ensemble repository provides ONNX graphs and vocabulary rather
than a resumable training checkpoint. A later training phase needs a compatible
trainable model, enough reviewed/appropriately sourced training text, and a
separate training environment. No fine-tuned model or accuracy result has been
invented. Review and expand the error set first; keep the evaluation groups fixed.
