# Arabic quality follow-up — 2 November 2026

The best measured improvement in this follow-up is to retain more context in
Rawi, rather than replacing it or automatically correcting it with GLM.

The previous adapter split paragraphs at 360 source characters. The proposed
adapter allows up to 1,024 model input tokens, matching the actual NFD encoding
budget. It still splits at whitespace or punctuation when possible. Letters,
spacing, punctuation and supplied marks remain preserved; Word processing still
changes only text nodes. Longer context cannot resolve every ambiguous reading,
and short sentences receive no additional context from this change.

## Same-input comparisons

The scorer is unchanged from the earlier evaluation: NFC, ordinary-harakat
classes, order-insensitive shadda/vowels, and equivalent fathatan placements.
Missing or altered base text is counted separately; missing predictions do not
disappear from the denominator. Lower DER/WER is better.

| Pipeline | 180-paragraph DER | 180-paragraph WER |
| --- | --- | --- |
| Rawi FP32, existing 360-character chunks | 3.520% | 12.683% |
| Rawi FP32, up to 1,024 tokens | 3.406% | 12.234% |
| Khair B2 POS-aware diacritizer, ONNX, 360-character chunks | 10.247% | 30.889% |

All pipelines preserved source text on all 180 paragraphs. The 49 original
synthetic/poetry/partial-mark diagnostics also completed with source and supplied
marks preserved. Their aggregate DER was unchanged for Rawi because those
examples fit inside the previous window; they are not independent human gold.

A second set of **37 additional long paragraphs** was frozen before its
predictions. It excludes the original 180 rows, selects only inputs longer than
360 and no longer than 1,024 characters, and takes at most 20 deterministic
SHA-256-ranked rows per source. On that length-selected diagnostic, Rawi DER
fell from **3.643% to 3.144%**, and WER from **12.960% to 11.328%**. This specifically
tests context boundaries; it is not an estimate for arbitrary user text. No
checkpoint or threshold was tuned on these outputs. Historical model-training
or benchmark overlap remains possible. Individual readings may still regress.

Both samples use [SadeedDiac-25](https://huggingface.co/datasets/Misraj/SadeedDiac-25),
revision `aa311213e44e4cab6cc3f2848daacd753adc1ce1`, by Zeina Aldallal, Sara
Chrouf, Khalil Hennara, Mohamed Motaism Hamed, Muhammad Hreden and Safwan
AlModhayan, [Sadeed, 2025](https://arxiv.org/abs/2504.21635). Its CC BY-NC-SA 4.0
license applies to the external evaluation inputs, which are not bundled with
the application. The sample selection is balanced by source, not representative
of the benchmark's original proportions or of public website traffic.

## Alternative models and GLM

[Khair B2](https://github.com/qurancomp/khair-arabic-models), Apache-2.0,
commit `085a2e8c53325198327ebb787b986c9909134bbe`, adds predicted POS features to
a compact BiLSTM. Both source checkpoints matched their Git LFS SHA-256 hashes.
The POS model and diacritizer were exported locally to ONNX FP32; class labels
and POS tags matched the Torch reference on three different short inputs.
Both ONNX models together peaked at **105.6 MiB RSS** during the 229-input
quality run under a strict 512 MiB/no-swap limit. It fits but did not beat Rawi
on this external sample. This is a local export evaluation, not an upstream
quality claim or a tested replacement HTTP application.

The earlier same-sample comparison already evaluated CATT EO/ED, Nano, Ichkil,
Shakkala, Shakkelha, libtashkeel and other Rawi/BiLSTM variants. No verified
standalone replacement has beaten the current Rawi FP32 aggregate quality while
meeting the practical free-hosting constraints. This is not a claim that no
better model exists.

The GLM tests **were post-correction after Rawi**, not a separate first pass.
GLM-4.5-Flash with a revised prompt fixed two of four targeted bad Rawi sentences
and worsened two, taking 7.55 seconds. Its earlier 12-sentence request copied the
drafts unchanged and ignored the requested JSON field names. Thinking mode
returned no usable output before a 150-second timeout. GLM-4.7-Flash returned
HTTP 429 / provider code 1305 on the fresh follow-up, matching the earlier two
attempts. Its correction quality remains unmeasured. No user documents were sent
in these API probes. The temporary credential file was removed; no key is
included in source, fixtures, or artifacts.

## Runtime checks

All quality comparisons ran offline with one ONNX intra/inter-op thread,
sequential execution, and the CPU arena disabled. Docker enforced
`--memory 512m --memory-swap 512m`; quality used one CPU. The longer-context Rawi
quality run peaked at 102.6 MiB RSS. RSS is process memory, not total container
usage; shared pages and warm caches can affect the measurements.

A separate HTTP/Word probe uses the actual changed FastAPI application under
0.1 CPU and the same 512 MiB/no-swap limit. It passed a 20,000-character
request in 88.6 seconds and a Word document with supplied marks, formatting,
and an unchanged binary ZIP entry in 10.1 seconds. Peak process RSS was
170.3 MiB, peak cgroup memory 150.6 MiB, exit status 0, and OOMKilled was false. The benchmark artifacts record raw timings,
container peaks, exit status and whether Docker reported an OOM. These are local
checks, not live Render measurements or concurrency guarantees.

The unit suite passes **16 tests**, including the expanded model bound and
mixed Arabic/Latin/Hangul/emoji input whose NFD encoding crosses chunk boundaries.

Raw reports, evaluation scripts, frozen samples, hashes, Docker states and the
Khair ONNX export are retained locally in
`/home/taha/tashkeel-evaluations/2026-11-02-second-layer/`.
