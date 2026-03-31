# AI-Powered Competitor Intelligence Engine

## Project Overview

This project provides automated competitive intelligence analysis for any website. It extracts detailed business profiles, discovers competitors, and generates comprehensive comparative analysis reports.

### What It Does

1. **Analyze any website** - Crawls and extracts structured business information
2. **Find competitors** - Discovers local (India) competitors via Tracxn and global competitors through AI-validated search on market listing platforms
3. **Compare brands** - Performs detailed comparative analysis of market positioning
4. **Generate reports** - Creates PDF reports with strategic recommendations

---

## Architecture and Data Flow

```
URL Input
    |
    v
+---------------------+
|  Web Crawler        |  Playwright + BeautifulSoup
|  (Adaptive BFS)     |  - Crawls up to 15 pages
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
| (Groq)     |  | (Groq)        |  +------------+
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
|  For Local: Tracxn search + crawl competitor pages   |
|  For Global: DDG search + crawl competitor pages     |
|  Extract names, find websites, LLM validation       |
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
| Groq (via LangChain) | LLM inference |
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
| ddgs | DuckDuckGo search |

---

## Key Features

### 1. Intelligent Competitor Discovery

The system uses a multi-stage approach for finding competitors based on scope:

**For Local Competitors (India):**
- Searches Tracxn platform using DuckDuckGo
- Crawls Tracxn company profile page
- Extracts competitor names from "Competitors" and "Alternatives" sections
- Finds official websites for each competitor

**For Global Competitors:**
- Searches competitor listing pages (Tracxn, Similarweb, Owler)
- Crawls the most relevant listing page
- Extracts competitor names and finds their websites

**For Both Scopes:**
- LLM validates all discovered competitors
- Rejects news sites, Q&A sites (zhihu, stackexchange), generic domains
- Falls back to LLM discovery if < 5 valid competitors found

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

All AI analysis uses Groq models via LangChain:

- **Business Extraction**: Structured JSON from website content
- **Visual Analysis**: Screenshot analysis for brand personality
- **Competitor Discovery**: Query generation and validation
- **Comparative Analysis**: Strategic intelligence and recommendations

### 5. LLM Fallback System

The system includes automatic fallback to ensure reliability:

**Primary Model:** `openai/gpt-oss-120b` (high capability)

**Fallback Model:** `llama-3.3-70b-versatile` (used when rate limited)

**How It Works:**
1. Request goes to primary model (GPT-OSS-120b)
2. If rate limit error (429) is encountered, automatically switches to Llama 70b
3. If fallback also fails, raises exception
4. All LLM calls across the system use this wrapper

**Configuration:**
```env
GROQ_API_KEY="your_key"
GROQ_MODEL="openai/gpt-oss-120b"
GROQ_FALLBACK_MODEL="meta-llama/llama-3.1-70b-instruct"
HF_API_KEY="hf_xxx"  # For HuggingFace tokenizer
```

**Result:** Crawler gracefully handles rate-limited sites by waiting and retrying instead of failing immediately.

---

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- API keys for:
  - Groq (LLM inference)
  - Pinecone (vector database)
  - Jina (embeddings)
  - DuckDuckGo (search, optional API key)

### Step 1: Clone and Install

```bash
# Clone the repository
cd D:\New folder\Competitor

# Install dependencies using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create a `.env` file in the project root:

