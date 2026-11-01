# Margin: study notes assistant, one small container (fits Render's free 512 MB tier)

# ---- 1. Build the React frontend ---------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. Python API + built frontend -------------------------------------------
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model at build time so the first request is fast
ENV EMBED_CACHE_DIR=/app/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/app/models')"

COPY backend/ ./backend
COPY --from=web /web/dist ./static

ENV STATIC_DIR=/app/static \
    VECTOR_STORE=atlas \
    READ_ONLY=true \
    PYTHONUNBUFFERED=1

RUN chown -R user:user /app
USER user
WORKDIR /app/backend

# Render (and most hosts) pass the port in $PORT
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-10000}"]
