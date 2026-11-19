# document-extractor

Extracts structured fields from invoices. Input can be a PDF, a scanned PDF, an image or an `.xlsx` file. Output is JSON, an editable review page, and XLSX/CSV export. FastAPI and Ollama, everything runs locally so documents stay on the machine.

Fields: vendor, invoice number, date, currency, subtotal, tax, total, line items, and the Japanese registration number (`T` + 13 digits) if present. Missing fields are `null`.

## How it works

The LLM does the extraction in every case. The input type only decides how the text is obtained:

| Input | Text source |
|---|---|
| PDF with text layer | PyMuPDF |
| Scanned PDF, PNG, JPEG, WebP | OCR: Tesseract (default) or an Ollama vision model (`OCR_BACKEND=vision`) |
| `.xlsx` | openpyxl reads cell values, sheets are flattened to text |

Then: input checks, cache lookup, Ollama (JSON schema passed as `format`, temperature 0), pydantic validation with retry, output checks, cache write.

## Run

```
ollama pull gemma2:9b
python -m venv .venv
.venv\Scripts\Activate.ps1      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Review page at `http://localhost:8000/`, Swagger at `/docs`. The first request is slow while Ollama loads the model.

OCR needs Tesseract with the `eng` and `jpn` language data (on Windows, the UB Mannheim build). If it is not on PATH, set `TESSERACT_CMD` in `.env`. For the vision backend, pull a vision model and set `VISION_MODEL`.

## API

```
POST /v1/extract             {"text": "..."}
POST /v1/documents/extract   multipart "file": pdf, png, jpg, webp, xlsx (max 10 MB, 10 pages)
POST /v1/export/xlsx         Invoice JSON in, .xlsx out
POST /v1/export/csv          Invoice JSON in, .csv out (one row per line item, UTF-8 with BOM)
GET  /v1/cache/stats
GET  /health
```

The extract endpoints return `data`, `model`, `latency_ms`, `cached`, `usage`, `warnings` and `source` (page count, OCR pages and time). Status codes: 422 rejected input or no readable text, 413/415 bad upload, 502 output failed validation, 503 Ollama or OCR unavailable, 504 timeout.

Review page: upload a file, correct the extracted fields and line items, export. Values are written to the DOM with `textContent`/`.value` only, and exports never write extracted strings as formulas.

## Checks

- Input: 10 to 20000 characters, regex list for injection phrases. OCR output goes through the same checks.
- Output, rejected: currency not in whitelist, date not `YYYY-MM-DD`, bad registration number, instruction text in fields.
- Output, warning only: line items vs subtotal (or total) mismatch, subtotal + tax vs total mismatch, vendor or invoice number not found in the source text.
- Results are cached only after the output checks pass. Cache key is prompt version + model + text.

## Config

Set in `.env`, defaults in `app/config.py`: `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_KEEP_ALIVE`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ITEMS`, `TIMEOUT`, `MAX_RETRIES`, `OCR_BACKEND` (`tesseract` or `vision`), `OCR_LANGS`, `OCR_DPI`, `TESSERACT_CMD`, `VISION_MODEL`. `--reload` does not pick up `.env` changes.

Tracing is optional: set `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Trace inputs are uploaded, so set `LANGSMITH_HIDE_INPUTS=true` for real documents.

## Other

```
pytest                           # LLM mocked
python -m scripts.profile_cost   # tokens and projected cost per 1000 requests, needs tiktoken
```

`scripts/` also has generators for sample files (text PDF, scanned PDF, xlsx). Test files should be synthetic.

## Layout

```
app/
  main.py  config.py  schemas.py  prompts.py  cache.py
  routers/extract.py  routers/export.py
  services/extractor.py  services/document.py  services/ocr.py
  guardrails/input_guard.py  guardrails/output_guard.py
  static/index.html
scripts/
tests/
```

Known gaps: only `.xlsx` is read (not `.xls` or `.xlsm`); formula cells that were never calculated by Excel have no cached value and come out empty; no authentication on the UI or API; the cache is per process and in memory; accuracy has not been measured, and OCR has only been tried on clean rendered samples.
