import io
import time
import fitz  # PyMuPDF
import datetime as dt
from openpyxl import load_workbook
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

MAX_SHEETS = 5
MAX_ROWS = 500
MAX_COLS = 40


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return str(v).strip()


def xlsx_to_text(data: bytes) -> tuple[str, dict]:
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception:
        raise ValueError("Could not read this Excel file (only .xlsx is supported)")
    lines: list[str] = []
    rows_read = 0
    sheet_count = len(wb.worksheets)
    try:
        for ws in wb.worksheets[:MAX_SHEETS]:
            if hasattr(ws, "reset_dimensions"):
                ws.reset_dimensions()  # some tools write wrong sheet dimensions
            sheet_lines = []
            for row in ws.iter_rows(max_row=MAX_ROWS, max_col=MAX_COLS, values_only=True):
                cells = [_fmt(v) for v in row]
                if any(cells):
                    sheet_lines.append(" | ".join(c for c in cells if c))
            if sheet_lines:
                lines.append(f"[Sheet: {ws.title}]")
                lines.extend(sheet_lines)
                rows_read += len(sheet_lines)
    finally:
        wb.close()
    source = {"type": "xlsx", "sheets": sheet_count, "rows": rows_read}
    return "\n".join(lines), source