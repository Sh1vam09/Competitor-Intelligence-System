# Competitor Intelligence Engine

FastAPI + Next.js app for website-based competitor analysis. It crawls a company website, extracts a business profile, discovers local and global competitors, analyzes them, and generates a PDF report.

## Architecture Flow

![Architecture Flow](architecture_flow.png)

1. Crawl source website with Playwright.
2. Clean text and chunk it with LangChain `RecursiveCharacterTextSplitter`.
3. Extract business and visual profiles with OpenRouter models.
4. Create embeddings with Jina and store vectors in Pinecone.
5. Find local Indian competitors from Tracxn pages located via Tavily.
6. Analyze local Tracxn competitors first and build a local benchmark summary.
7. Use that benchmark to guide global LLM competitor discovery.
8. Crawl/analyze competitors in parallel, compute similarity, save results, and generate a PDF report.

## Key Behavior

- Tracxn local candidates are trusted for inclusion when `source == "tracxn"`.
- Tracxn competitors are still crawled, profiled, embedded, scored, saved, and shown in reports.
- Tracxn similarity is not forced to `1.0`; the real embedding similarity is saved.
- Global competitors still go through LLM validation and relevance checks.
- Pinecone is the active vector store. There is no local FAISS index.
- No HuggingFace/BERT tokenizer is used; chunking is recursive character splitting.

## Stack

- Backend: FastAPI, SQLAlchemy, Playwright, BeautifulSoup, LangChain, OpenRouter, Jina, Pinecone, ReportLab
- Frontend: Next.js, React, TypeScript
- Search/source discovery: Tavily and Tracxn
- Default DB: SQLite under `backend/data/`

## Setup

Install backend dependencies:

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Create `.env` in the repo root:

```env
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
PINECONE_API_KEY=your_pinecone_key
JINA_API_KEY=your_jina_key
```

Useful optional settings:

```env
OPENROUTER_MODEL=xiaomi/mimo-v2-pro
OPENROUTER_FALLBACK_MODEL=google/gemma-4-31b-it:free
OPENROUTER_VISION_MODEL=google/gemma-4-31b-it:free
PINECONE_INDEX_NAME=competitor-intel
JINA_EMBEDDING_MODEL=jina-embeddings-v5-text-small
MAX_LOCAL_COMPETITORS=5
MAX_GLOBAL_COMPETITORS=5
COMPETITOR_CRAWL_CONCURRENCY=3
```

## Run

Backend:

```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

Docker:

```bash
docker compose up --build
```

## API

- `POST /analyze` - start analysis for `{ "url": "https://example.com" }`
- `GET /status/{job_id}` - poll job status
- `GET /company/{company_id}` - get source company profile
- `GET /company/{company_id}/competitors` - get local/global competitors
- `GET /company/{company_id}/report` - download PDF report
- `GET /company/{company_id}/report/json` - get report JSON
- `GET /health` - health check

## Project Structure

```text
backend/
  api/                    FastAPI app and pipeline orchestration
  analysis/               Comparative analysis prompts
  competitor_discovery/   Tracxn, Tavily, LLM discovery, ranking
  crawler/                Playwright crawler
  database/               SQLAlchemy models and sessions
  embedding/              Jina + Pinecone integration
  extraction/             Business profile extraction
  processing/             Text cleanup, chunking, DOM analysis
  reporting/              PDF generation
  vision/                 Screenshot analysis
frontend/
  app/                    Next.js UI
```

## Runtime Data

Generated files live under `backend/data/`:

- screenshots
- reports
- SQLite database

## License

See [LICENSE](LICENSE).
