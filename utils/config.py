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

# ── OpenRouter / LLMs ──────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv(
    "OPENROUTER_API_KEY",
    "",
)
OPENROUTER_BASE_URL: str = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
OPENROUTER_MODEL: str = os.getenv(
    "OPENROUTER_MODEL",
    "xiaomi/mimo-v2-pro",
)
OPENROUTER_FALLBACK_MODEL: str = os.getenv(
    "OPENROUTER_FALLBACK_MODEL",
    "google/gemma-4-31b-it:free",
)
OPENROUTER_VISION_MODEL: str = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "google/gemma-4-31b-it:free",
)
OPENROUTER_MAX_RETRIES: int = int(
    os.getenv("OPENROUTER_MAX_RETRIES", "3")
)
OPENROUTER_RETRY_DELAY: float = float(
    os.getenv("OPENROUTER_RETRY_DELAY", "2.0")
)
OPENROUTER_APP_NAME: str = os.getenv(
    "OPENROUTER_APP_NAME", "competitor-intelligence-engine"
)
OPENROUTER_HTTP_REFERER: str = os.getenv("OPENROUTER_HTTP_REFERER", "")


# ── HuggingFace ───────────────────────────────────────────────────────────────
HF_API_KEY: str = os.getenv("HF_API_KEY", "")

# ── Tavily Search ─────────────────────────────────────────────────────────────
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

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
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "8"))
CRAWL_TIMEOUT_MS: int = int(os.getenv("CRAWL_TIMEOUT_MS", "30000"))
SCROLL_PAUSE_MS: int = int(os.getenv("SCROLL_PAUSE_MS", "1000"))
MAX_SCROLLS: int = int(os.getenv("MAX_SCROLLS", "3"))
CRAWL_DELAY_MIN_SECS: float = float(os.getenv("CRAWL_DELAY_MIN_SECS", "2.5"))
CRAWL_DELAY_MAX_SECS: float = float(os.getenv("CRAWL_DELAY_MAX_SECS", "4.0"))
CRAWL_429_DOMAIN_THRESHOLD: int = int(os.getenv("CRAWL_429_DOMAIN_THRESHOLD", "3"))

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
TAVILY_SEARCH_DEPTH: str = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
COMPETITOR_CRAWL_DELAY: float = float(os.getenv("COMPETITOR_CRAWL_DELAY", "2.0"))
COMPETITOR_CRAWL_CONCURRENCY: int = int(
    os.getenv("COMPETITOR_CRAWL_CONCURRENCY", "1")
)

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'competitor_intel.db'}"
)

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
