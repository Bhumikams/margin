# Margin: a study-notes assistant (RAG)

Ask questions about your own lecture notes and get answers that cite the exact page they came from.
Margin also writes exam-style practice questions and one-page revision sheets, built only from the notes you upload.

**Stack:** React (Vite) · FastAPI · MongoDB Atlas Vector Search · fastembed (ONNX) · Groq (GPT-OSS 120B), with Claude available as a drop-in alternative.

## Features

- **Grounded answers with citations.** Every claim carries a highlighted [n] mark. Hovering over it lights up the source excerpt in the margin, with file name and page range.
- **Scoped retrieval.** Pick a subject or a module, and the vector search pre-filters on that metadata, so answers about NoSQL never pull from your SAN notes.
- **Automatic module detection.** "Module 2" or "Unit 3" headings at the top of a page tag every chunk that starts there.
- **Practice mode.** Generates mixed short-answer, long-answer and MCQ questions, each linked back to its source page.
- **Revise mode.** Produces a one-page sheet with an overview, key terms and likely exam topics.
- **Retrieval evaluation.** `scripts/eval.py` reports Hit@k and MRR against a hand-labelled question set.
- **Pluggable LLM.** Set `LLM_PROVIDER=groq` or `claude` in `.env`; no code changes.
- **Duplicate-safe ingestion.** Uploads are content-hashed, so re-uploading the same file is a no-op.

## How it works

```
PDF ─► PyMuPDF (text per page) ─► 350-word chunks, 60-word overlap, page + module metadata
                                         │
                         all-MiniLM-L6-v2 embeddings via fastembed/ONNX (384-d, normalised)
                                         │
                       MongoDB Atlas  chunks  collection + vector index
                                         │
question ─► embed ─► $vectorSearch (filter: subject, module) ─► top-k excerpts
                                         │
          numbered excerpts + strict "answer only from these, cite [n]" prompt ─► Groq / Claude
                                         │
                  answer + sources + which sources were actually cited ─► React UI
```

## Run it locally

### 1. Get the free accounts

- **Groq API key:** sign up at console.groq.com, then create a key under API Keys.
- **MongoDB Atlas:** create a free M0 cluster at cloud.mongodb.com. Add a database user, allow your IP under Network Access, and copy the connection string.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in GROQ_API_KEY and MONGODB_URI
python -m scripts.create_index   # once: creates the Atlas vector index
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

The first start downloads the embedding model (about 90 MB), and it is cached after that. Embeddings run on ONNX Runtime, so there is no PyTorch install.

To try it without Atlas, set `VECTOR_STORE=memory` in `.env`. Everything works, but uploads are lost when the server restarts.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Vite proxies `/api` to the backend on port 8000. To point the frontend at a deployed backend, set `VITE_API_URL`.

### 4. Tests

```bash
cd backend && pytest -q
```

The tests use an in-memory store, a hash-based embedder and a fake LLM, so they run offline in about 2 seconds.

## Deploy for free (Render)

The repo includes a `Dockerfile` and a `render.yaml` blueprint. The container serves the API under `/api` and the built React app at `/`, and uses about 250 MB of RAM, so it fits Render's free tier.

1. Push this repo to GitHub. `.env` is git-ignored, so keys stay private.
2. On render.com, sign in with GitHub and choose **New > Blueprint**, then pick the repo.
3. Enter `GROQ_API_KEY` and `MONGODB_URI` when prompted, then click **Apply**.

The hosted app runs with `READ_ONLY=true`: visitors can ask, practise and revise, but can't upload or delete. Add notes from your local copy instead. Both use the same Atlas database, so new notes show up on the live site straight away.

Free instances sleep after 15 minutes without traffic, and the first visit after that takes about a minute.

## Measuring retrieval quality

1. Copy `backend/eval/questions.sample.json` to `eval/questions.json`.
2. Write 20 or more real questions from your notes, each with the file and page where the answer is.
3. Run:

```bash
python -m scripts.eval eval/questions.json --k 5
```

You get Hit@5 and MRR, plus the list of missed questions. Change `CHUNK_WORDS`, `CHUNK_OVERLAP` or `EMBED_MODEL` and re-run to compare. If you change the embedding model, also update `EMBED_DIM` and recreate the index.

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/upload` | multipart: `file`, `subject`, `module?` | pages, chunks, modules detected |
| POST | `/ask` | `question`, `subject?`, `module?`, `history?` | `answer`, `sources[]`, `cited[]` |
| POST | `/quiz` | `topic?`, `count`, `subject?`, `module?` | `questions[]`, `sources[]` |
| POST | `/summarize` | `topic?`, `subject?`, `module?` | `summary`, `sources[]` |
| GET | `/subjects` | | subjects with their modules |
| GET | `/documents` | | uploaded files |
| DELETE | `/documents/{id}` | | chunks removed |

Interactive docs are at `/docs` while the server is running.

## Project layout

```
backend/
  app/
    config.py       settings from .env
    ingest.py       PDF parsing, chunking, module detection
    embeddings.py   fastembed (ONNX) wrapper (+ test embedder)
    server.py       production entry: API at /api + built frontend at /
    store.py        AtlasStore ($vectorSearch) and MemoryStore
    llm.py          Groq / Claude behind one interface
    rag.py          retrieval, prompts, citation handling
    main.py         FastAPI routes
  scripts/          create_index.py, eval.py
  tests/            API and unit tests
frontend/
  src/
    App.jsx         layout, state, mode switching
    components/     Library, AskView, Answer, SourceMargin, PracticeView, ReviseView, UploadDialog
    styles.css      design tokens, light and dark themes
```

## Notes and limits

- Scanned PDFs have no text layer. Run them through OCR first, for example `ocrmypdf in.pdf out.pdf`.
- Groq's free tier is rate-limited. If you hit the limit, wait a minute, or switch `LLM_PROVIDER` to `claude`.
- Module detection only looks at the top of each page, so a passing mention like "see Module 1" mid-page doesn't re-tag it.
