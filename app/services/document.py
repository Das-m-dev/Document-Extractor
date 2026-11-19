import io
import time

import fitz  # PyMuPDF
from PIL import Image

from app.config import settings
from app.services.ocr import image_to_text

MAX_PAGES = 10
MIN_PAGE_CHARS = 20   # a page with less text than this is treated as scanned


async def pdf_to_text(data: bytes) -> tuple[str, dict]:
    parts: list[str] = []
    ocr_pages = 0
    ocr_ms = 0
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.page_count > MAX_PAGES:
            raise ValueError(f"PDF has more than {MAX_PAGES} pages")
        for page in doc:
            text = page.get_text().strip()
            if len(text) < MIN_PAGE_CHARS:
                png = page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")
                t0 = time.perf_counter()
                text = (await image_to_text(png)).strip()
                ocr_ms += int((time.perf_counter() - t0) * 1000)
                ocr_pages += 1
            parts.append(text)
    source = {"type": "pdf", "pages": len(parts), "ocr_pages": ocr_pages, "ocr_ms": ocr_ms}
    return "\n".join(parts).strip(), source


async def image_file_to_text(data: bytes) -> tuple[str, dict]:
    img = Image.open(io.BytesIO(data)).convert("RGB")   # raises if the file is not an image
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    t0 = time.perf_counter()
    text = (await image_to_text(buf.getvalue())).strip()
    source = {"type": "image", "pages": 1, "ocr_pages": 1,
              "ocr_ms": int((time.perf_counter() - t0) * 1000)}
    return text, source