```env
# Groq API
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=meta-llama/llama-3.1-8b-instruct

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
│   ├── discovery.py               # Competitor discovery with LLM + DDG
│
├── crawler/
│   ├── crawler.py                 # Adaptive BFS web crawler with retry + exponential backoff
│
├── processing/
│   ├── text_processor.py          # Text cleaning and chunking
│   ├── dom_analyzer.py            # DOM structure analysis
│
├── vision/
│   ├── visual_analyzer.py         # Screenshot analysis with Groq
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
| `GROQ_API_KEY` | Yes | - | Groq API key for LLM |
| `GROQ_MODEL` | No | `meta-llama/llama-3.1-8b-instruct` | Primary Groq model |
| `GROQ_FALLBACK_MODEL` | No | `llama-3.3-70b-versatile` | Fallback Groq model |
| `PINECONE_API_KEY` | Yes | - | Pinecone API key |
| `PINECONE_ENVIRONMENT` | No | `us-east-1` | Pinecone environment |
| `PINECONE_INDEX_NAME` | No | `competitor-intel` | Pinecone index name |
| `HF_API_KEY` | No | - | HuggingFace API key for tokenizer |
| `JINA_API_KEY` | Yes | - | Jina API key for embeddings |
| `JINA_EMBEDDING_MODEL` | No | `jina-embeddings-v5-text-small` | Jina model |
| `MAX_COMPETITORS` | No | 5 | Max competitors to analyze |
| `CHUNK_SIZE` | No | 1200 | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | No | 200 | Chunk overlap (tokens) |
| `MAX_PAGES` | No | 15 | Max pages to crawl |
| `MAX_CRAWL_DEPTH` | No | 2 | Max crawl depth |

### Key Settings

**Text Processing:**
- **Chunk Size**: 1200 tokens (optimal for Groq context window)
- **Overlap**: 200 tokens (maintains semantic continuity)
- **Min Chunk**: 100 tokens (discard very small chunks)

**Crawling:**
- **Max Pages**: 15 per website
- **Max Depth**: 2 (prevents infinite crawling)
- **Timeout**: 30 seconds per page
- **Parallel Batches**: 3-4 competitors

**Competitor Discovery:**
- **Max Local Competitors**: 5 (India)
- **Max Global Competitors**: 5 (International)
- **DDG Rate Limit**: 1 second between queries
- **Similarity Threshold**: 0.3 (minimum semantic similarity)

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

**Problem:** Too many requests to Groq API causing rate limit errors

**Solution:**
1. System includes automatic fallback to Llama 70b model
2. Primary model: GPT-OSS-120b (high capability)
3. Fallback model: Llama 3.1 70b (used when rate limited)
4. System automatically switches models on rate limit error
5. Adjust `GROQ_MAX_RETRIES` and `GROQ_RETRY_DELAY` in `.env` for fine-tuning

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

## Updated Competitor Discovery Flow

### Local Competitors (India)
1. Search Tracxn: `tracxn "{brand}" company profile`
2. Crawl Tracxn page
3. Extract competitor names from page text
4. Find official websites via DDG
5. LLM validation (reject news/Q&A/generic sites)
6. If < 5 valid: LLM fallback discovery

### Global Competitors
1. Search DDG for competitor listing pages
2. Crawl first relevant result (Tracxn, Similarweb, Owler)
3. Extract competitor names and find websites
4. LLM validation
5. If < 5 valid: LLM fallback discovery

---

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

## Project Roadmap

### Phase 1: Core Pipeline (Completed)
- Web crawling with Playwright
- Text processing and chunking
- Business profile extraction
- Competitor discovery with DDG

### Phase 2: Enhanced AI Integration (Completed)
- LangChain integration
- Jina embeddings v5
- Pinecone vector store
- Parallel competitor crawling

### Phase 3: Optimization (Completed)
- Dynamic query generation with LLM
- Improved relevance filtering
- Response time optimization
- Error handling improvements
- Tracxn integration for local competitor discovery
- Domain filtering for irrelevant results (news, Q&A, generic sites)
- Website URL resolution for extracted competitors
- LLM validation with strict rejection rules
- LLM fallback system (automatic switch to Llama 70b on rate limit)
- HuggingFace API integration for tokenizer

### Phase 4: Future Enhancements
- Multi-language support
- Real-time monitoring
- API rate limiting
- Dashboard analytics
- Export formats (CSV, Excel)

---

## License

MIT License - See LICENSE file for details

---

## Contact

For questions or issues, please refer to the GitHub repository or contact the development team.
