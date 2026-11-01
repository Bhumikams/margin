"""The RAG core: retrieve -> build grounded prompt -> generate -> attach citations."""
from __future__ import annotations

import json
import re

from .embeddings import Embedder
from .llm import LLM
from .store import VectorStore

ANSWER_SYSTEM = """You are a study assistant for an engineering student.
Answer ONLY using the numbered note excerpts provided. Rules:
- Cite every claim with the excerpt number in square brackets, e.g. [1] or [2][3].
- If the excerpts don't contain the answer, say exactly: "I couldn't find this in your notes."
  Then, on a new line, you may add a short general hint marked "(general knowledge, not from your notes)".
- Write for exam revision: clear headings or bullet points where they help, define key terms,
  and keep it concise unless the student asks for detail.
- Never invent page numbers or sources."""

QUIZ_SYSTEM = """You write exam practice questions strictly from the provided note excerpts.
Return JSON: {"questions": [{"question": str, "type": "mcq"|"short"|"long",
"options": [str] (only for mcq, 4 options), "answer": str, "source": int}]}
"source" is the excerpt number the question is based on. Mix types: mostly short and long
answer questions like a university theory exam, plus a few MCQs. Don't use outside knowledge."""

SUMMARY_SYSTEM = """You summarise study notes for quick revision.
Use only the excerpts given. Output markdown with: a 2-line overview, the key concepts as bullets
(term — one-line explanation), and a "Likely exam topics" list. Cite excerpts like [1]."""


def _label(c: dict) -> str:
    pages = (
        f"p.{c['page_start']}"
        if c["page_start"] == c["page_end"]
        else f"pp.{c['page_start']}-{c['page_end']}"
    )
    mod = f", Module {c['module']}" if c.get("module") else ""
    return f"{c['file_name']} ({c['subject']}{mod}, {pages})"


def format_context(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{i}] {_label(c)}\n{c['text']}" for i, c in enumerate(chunks, 1))


def sources_payload(chunks: list[dict]) -> list[dict]:
    return [
        {
            "n": i,
            "file_name": c["file_name"],
            "subject": c["subject"],
            "module": c.get("module"),
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "score": round(float(c.get("score", 0.0)), 4),
            "snippet": c["text"][:280] + ("…" if len(c["text"]) > 280 else ""),
        }
        for i, c in enumerate(chunks, 1)
    ]


def cited_numbers(answer: str, max_n: int) -> list[int]:
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return sorted(n for n in nums if 1 <= n <= max_n)


def parse_json(text: str) -> dict:
    """Tolerant JSON parse: strips code fences / leading prose some models add."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    return json.loads(text[start : end + 1])


class RAG:
    def __init__(self, store: VectorStore, embedder: Embedder, llm: LLM, top_k: int = 5):
        self.store = store
        self.embedder = embedder
        self.llm = llm
        self.top_k = top_k

    def retrieve(self, query: str, filters: dict | None = None, k: int | None = None):
        vec = self.embedder.embed([query])[0]
        return self.store.search(vec, k or self.top_k, filters)

    def ask(self, question: str, filters: dict | None = None, history: list[dict] | None = None):
        chunks = self.retrieve(question, filters)
        if not chunks:
            return {
                "answer": "I couldn't find anything in your notes yet. Upload notes for this "
                "subject first, or clear the subject/module filter.",
                "sources": [],
                "cited": [],
            }
        convo = ""
        if history:
            last = history[-6:]
            convo = "Earlier in this chat:\n" + "\n".join(
                f"{m['role']}: {m['content'][:500]}" for m in last
            ) + "\n\n"
        user = f"{convo}Note excerpts:\n\n{format_context(chunks)}\n\nQuestion: {question}"
        answer = self.llm.complete(ANSWER_SYSTEM, user)
        return {
            "answer": answer,
            "sources": sources_payload(chunks),
            "cited": cited_numbers(answer, len(chunks)),
        }

    def _topic_chunks(self, topic: str | None, filters: dict | None, k: int):
        if topic:
            return self.retrieve(topic, filters, k)
        return self.store.get_chunks(filters, limit=k)

    def quiz(self, topic: str | None, filters: dict | None, count: int = 5):
        chunks = self._topic_chunks(topic, filters, k=8)
        if not chunks:
            return {"questions": [], "sources": []}
        user = (
            f"Write {count} questions"
            + (f" about: {topic}" if topic else "")
            + f".\n\nNote excerpts:\n\n{format_context(chunks)}"
        )
        data = parse_json(self.llm.complete(QUIZ_SYSTEM, user, json_mode=True))
        questions = data.get("questions", [])[:count]
        return {"questions": questions, "sources": sources_payload(chunks)}

    def summarize(self, topic: str | None, filters: dict | None):
        chunks = self._topic_chunks(topic, filters, k=10)
        if not chunks:
            return {"summary": "No notes found for this selection.", "sources": []}
        user = (
            (f"Focus on: {topic}\n\n" if topic else "")
            + f"Note excerpts:\n\n{format_context(chunks)}"
        )
        return {
            "summary": self.llm.complete(SUMMARY_SYSTEM, user),
            "sources": sources_payload(chunks),
        }
