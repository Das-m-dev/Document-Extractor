import fitz  # PyMuPDF

MAX_PAGES = 10

def pdf_to_text(data: bytes) -> str:
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.page_count > MAX_PAGES:
            raise ValueError(f"PDF has more than {MAX_PAGES} pages")
        return "\n".join(page.get_text() for page in doc).strip()