import asyncio
import base64
import io

import httpx
import pytesseract
from PIL import Image

from app.config import settings

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


class OCRError(Exception):
    pass


def _tesseract(png: bytes) -> str:
    img = Image.open(io.BytesIO(png))
    try:
        return pytesseract.image_to_string(img, lang=settings.ocr_langs)
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract not found. Install it or set TESSERACT_CMD in .env")
    except pytesseract.TesseractError as e:
        raise OCRError(f"Tesseract failed: {e}")


async def _vision(png: bytes) -> str:
    payload = {
        "model": settings.vision_model,
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {"temperature": 0, "num_ctx": settings.ollama_num_ctx},
        "messages": [{
            "role": "user",
            "content": (
                "Transcribe all text in this document image exactly as written, "
                "line by line, keeping numbers and symbols unchanged. Output the text only."
            ),
            "images": [base64.b64encode(png).decode()],
        }],
    }
    async with httpx.AsyncClient(timeout=settings.timeout) as client:
        r = await client.post(f"{settings.ollama_host}/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]


async def image_to_text(png: bytes) -> str:
    if settings.ocr_backend == "vision":
        return await _vision(png)
    return await asyncio.to_thread(_tesseract, png)  # blocking call, keep it off the event loop