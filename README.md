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

The ONNX model and character maps come from [mush42/libtashkeel](https://github.com/mush42/libtashkeel), revision `9b91c2dbc3dc4085dc4f77a9e250e5dd095d7d0c`, under the bundled MIT license. See `app/assets/libtashkeel/PROVENANCE.json`. The Python adapter was extracted from Taha Chelly's Qafiya project. IBM Plex Sans Arabic and Amiri are bundled with their font licenses.

The public domain is https://tashkeel.tahachelly.com. Render service: https://tashkeel.onrender.com ([dashboard](https://dashboard.render.com/web/srv-dbjna4rbc2fs73db7v40)). Cloudflare Worker `tashkeel-proxy` supplies the public domain and TLS and streams requests to Render; all application code, file processing, and inference run on this separate Render service. Gateway source is in `cloudflare/worker.mjs`. Manual Render deploys are enabled; deploy only a tested commit.
