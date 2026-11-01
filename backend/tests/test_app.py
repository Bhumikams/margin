"""End-to-end API tests with an in-memory store, a hash embedder and a fake LLM.
Run:  cd backend && pytest -q
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.embeddings import HashEmbedder
from app.ingest import Page, chunk_pages, detect_modules
from app.rag import RAG, cited_numbers, parse_json
from app.store import MemoryStore

NOTES = """Module 1
MongoDB is a document database that stores data as BSON documents inside collections.
Sharding distributes data across multiple machines using a shard key.

Module 2
The CAP theorem states that a distributed system can guarantee only two of
consistency, availability and partition tolerance at the same time.
Replica sets provide redundancy and high availability in MongoDB.
"""


class FakeLLM:
    name = "fake"

    def __init__(self):
        self.last_user = ""

    def complete(self, system, user, *, json_mode=False):
        self.last_user = user
        if json_mode:
            return "```json\n" + json.dumps(
                {
                    "questions": [
                        {"question": "State the CAP theorem.", "type": "short",
                         "answer": "Only two of C, A, P.", "source": 1}
                    ]
                }
            ) + "\n```"
        return "The CAP theorem says you get two of three guarantees [1]. See also [9]."


@pytest.fixture
def client():
    store, emb, llm = MemoryStore(), HashEmbedder(), FakeLLM()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_embedder] = lambda: emb
    main.app.dependency_overrides[main.get_rag] = lambda: RAG(store, emb, llm, top_k=3)
    c = TestClient(main.app)
    c.llm = llm
    yield c
    main.app.dependency_overrides.clear()


def upload(client, subject="NoSQL", module=None, text=NOTES, name="nosql.txt"):
    data = {"subject": subject}
    if module:
        data["module"] = module
    return client.post("/upload", files={"file": (name, text.encode(), "text/plain")}, data=data)


# ---- unit ----------------------------------------------------------------- #
def test_chunking_tracks_pages_and_overlap():
    pages = [Page(1, "a " * 300), Page(2, "b " * 300)]
    chunks = chunk_pages(pages, doc_id="d", file_name="f.pdf", subject="S",
                         chunk_words=200, overlap=50)
    assert chunks[0].page_start == 1 and chunks[0].page_end == 1
    assert any(c.page_start == 1 and c.page_end == 2 for c in chunks)
    assert chunks[-1].page_end == 2
    # overlap: consecutive chunks share 50 words
    assert chunks[0].text.split()[-50:] == chunks[1].text.split()[:50]


def test_module_detection_only_uses_page_top():
    pages = [Page(1, "Module 1 Intro"), Page(2, "body text " * 40 + " as in Module 7"),
             Page(3, "MODULE-3 Replication")]
    assert detect_modules(pages) == {1: "1", 2: "1", 3: "3"}


def test_cited_numbers_ignores_out_of_range():
    assert cited_numbers("x [1] y [2][2] z [9]", 3) == [1, 2]


def test_parse_json_strips_fences():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}


# ---- API ------------------------------------------------------------------ #
def test_upload_and_dedupe(client):
    r = upload(client)
    assert r.status_code == 200 and r.json()["status"] == "indexed"
    assert upload(client).json()["status"] == "already_indexed"
    assert client.get("/documents").json()[0]["file_name"] == "nosql.txt"


def test_pdf_upload_detects_pages_and_modules(client):
    import fitz

    doc = fitz.open()
    for text in ["Module 1\nDocument databases store JSON-like documents.",
                 "Module 2\nThe CAP theorem trades consistency and availability."]:
        doc.new_page().insert_text((72, 72), text)
    pdf = doc.tobytes()
    r = client.post("/upload", files={"file": ("notes.pdf", pdf, "application/pdf")},
                    data={"subject": "NoSQL"})
    body = r.json()
    assert body["pages"] == 2 and body["modules_detected"] == ["1"]  # one chunk starts on p.1
    src = client.post("/ask", json={"question": "CAP theorem"}).json()["sources"][0]
    assert src["page_start"] == 1 and src["page_end"] == 2


def test_upload_rejects_bad_type(client):
    r = client.post("/upload", files={"file": ("x.exe", b"zz")}, data={"subject": "S"})
    assert r.status_code == 415


def test_ask_returns_answer_sources_and_valid_citations(client):
    upload(client)
    r = client.post("/ask", json={"question": "What is the CAP theorem?"})
    body = r.json()
    assert r.status_code == 200
    assert body["cited"] == [1]  # [9] is out of range and dropped
    assert body["sources"][0]["file_name"] == "nosql.txt"
    assert "Note excerpts" in client.llm.last_user


def test_subject_filter_excludes_other_subjects(client):
    upload(client, subject="NoSQL")
    upload(client, subject="SAN", text="Fibre Channel zoning controls which hosts see which storage.",
           name="san.txt")
    r = client.post("/ask", json={"question": "zoning fibre channel", "subject": "NoSQL"})
    assert all(s["subject"] == "NoSQL" for s in r.json()["sources"])
    subjects = {s["subject"] for s in client.get("/subjects").json()}
    assert subjects == {"NoSQL", "SAN"}


def test_ask_with_no_notes(client):
    r = client.post("/ask", json={"question": "anything?"})
    assert r.json()["sources"] == []


def test_quiz_and_summary(client):
    upload(client)
    q = client.post("/quiz", json={"topic": "CAP", "count": 3}).json()
    assert q["questions"][0]["question"].startswith("State")
    s = client.post("/summarize", json={"subject": "NoSQL"}).json()
    assert s["sources"]


def test_read_only_blocks_upload_and_delete(client, monkeypatch):
    import dataclasses

    doc_id = upload(client).json()["doc_id"]
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, read_only=True))
    assert client.get("/health").json()["read_only"] is True
    assert upload(client, name="other.txt", text="new notes").status_code == 403
    assert client.delete(f"/documents/{doc_id}").status_code == 403
    assert client.post("/ask", json={"question": "CAP theorem"}).status_code == 200


def test_server_serves_api_and_frontend(client, tmp_path, monkeypatch):
    import importlib

    (tmp_path / "index.html").write_text("<title>Margin</title>")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    from app import server
    importlib.reload(server)
    c = TestClient(server.app)
    assert "Margin" in c.get("/").text
    assert c.get("/api/health").json()["status"] == "ok"


def test_delete_document(client):
    doc_id = upload(client).json()["doc_id"]
    assert client.delete(f"/documents/{doc_id}").json()["deleted_chunks"] > 0
    assert client.get("/documents").json() == []
    assert client.delete(f"/documents/{doc_id}").status_code == 404
