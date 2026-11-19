import time

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.cache import extraction_cache, make_key
from app.config import settings
from app.guardrails.input_guard import InputRejected, check_input
from app.guardrails.output_guard import OutputRejected, check_output
from app.schemas import ExtractRequest, ExtractResponse
from app.services.document import image_file_to_text, pdf_to_text
from app.services.extractor import ExtractionError, extract_invoice
from app.services.ocr import OCRError

router = APIRouter(prefix="/v1", tags=["extract"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


# ---------- shared logic: used by both endpoints ----------
async def run_pipeline(raw_text: str, source: dict | None = None) -> ExtractResponse:
    start = time.perf_counter()
    source = source or {}

    try:
        checked = check_input(raw_text)
    except InputRejected as e:
        raise HTTPException(422, {"code": e.code, "message": e.message})
    text = checked.text
    warnings = list(checked.warnings)

    key = make_key(settings.active_model, text)
    hit = extraction_cache.get(key)
    if hit:
        return ExtractResponse(
            data=hit,
            model=settings.active_model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            cached=True,
            source=source,
        )

    try:
        data, usage = await extract_invoice(text)
        warnings += check_output(data, text)
    except OutputRejected as e:
        raise HTTPException(502, {"code": "output_guardrail", "message": str(e)})
    except httpx.ConnectError:
        raise HTTPException(503, "LLM backend (Ollama) is not reachable")
    except httpx.TimeoutException:
        raise HTTPException(504, "LLM backend timed out")
    except ExtractionError as e:
        raise HTTPException(502, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Ollama error {e.response.status_code}: {e.response.text}")

    extraction_cache.set(key, data)
    return ExtractResponse(
        data=data,
        model=settings.active_model,
        latency_ms=int((time.perf_counter() - start) * 1000),
        usage=usage,
        warnings=warnings,
        source=source,
    )


# ---------- endpoint 1: plain text ----------
@router.post("/extract", response_model=ExtractResponse)
async def extract(req: ExtractRequest):
    return await run_pipeline(req.text)


# ---------- endpoint 2: PDF or image upload ----------
@router.post("/documents/extract", response_model=ExtractResponse)
async def extract_document(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Supported types: PDF, PNG, JPEG, WebP")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")

    try:
        if file.content_type == "application/pdf":
            text, source = await pdf_to_text(data)
        else:
            text, source = await image_file_to_text(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except OCRError as e:
        raise HTTPException(503, f"OCR unavailable: {e}")
    except httpx.HTTPError:
        raise HTTPException(503, "Vision OCR failed: Ollama is not reachable or timed out")
    except Exception:
        raise HTTPException(400, "Could not read this file")

    if len(text) < 20:
        raise HTTPException(422, "No readable text found in the document")

    if source.get("ocr_pages"):
        source["ocr_backend"] = settings.ocr_backend
    return await run_pipeline(text, source)


# ---------- cache stats ----------
@router.get("/cache/stats")
def cache_stats():
    c = extraction_cache
    total = c.hits + c.misses
    return {
        "hits": c.hits,
        "misses": c.misses,
        "hit_rate": round(c.hits / total, 2) if total else 0,
        "size": len(c._store),
    }