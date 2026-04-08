# AI-Powered Competitor Intelligence Engine

## Project Overview

This project provides automated competitive intelligence analysis for any website. It extracts structured business profiles, discovers relevant competitors, compares them, and generates customer-facing PDF reports.

### What It Does

1. **Analyze any website** - Crawls and extracts structured business information
2. **Find competitors** - Discovers local competitors via Tracxn + Tavily and global competitors via Tavily + LLM validation
3. **Compare brands** - Performs detailed comparative analysis of market positioning
4. **Generate reports** - Creates customer-facing PDF reports with strategic recommendations

### Report Output

The current PDF report includes:

- Executive summary
- Business profile
- Visual brand analysis
- Local competitors
- Global competitors
- Competitor deep profiles
- Side-by-side comparison
- Strategic threat assessment
- White space opportunities
- Strategic recommendations

The PDF report intentionally excludes:

- Website structural analysis
- CTA aggressiveness
- Tech stack

---

## Architecture and Data Flow

```
URL Input
    |
    v
+---------------------+
|  Web Crawler        |  Playwright + BeautifulSoup
|  (Adaptive BFS)     |  - Crawls up to 8 pages by default
|                     |  - Renders JavaScript
|                     |  - Captures screenshots
|                     |  - Retry with exponential backoff
+---------------------+
    |
    v
+---------------------+
|  Text Processing    |  Clean, chunk, analyze DOM
|  - Remove boilerplate  |  - LangChain splitter
|  - DOM extraction   |  - HuggingFace tokenizer
|  - Text chunking    |
+---------------------+
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
+------------+  +---------------+  +--------------+
| Visual     |  | Business      |  | Embeddings  |
| Analysis   |  | Extraction    |  | (Jina v5)   |
| (OpenRouter)      |  | (OpenRouter)        |  +------------+
| Screenshot |  | Structured    |         |
| to profile |  | JSON profile  |         v
+------------+  +---------------+  +--------------+
    |                  |                  | Pinecone
    v                  v                  v  Vector Store
+------------+  +---------------+  +--------------+
| Visual     |  | Business      |  | Semantic     |
| Profile    |  | Profile       |  | Search Index |
+------------+  +---------------+  +--------------+
    |                  |                  |
    +------------------+------------------+
                         |
                         v
+------------------------------------------------------+
|  Competitor Discovery                                |
|  ──────────────────────────────────────────────────── |
|  For Local: Tracxn + Tavily listing-page discovery   |
|  For Global: Tavily listing-page discovery           |
|  Extract names + website URLs directly from HTML     |
|  LLM validation with hardened domain filtering       |
+------------------------------------------------------+
                        |
                        v
+------------------------------------------------------+
|  Parallel Competitor Crawling                        |
|  ──────────────────────────────────────────────────── |
|  - Processes 3-4 competitors concurrently            |
|  - Async/await with Semaphore for rate limiting      |
|  - Each competitor goes through same pipeline       |
+------------------------------------------------------+
                        |
                        v
+------------------------------------------------------+
|  Comparative Analysis (LLM)                          |
|  ──────────────────────────────────────────────────── |
|  - Positioning comparison                           |
|  - Pricing comparison                               |
|  - Feature gap analysis                             |
|  - Brand personality differences                    |
|  - Market saturation assessment                     |
|  - Strategic recommendations                        |
+------------------------------------------------------+
    |
    v
+---------------------+
|  PDF Report         |  ReportLab
|  Generation         |  - Executive summary
|                     |  - Detailed analysis
|                     |  - Strategic recommendations
+---------------------+
```

---

## Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| FastAPI | REST API framework |
| Uvicorn | ASGI server |
| SQLAlchemy | ORM for database |
| Python | Runtime |

### AI/ML
| Technology | Purpose |
|------------|---------|
| LangChain | LLM orchestration |
| OpenRouter (via LangChain) | LLM inference |
| Jina Embeddings v5 | Text embeddings |
| Pinecone | Vector database |

### Web Crawling
| Technology | Purpose |
|------------|---------|
| Playwright | Browser automation |
| BeautifulSoup4 | HTML parsing |
| lxml | Fast HTML parsing |

### Frontend
| Technology | Purpose |
|------------|---------|
| Streamlit | Interactive dashboard |

### Utilities
| Technology | Purpose |
|------------|---------|
| HuggingFace Tokenizers | Tokenize Text |
| ReportLab | PDF generation |
| Tavily | Web search and competitor source discovery |

---

## Key Features

### 1. Intelligent Competitor Discovery

