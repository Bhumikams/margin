"""Central configuration, read from environment variables (.env supported)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM ---------------------------------------------------------------
    # "groq" (default, free tier) or "claude" (paid, needs ANTHROPIC_API_KEY)
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq").lower()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    # gpt-oss models think before answering; "low" keeps responses fast
    groq_reasoning_effort: str = os.getenv("GROQ_REASONING_EFFORT", "low")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # --- Embeddings ----------------------------------------------------------
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embed_dim: int = _int("EMBED_DIM", 384)
    embed_cache_dir: str | None = os.getenv("EMBED_CACHE_DIR") or None

    # --- Vector store ------------------------------------------------------
    # "atlas" (MongoDB Atlas Vector Search) or "memory" (in-process, for demos/tests)
    vector_store: str = os.getenv("VECTOR_STORE", "atlas").lower()
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_db: str = os.getenv("MONGODB_DB", "study_notes")
    vector_index_name: str = os.getenv("VECTOR_INDEX_NAME", "vector_index")

    # --- Chunking & retrieval ----------------------------------------------
    chunk_words: int = _int("CHUNK_WORDS", 350)
    chunk_overlap: int = _int("CHUNK_OVERLAP", 60)
    top_k: int = _int("TOP_K", 5)

    # --- API ---------------------------------------------------------------
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 25)
    # Public demo mode: visitors can ask, quiz and revise, but not upload or delete
    read_only: bool = os.getenv("READ_ONLY", "false").lower() in ("1", "true", "yes")


settings = Settings()
