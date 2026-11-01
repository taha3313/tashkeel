# Rawi Ensemble FP32 integration

The default checkpoint is `TigreGotico/rawi-ensemble` at
`de3fca3a2f24cf7315a955ba09f73def025209d8`, file `rawi_ensemble.onnx`
(19,501,886 bytes). Upstream declares Apache-2.0; attribution, license and
SHA-256 provenance ship beside the model.

The integration uses original source characters for reconstruction, filters
predicted classes to ordinary harakat, and merges supplied marks after inference.
It does not restore hamzas or rewrite spelling. One ONNX CPU thread, disabled
CPU arena, serialized inference, existing 360-slot segmentation, and existing
text/document limits are retained. No new runtime packages or network calls.

## Validation

- 14 pytest tests pass: existing text/Word API roundtrip, split-run marks,
  tables/images/headers, rejection paths, model hashes, original Unicode
  characters (including emoji and decomposed hamza), supplied marks, model
  bounds and spelling preservation.
- The integrated adapter reproduced all 229 outputs of the isolated FP32
  reference runner exactly, including the frozen 180-paragraph SadeedDiac-25
  subset and 49 diagnostic examples. This is parity evidence, not an independent
  accuracy benchmark. Historical training/benchmark overlap remains possible.
- JavaScript syntax check and git diff whitespace checks pass.

Earlier isolated application measurements at 0.1 CPU with a 512 MiB/no-swap
limit peaked at 142.7 MiB RSS / 91.4 MiB cgroup memory. Corpus DER/WER were
3.52% / 12.68%, compared with 5.19% / 18.19% for the preceding libtashkeel
adapter on the same frozen 180 paragraphs and evaluator. The small difference
from Rawi INT8 (3.53% / 12.72%) is not a general quality guarantee; FP32 is slower.

The production Dockerfile uses a 180-second UV download timeout to tolerate
slow build networks. This does not change inference behavior or the memory plan.