The system uses a multi-stage approach for finding competitors based on scope:

**For Local Competitors (India):**
- Uses Tavily only to locate the correct Tracxn company page for the source brand
- Crawls the Tracxn page and extracts competitor names from the competitor table
- Resolves competitor websites from Tracxn profile pages or direct homepage verification
- Deduplicates local and global competitors by base domain and name

**For Global Competitors:**
- Uses LLM-only discovery to generate global competitor candidates
- Skips Tavily and Tracxn entirely for global scope

**For Both Scopes:**
- LLM validates all discovered competitors; only validated results are used in final ranking
- Hardened domain filtering rejects 50+ non-brand domain categories (platform sites, design awards, developer portals, SaaS tools, documentation sites, marketplaces, etc.)
- Runs post-crawl relevance validation via LLM after competitor profile extraction
- Falls back to LLM-based discovery if < 3 valid competitors found

### 2. Parallel Competitor Crawling

Instead of sequential crawling, the system processes competitors in parallel batches:

```
Batch 1: Competitor A, Competitor B, Competitor C (concurrent)
Batch 2: Competitor D, Competitor E, Competitor F (concurrent)
```

This significantly reduces total processing time while managing rate limits.

### 3. Semantic Embeddings and Vector Search

The system uses Jina embeddings v5 for semantic representation and Pinecone for vector similarity search:

- **Embeddings**: 1024-dimensional vectors for semantic similarity
- **Vector Store**: Cloud-based Pinecone for fast similarity queries
- **Similarity Scoring**: Cosine similarity for ranking competitors

### 4. LLM-Powered Analysis

All AI analysis uses OpenRouter models via LangChain:

- **Business Extraction**: Structured JSON from website content
- **Visual Analysis**: Screenshot analysis for brand personality
- **Competitor Discovery**: Query generation and validation
- **Comparative Analysis**: Strategic intelligence and recommendations

### 5. LLM Fallback System

The system includes automatic fallback to ensure reliability:

**Primary Model:** `openai/gpt-4.1-mini` (high capability)

**Fallback Model:** `google/gemini-2.5-flash` (used when rate limited)

**How It Works:**
1. Request goes to primary model (GPT-4.1-mini)
2. If rate limit error (429) is encountered, automatically switches to Gemini 2.5 Flash
3. If fallback also fails, raises exception
4. All LLM calls across the system use this wrapper

**Configuration:**
```env
OPENROUTER_API_KEY="your_key"
OPENROUTER_MODEL="openai/gpt-4.1-mini"
OPENROUTER_FALLBACK_MODEL="google/gemini-2.5-flash"
OPENROUTER_VISION_MODEL="google/gemini-2.5-flash"
TAVILY_API_KEY="tvly-xxx"
```

**Result:** Crawler gracefully handles rate-limited sites by waiting and retrying instead of failing immediately.

---

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- API keys for:
  - OpenRouter (LLM inference)
  - Pinecone (vector database)
  - Jina (embeddings)
  - Tavily (search)

### Step 1: Clone and Install

```bash
# Clone the repository
cd D:\Competitor

# Install dependencies using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create a `.env` file in the project root:

```env
# OpenRouter API
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openai/gpt-4.1-mini
OPENROUTER_FALLBACK_MODEL=google/gemini-2.5-flash
OPENROUTER_VISION_MODEL=google/gemini-2.5-flash

# Tavily Search
TAVILY_API_KEY=your_tavily_api_key_here
TAVILY_SEARCH_DEPTH=advanced

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=competitor-intel

# Jina Embeddings
JINA_API_KEY=your_jina_api_key_here
JINA_EMBEDDING_MODEL=jina-embeddings-v5-text-small

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Crawling
MAX_CRAWL_DEPTH=2
MAX_PAGES=8
CRAWL_DELAY_MIN_SECS=2.5
CRAWL_DELAY_MAX_SECS=4.0
CRAWL_429_DOMAIN_THRESHOLD=3
```

### Step 3: Initialize Database

```bash
uv run python -c "from database.session import init_db; init_db()"
```

### Step 4: Start Services

**API Server:**
```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Streamlit Frontend:**
```bash
uv run streamlit run frontend/app.py --server.port 8501
```

If your shell has broken proxy variables, clear them before starting the services:

```powershell
$env:HTTP_PROXY=''
$env:HTTPS_PROXY=''
$env:ALL_PROXY=''
```

---

## API Endpoints

### POST /analyze

