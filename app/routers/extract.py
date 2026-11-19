import time

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.cache import extraction_cache, make_key
from app.config import settings
from app.guardrails.input_guard import InputRejected, check_input
from app.guardrails.output_guard import OutputRejected, check_output
from app.schemas import ExtractRequest, ExtractResponse
from app.services.extractor import ExtractionError, extract_invoice
from app.services.pdf_text import pdf_to_text

router = APIRouter(prefix="/v1", tags=["extract"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------- shared logic: used by both endpoints ----------
async def run_pipeline(raw_text: str) -> ExtractResponse:
    start = time.perf_counter()

    # 1. input guardrails
    try:
        checked = check_input(raw_text)
    except InputRejected as e:
        raise HTTPException(422, {"code": e.code, "message": e.message})
    text = checked.text
    warnings = list(checked.warnings)

    # 2. response cache
    key = make_key(settings.active_model, text)
    hit = extraction_cache.get(key)
    if hit:
        return ExtractResponse(
            data=hit,
            model=settings.active_model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            cached=True,
        )

    # 3. model call + output guardrails
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

    # 4. cache only results that passed the output checks
    extraction_cache.set(key, data)
    return ExtractResponse(
        data=data,
        model=settings.active_model,
        latency_ms=int((time.perf_counter() - start) * 1000),
        usage=usage,
        warnings=warnings,
    )


# ---------- endpoint 1: plain text ----------
@router.post("/extract", response_model=ExtractResponse)
async def extract(req: ExtractRequest):
    return await run_pipeline(req.text)


# ---------- endpoint 2: PDF upload ----------
@router.post("/documents/extract", response_model=ExtractResponse)
async def extract_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(415, "Only PDF files are supported for now")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")

    try:
        text = pdf_to_text(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(400, "Could not read this PDF")

    if len(text) < 20:
        raise HTTPException(422, "No text found. This looks like a scanned PDF (OCR comes in phase 2).")

    return await run_pipeline(text)


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