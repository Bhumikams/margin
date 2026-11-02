"""FastAPI app: upload notes, ask questions, generate quizzes and summaries."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .embeddings import Embedder, FastEmbedEmbedder
from .ingest import chunk_pages, file_hash, parse_pdf, parse_text
from .llm import build_llm
from .rag import RAG
from .store import AtlasStore, MemoryStore, VectorStore

log = logging.getLogger("study-notes")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Study Notes Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unexpected_error(request, exc: Exception):
    """Turn crashes into a readable JSON error instead of a bare 500 page."""
    from fastapi.responses import JSONResponse

    log.exception("Unhandled error on %s", request.url.path)
    message = f"{type(exc).__name__}: {exc}"[:300]
    return JSONResponse(status_code=500, content={"detail": f"Server error. {message}"})


# ---- dependencies (overridable in tests) ---------------------------------- #
@lru_cache
def get_store() -> VectorStore:
    if settings.vector_store == "memory":
        log.warning("Using in-memory vector store: data is lost on restart.")
        return MemoryStore()
    return AtlasStore(settings.mongodb_uri, settings.mongodb_db, settings.vector_index_name)


@lru_cache
def get_embedder() -> Embedder:
    return FastEmbedEmbedder(settings.embed_model, settings.embed_cache_dir)


@lru_cache
def get_rag() -> RAG:
    return RAG(get_store(), get_embedder(), build_llm(settings), settings.top_k)


# ---- schemas -------------------------------------------------------------- #
class Filters(BaseModel):
    subject: str | None = None
    module: str | None = None

    def as_dict(self) -> dict:
        return {"subject": self.subject, "module": self.module}


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(Filters):
    question: str = Field(min_length=2, max_length=2000)
    history: list[Message] = []


class QuizRequest(Filters):
    topic: str | None = None
    count: int = Field(default=5, ge=1, le=15)


class SummaryRequest(Filters):
    topic: str | None = None


# ---- routes --------------------------------------------------------------- #
@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "vector_store": settings.vector_store,
        "read_only": settings.read_only,
    }


def require_writable():
    if settings.read_only:
        raise HTTPException(403, "This is a read-only demo. Notes can only be changed by the owner.")


@app.post("/upload", dependencies=[Depends(require_writable)])
async def upload(
    file: UploadFile = File(...),
    subject: str = Form(...),
    module: str | None = Form(None),
    store: VectorStore = Depends(get_store),
    embedder: Embedder = Depends(get_embedder),
):
    name = file.filename or "notes"
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")

    subject = subject.strip()
    module = (module or "").strip() or None
    if not subject:
        raise HTTPException(422, "Subject is required")

    # Same file + same subject = same doc_id, so re-uploads are skipped
    doc_id = file_hash(data + subject.encode())[:16]
    if store.has_document(doc_id):
        return {"doc_id": doc_id, "status": "already_indexed", "file_name": name}

    lower = name.lower()
    if lower.endswith(".pdf"):
        pages = parse_pdf(data)
    elif lower.endswith((".txt", ".md")):
        pages = parse_text(data)
    else:
        raise HTTPException(415, "Upload a .pdf, .txt or .md file")

    if not pages:
        raise HTTPException(
            422,
            "No text found. If this is a scanned PDF, run OCR on it first "
            "(e.g. `ocrmypdf in.pdf out.pdf`).",
        )

    chunks = chunk_pages(
        pages,
        doc_id=doc_id,
        file_name=name,
        subject=subject,
        module=module,
        chunk_words=settings.chunk_words,
        overlap=settings.chunk_overlap,
    )
    vectors = embedder.embed([c.text for c in chunks])
    store.add(
        {
            "doc_id": doc_id,
            "file_name": name,
            "subject": subject,
            "module": module,
            "pages": len(pages),
            "chunks": len(chunks),
        },
        [c.to_dict() for c in chunks],
        vectors,
    )
    log.info("Indexed %s: %d pages, %d chunks", name, len(pages), len(chunks))
    return {
        "doc_id": doc_id,
        "status": "indexed",
        "file_name": name,
        "pages": len(pages),
        "chunks": len(chunks),
        "modules_detected": sorted({c.module for c in chunks if c.module}),
    }


@app.get("/documents")
def documents(store: VectorStore = Depends(get_store)):
    return store.list_documents()


@app.delete("/documents/{doc_id}", dependencies=[Depends(require_writable)])
def delete_document(doc_id: str, store: VectorStore = Depends(get_store)):
    removed = store.delete_document(doc_id)
    if not removed:
        raise HTTPException(404, "Document not found")
    return {"deleted_chunks": removed}


@app.get("/subjects")
def subjects(store: VectorStore = Depends(get_store)):
    return store.subjects()


def _run(fn):
    try:
        return fn()
    except RuntimeError as e:  # missing keys / config
        raise HTTPException(500, str(e)) from e
    except ValueError as e:  # bad model JSON etc.
        raise HTTPException(502, f"LLM returned an unexpected response: {e}") from e


@app.post("/ask")
def ask(req: AskRequest, rag: RAG = Depends(get_rag)):
    return _run(
        lambda: rag.ask(
            req.question, req.as_dict(), [m.model_dump() for m in req.history]
        )
    )


@app.post("/quiz")
def quiz(req: QuizRequest, rag: RAG = Depends(get_rag)):
    return _run(lambda: rag.quiz(req.topic, req.as_dict(), req.count))


@app.post("/summarize")
def summarize(req: SummaryRequest, rag: RAG = Depends(get_rag)):
    return _run(lambda: rag.summarize(req.topic, req.as_dict()))
