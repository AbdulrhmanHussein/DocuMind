from pathlib import Path
from docx import Document
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def load_document(file_path: Path) -> list[dict]:
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {extension}")

    pages = []

    if extension == ".pdf":
        reader = PdfReader(str(file_path))

        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({
                    "text": text.strip(),
                    "page": page_number,
                })

    elif extension == ".docx":
        document = Document(str(file_path))
        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

        if text.strip():
            pages.append({"text": text.strip(), "page": None})

    else:
        text = file_path.read_text(encoding="utf-8-sig")

        if text.strip():
            pages.append({"text": text.strip(), "page": None})

    if not pages:
        raise ValueError(
            "No extractable text found. The file may be empty, "
            "or a scanned PDF may require OCR."
        )

    return pages