Start a competitor intelligence analysis for a website URL.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "job_id": "abc123-def456",
  "message": "Analysis started",
  "status": "pending"
}
```

### GET /status/{job_id}

Poll the status of an analysis job.

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "completed",
  "progress": "Complete! Analyzed ExampleBrand with 5 competitors.",
  "company_id": 1,
  "error": null
}
```

### GET /company/{company_id}

Retrieve a company profile by ID.

**Response:**
```json
{
  "id": 1,
  "url": "https://example.com",
  "name": "ExampleBrand",
  "industry": "Men's Clothing",
  "json_profile": { ... },
  "visual_profile": { ... },
  "created_at": "2024-01-15T10:30:00"
}
```

### GET /company/{company_id}/competitors

Retrieve all discovered competitors for a company.

**Response:**
```json
{
  "company_id": 1,
  "company_name": "ExampleBrand",
  "competitors": [ ... ],
  "local_competitors": [ ... ],
  "global_competitors": [ ... ]
}
```

### GET /company/{company_id}/report

Download the PDF report for a company.

**Response:** PDF file download

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "Competitor Intelligence Engine"
}
```

---

## Project Structure

```
Competitor/
├── .env                           # API keys (not committed)
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # uv project configuration
├── requirements.txt               # Python dependencies
├── README.md                      # This file
│
├── api/
│   ├── main.py                    # FastAPI server with lifespan
│   ├── pipeline.py                # Orchestrates full pipeline
│   ├── schemas.py                 # API request/response models
│
├── competitor_discovery/
│   ├── discovery.py               # Competitor discovery with Tracxn + Tavily + LLM validation
│
├── crawler/
│   ├── crawler.py                 # Adaptive BFS web crawler with retry + exponential backoff
│
├── processing/
│   ├── text_processor.py          # Text cleaning and chunking
│   ├── dom_analyzer.py            # DOM structure analysis
│
├── vision/
│   ├── visual_analyzer.py         # Screenshot analysis with OpenRouter
│
├── extraction/
│   ├── business_extractor.py      # Structured business profile extraction
│
├── analysis/
│   ├── comparator.py              # Comparative intelligence analysis
│
├── embedding/
│   ├── embedder.py                # Jina embeddings + Pinecone vector store
│
├── reporting/
│   ├── report_generator.py        # PDF report generation
│
├── database/
│   ├── models.py                  # SQLAlchemy models
│   ├── session.py                 # Database session management
│
├── frontend/
│   ├── app.py                     # Streamlit dashboard
│
└── utils/
    ├── config.py                  # Configuration settings
    ├── helpers.py                 # Utility functions
    ├── logger.py                  # Logging setup
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key for LLM |
| `OPENROUTER_MODEL` | No | `xiaomi/mimo-v2-pro` | Primary OpenRouter model override |
| `OPENROUTER_FALLBACK_MODEL` | No | `google/gemma-4-31b-it:free` | Fallback OpenRouter model |
| `OPENROUTER_VISION_MODEL` | No | `google/gemma-4-31b-it:free` | OpenRouter vision model override |
| `TAVILY_API_KEY` | Yes | - | Tavily API key for search |
| `TAVILY_SEARCH_DEPTH` | No | `advanced` | Tavily search depth |
| `PINECONE_API_KEY` | Yes | - | Pinecone API key |
| `PINECONE_ENVIRONMENT` | No | `us-east-1` | Pinecone environment |
| `PINECONE_INDEX_NAME` | No | `competitor-intel` | Pinecone index name |
| `HF_API_KEY` | No | - | HuggingFace API key for tokenizer |
| `JINA_API_KEY` | Yes | - | Jina API key for embeddings |
| `JINA_EMBEDDING_MODEL` | No | `jina-embeddings-v5-text-small` | Jina model |
| `MAX_COMPETITORS` | No | 5 | Max competitors to analyze |
| `CHUNK_SIZE` | No | 1200 | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | No | 200 | Chunk overlap (tokens) |
| `MAX_PAGES` | No | 8 | Max pages to crawl |
| `MAX_CRAWL_DEPTH` | No | 2 | Max crawl depth |
| `CRAWL_DELAY_MIN_SECS` | No | 2.5 | Minimum polite crawl delay |
| `CRAWL_DELAY_MAX_SECS` | No | 4.0 | Maximum polite crawl delay |
| `CRAWL_429_DOMAIN_THRESHOLD` | No | 3 | Stop expanding a domain after repeated 429s |

### Key Settings

**Text Processing:**
- **Chunk Size**: 1200 tokens (optimal for OpenRouter context window)
- **Overlap**: 200 tokens (maintains semantic continuity)
- **Min Chunk**: 100 tokens (discard very small chunks)

