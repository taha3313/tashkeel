# Tashkeel | تشكيل

A standalone Arabic vocalization tool by Taha Chelly. Paste Arabic text, or upload a Word `.docx` and download a vocalized copy. Runs its own bundled CPU ONNX model, with no Gemini account or connection to Qafiya required.

- Arabic RTL writing desk with Amiri manuscript typography, paired original/result editors on desktop, stacked mobile editors, loading and error states, editable results, copy and text download.
- Word upload supports the file picker and drag and drop.
- Word files retain run formatting, tables, images, hyperlinks, sections, headers, and footers. Footnote and endnote text is processed too. Text inside embedded objects and images is not recognized.
- Up to 20,000 text characters; `.docx` files up to 5 MB (30 MB expanded). Old `.doc` files must first be saved as `.docx` in Word.
- Existing vowel marks are respected. Longer passages are split at whitespace or punctuation; context across chunks is limited.
- Automatic diacritization can be wrong, especially names and grammatical endings. Review outputs.
- Files are processed in memory after the HTTP upload and are not retained by application code. Input/output text is not logged or cached. Hosting infrastructure may retain ordinary request metadata.
- One inference job at a time; concurrent requests receive a retry message.

## Run

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
uv run pytest
```

Docker: `docker build -t tashkeel .` then `docker run --rm -p 8000:8000 tashkeel`.

## Deploy

Dedicated Render Docker web service, Frankfurt, one worker. Startup binds `0.0.0.0:$PORT`; `/health` reports readiness after model initialization. The free plan can sleep when inactive. No API keys, database, or persistent disk are needed.

## Model provenance

The bundled model is [TigreGotico/Rawi Ensemble](https://huggingface.co/TigreGotico/rawi-ensemble), **FP32**, revision `de3fca3a2f24cf7315a955ba09f73def025209d8`, declared Apache-2.0 upstream. It combines Rawi V2 and V3 in one ONNX graph. Credit: TigreGotico; Mike Hansen provided training compute. License, attribution, exact artifact hashes and provenance are bundled in `app/assets/rawi-ensemble/`.

The adapter uses Rawi's NFD character vocabulary for inference and applies only ordinary harakat to the original source characters. Predicted hamza/spelling restoration and dagger alef are excluded; supplied marks, whitespace, digits, symbols and non-Arabic text are retained. Supplied marks are merged after prediction, not passed as model hints. Inference remains serialized with one CPU thread and bounded chunks. No network, API key, PyTorch or GPU dependency is needed.

Isolated validation on 180 released-reference paragraphs measured 3.52% DER / 12.68% WER, versus 5.19% / 18.19% for the previous libtashkeel adapter. These are sample-specific results with benchmark-overlap uncertainty. FP32's gain over INT8 was small and it was slower at 0.1 CPU. A local application probe peaked around 143 MiB process RSS under a 512 MiB/no-swap cap; this is not a guarantee for every hosting workload. See `docs/model-validation.md` for the integration checks. IBM Plex Sans Arabic and Amiri retain their bundled font licenses.

The public domain is https://tashkeel.tahachelly.com. Render service: https://tashkeel.onrender.com ([dashboard](https://dashboard.render.com/web/srv-dbjna4rbc2fs73db7v40)). Cloudflare Worker `tashkeel-proxy` supplies the public domain and TLS and streams requests to Render; all application code, file processing, and inference run on this separate Render service. Gateway source is in `cloudflare/worker.mjs`. Manual Render deploys are enabled; deploy only a tested commit.
