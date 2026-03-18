<<<<<<< HEAD
"""
Central configuration for the Competitor Intelligence Engine.

All settings are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path


# ── Project Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
REPORTS_DIR = DATA_DIR / "reports"
FAISS_DIR = DATA_DIR / "faiss"

# Ensure directories exist
for _dir in [DATA_DIR, SCREENSHOTS_DIR, REPORTS_DIR, FAISS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ── Groq / Llama ───────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "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")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL: str = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "3"))
GROQ_RETRY_DELAY: float = float(os.getenv("GROQ_RETRY_DELAY", "2.0"))

# ── Crawler ────────────────────────────────────────────────────────────────────
MAX_CRAWL_DEPTH: int = int(os.getenv("MAX_CRAWL_DEPTH", "2"))
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "15"))
CRAWL_TIMEOUT_MS: int = int(os.getenv("CRAWL_TIMEOUT_MS", "30000"))
SCROLL_PAUSE_MS: int = int(os.getenv("SCROLL_PAUSE_MS", "1000"))
MAX_SCROLLS: int = int(os.getenv("MAX_SCROLLS", "3"))

# ── Text Processing ───────────────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
MIN_CHUNK_SIZE: int = int(os.getenv("MIN_CHUNK_SIZE", "100"))

# ── Embeddings ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# ── Competitor Discovery ───────────────────────────────────────────────────────
MAX_COMPETITORS: int = int(os.getenv("MAX_COMPETITORS", "5"))
MAX_COMPETITOR_CANDIDATES = int(os.getenv("MAX_COMPETITOR_CANDIDATES", "15"))
MIN_SIMILARITY_THRESHOLD = float(os.getenv("MIN_SIMILARITY_THRESHOLD", "0.25"))

# Per-scope limits for local vs global competitor discovery
MAX_LOCAL_COMPETITORS = int(os.getenv("MAX_LOCAL_COMPETITORS", "5"))
MAX_GLOBAL_COMPETITORS = int(os.getenv("MAX_GLOBAL_COMPETITORS", "5"))
MAX_LOCAL_CANDIDATES = int(os.getenv("MAX_LOCAL_CANDIDATES", "7"))
MAX_GLOBAL_CANDIDATES = int(os.getenv("MAX_GLOBAL_CANDIDATES", "7"))
MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "15"))
SEARCH_RATE_LIMIT_DELAY: float = float(os.getenv("SEARCH_RATE_LIMIT_DELAY", "5.0"))
COMPETITOR_CRAWL_DELAY: float = float(os.getenv("COMPETITOR_CRAWL_DELAY", "2.0"))

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'competitor_intel.db'}")

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
=======
"""
Central configuration for the Competitor Intelligence Engine.

All settings are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ── Project Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
REPORTS_DIR = DATA_DIR / "reports"
FAISS_DIR = DATA_DIR / "faiss"

# Ensure directories exist
for _dir in [DATA_DIR, SCREENSHOTS_DIR, REPORTS_DIR, FAISS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ── Groq / Llama ───────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "meta-llama/llama-3.1-8b-instruct")
GROQ_FALLBACK_MODEL: str = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")
GROQ_VISION_MODEL: str = os.getenv(
    "GROQ_VISION_MODEL", "meta-llama/llama-3.2-11b-vision-preview"
)
GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "3"))
GROQ_RETRY_DELAY: float = float(os.getenv("GROQ_RETRY_DELAY", "2.0"))

# ── HuggingFace ───────────────────────────────────────────────────────────────
HF_API_KEY: str = os.getenv("HF_API_KEY", "")

# ── Pinecone ───────────────────────────────────────────────────────────────────
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "competitor-intel")

# ── Jina Embeddings ───────────────────────────────────────────────────────────
JINA_API_KEY: str = os.getenv("JINA_API_KEY", "")
JINA_EMBEDDING_MODEL: str = os.getenv(
    "JINA_EMBEDDING_MODEL", "jina-embeddings-v5-text-small"
)

# ── Crawler ────────────────────────────────────────────────────────────────────
MAX_CRAWL_DEPTH: int = int(os.getenv("MAX_CRAWL_DEPTH", "2"))
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "15"))
CRAWL_TIMEOUT_MS: int = int(os.getenv("CRAWL_TIMEOUT_MS", "30000"))
SCROLL_PAUSE_MS: int = int(os.getenv("SCROLL_PAUSE_MS", "1000"))
MAX_SCROLLS: int = int(os.getenv("MAX_SCROLLS", "3"))

# ── Text Processing ───────────────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
MIN_CHUNK_SIZE: int = int(os.getenv("MIN_CHUNK_SIZE", "100"))

# ── Embeddings ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = JINA_EMBEDDING_MODEL  # Use Jina by default
# Dimension will be detected at runtime from Jina API for v5 models
EMBEDDING_DIMENSION: int = 1024  # Default for jina-embeddings-v5-text-small

# ── Competitor Discovery ───────────────────────────────────────────────────────
MAX_COMPETITORS: int = int(os.getenv("MAX_COMPETITORS", "5"))
MAX_COMPETITOR_CANDIDATES = int(os.getenv("MAX_COMPETITOR_CANDIDATES", "15"))
MIN_SIMILARITY_THRESHOLD = float(os.getenv("MIN_SIMILARITY_THRESHOLD", "0.25"))

# Per-scope limits for local vs global competitor discovery
MAX_LOCAL_COMPETITORS = int(os.getenv("MAX_LOCAL_COMPETITORS", "5"))
MAX_GLOBAL_COMPETITORS = int(os.getenv("MAX_GLOBAL_COMPETITORS", "5"))
MAX_LOCAL_CANDIDATES = int(os.getenv("MAX_LOCAL_CANDIDATES", "7"))
MAX_GLOBAL_CANDIDATES = int(os.getenv("MAX_GLOBAL_CANDIDATES", "7"))
MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "15"))
SEARCH_RATE_LIMIT_DELAY: float = float(os.getenv("SEARCH_RATE_LIMIT_DELAY", "5.0"))
COMPETITOR_CRAWL_DELAY: float = float(os.getenv("COMPETITOR_CRAWL_DELAY", "2.0"))

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'competitor_intel.db'}"
)

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
>>>>>>> c8b6483 (updated the report and fixed bugs)
