"""PDF parsing and chunking.

Each chunk keeps the metadata needed for citations and filtering:
file name, page range, subject and module.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict

# Matches headings like "Module 2", "MODULE-3", "Module – 4", "Unit 5"
MODULE_RE = re.compile(r"\b(?:module|unit)\s*[-–:]?\s*(\d{1,2})\b", re.IGNORECASE)


@dataclass
class Page:
    number: int  # 1-based page number
    text: str


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    file_name: str
    subject: str
    module: str | None
    page_start: int
    page_end: int
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def file_hash(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def clean_text(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r"-\n(\w)", r"\1", text)  # words broken across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(data: bytes) -> list[Page]:
    """Extract text page by page with PyMuPDF."""
    import fitz  # PyMuPDF

    pages: list[Page] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            txt = clean_text(page.get_text("text"))
            if txt:
                pages.append(Page(number=i, text=txt))
    return pages


def parse_text(data: bytes) -> list[Page]:
    """Plain .txt / .md notes are treated as a single 'page'."""
    return [Page(number=1, text=clean_text(data.decode("utf-8", errors="ignore")))]


def detect_modules(pages: list[Page]) -> dict[int, str | None]:
    """Map page number -> module label, carrying the last seen heading forward.

    Only headings near the top of a page count, so a passing reference such as
    "as discussed in Module 1" in the middle of a page doesn't flip the module.
    """
    current: str | None = None
    result: dict[int, str | None] = {}
    for p in pages:
        head = p.text[:200]
        m = MODULE_RE.search(head)
        if m:
            current = m.group(1)
        result[p.number] = current
    return result


def chunk_pages(
    pages: list[Page],
    *,
    doc_id: str,
    file_name: str,
    subject: str,
    module: str | None = None,
    chunk_words: int = 350,
    overlap: int = 60,
) -> list[Chunk]:
    """Sliding word window across pages, remembering which page each word came from.

    If `module` is given it applies to every chunk; otherwise it's detected from
    "Module N" headings in the document.
    """
    if overlap >= chunk_words:
        raise ValueError("overlap must be smaller than chunk_words")

    module_by_page = {} if module else detect_modules(pages)

    words: list[tuple[str, int]] = []
    for p in pages:
        words.extend((w, p.number) for w in p.text.split())

    chunks: list[Chunk] = []
    step = chunk_words - overlap
    start = 0
    idx = 0
    while start < len(words):
        window = words[start : start + chunk_words]
        # Skip a tiny trailing window that is fully covered by the previous chunk
        if chunks and len(window) <= overlap:
            break
        text = " ".join(w for w, _ in window)
        p_start, p_end = window[0][1], window[-1][1]
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}:{idx}",
                doc_id=doc_id,
                file_name=file_name,
                subject=subject,
                module=module or module_by_page.get(p_start),
                page_start=p_start,
                page_end=p_end,
                text=text,
            )
        )
        idx += 1
        start += step
    return chunks