**Crawling:**
- **Max Pages**: 8 per website
- **Max Depth**: 2 (prevents infinite crawling)
- **Timeout**: 30 seconds per page
- **Delay**: 2.5s to 4.0s jitter between same-domain requests
- **Parallel Batches**: 3-4 competitors

**Competitor Discovery:**
- **Max Local Competitors**: 5 (India)
- **Max Global Competitors**: 5 (International)
- **Search Provider**: Tavily 
- **Website Resolution**: Direct extraction from listing page HTML, Tavily fallback with hardened domain filtering
- **Cross-Scope Dedupe**: Same competitor removed across local/global
- **Similarity Threshold**: 0.25 (minimum semantic similarity)


---

## Usage Examples

### Example 1: Analyze a Men's Clothing Brand

```bash
# Start the API
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000

# Submit analysis request
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.muffynn.com"}'

# Check status
curl http://localhost:8000/status/{job_id}

# View results
curl http://localhost:8000/company/1/competitors
```

### Example 2: Using Streamlit Interface

1. Start Streamlit: `uv run streamlit run frontend/app.py`
2. Open browser to `http://localhost:8501`
3. Enter website URL
4. Click "Analyze"
5. View results in dashboard

### Example 3: Python SDK

```python
from competitor_discovery.discovery import discover_competitors
from embedding.embedder import EmbeddingEngine

# Create embedding engine
engine = EmbeddingEngine()

# Get your brand profile
profile = {
    "brand_name": "Your Brand",
    "industry": "Men's Clothing",
    "products_services": ["Shirts", "Pants"],
    "target_customer": "Men 25-40"
}

# Generate embeddings for your brand
embedding = engine.build_profile_embedding(profile)

# Discover competitors
competitors = discover_competitors(
    profile,
    "https://yourbrand.com",
    profile_embedding=embedding,
    embedding_engine=engine,
    scope="local"
)
```

---

## Troubleshooting

### LLM Rate Limits

**Problem:** Too many requests to OpenRouter API causing rate limit errors

**Solution:**
1. System includes automatic fallback to Gemini 2.5 Flash model
2. Primary model: GPT-4.1-mini (high capability)
3. Fallback model: Gemini 2.5 Flash (used when rate limited)
4. System automatically switches models on rate limit error
5. Adjust `OPENROUTER_MAX_RETRIES` and `OPENROUTER_RETRY_DELAY` in `.env` for fine-tuning

### Crawling Timeouts

**Problem:** Pages taking too long to crawl

**Solution:**
1. Reduce `MAX_PAGES` and `MAX_CRAWL_DEPTH` in `.env`
2. Increase `CRAWL_TIMEOUT_MS` for slower websites
3. Parallel crawling automatically handles timeouts

### Database Issues

**Problem:** Database connection errors

**Solution:**
1. Run: `python -c "from database.session import init_db; init_db()"`
2. Check that `data/` directory exists
3. Verify file permissions on database location

---

## Competitor Discovery Flow

### Local Competitors (India)
1. Search Tracxn for the brand's company page via Tavily
2. Crawl the Tracxn page and extract competitor names **and website URLs** directly from anchor tags
3. Search Tavily for additional competitor-listing pages (Growjo, Similarweb)
4. Crawl listing pages and extract competitor names + external website links from HTML
5. For competitors still missing a website, fall back to Tavily lookup with hardened domain filtering
6. LLM validation rejects irrelevant candidates; only validated results are used
7. Post-crawl relevance validation removes mismatched brands
8. Cross-scope dedupe prevents the same competitor from appearing in local and global

### Global Competitors
1. Search Tavily for competitor-listing pages (Similarweb, Ahrefs, Growjo)
2. Crawl listing pages and extract competitor names + external website links from HTML
3. For competitors still missing a website, fall back to Tavily lookup with hardened domain filtering
4. LLM validation filters weak candidates; only validated results are used
5. Post-crawl relevance validation removes mismatched brands
6. If < 3 valid candidates remain, use LLM fallback discovery


## Development

### Running Tests

```bash
uv run pytest tests/
```

### Code Formatting

```bash
uv run black .
uv run ruff check .
```

### Adding New Features

1. Follow existing module structure
2. Use LangChain patterns for LLM integration
3. Add type hints for all functions
4. Include docstrings for public functions
5. Update README if adding new capabilities

---



## License

MIT License - See LICENSE file for details

---

## Contact

For questions or issues, please refer to the GitHub repository or contact the development team.
