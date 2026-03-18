"""
FastAPI Backend for the Competitor Intelligence Engine.

Endpoints:
    POST /analyze          — Start analysis for an input URL (background job)
    GET  /status/{job_id}  — Poll job status
    GET  /company/{id}     — View company profile
    GET  /company/{id}/competitors — View discovered competitors
    GET  /company/{id}/report      — Download PDF report
"""

import asyncio
import json
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import nest_asyncio

nest_asyncio.apply()

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    JobStatusResponse,
    CompanyResponse,
    CompetitorListResponse,
    CompetitorResponse,
)
from api.pipeline import PipelineOrchestrator
from database.models import Company, Competitor, Report
from database.session import get_db_dependency, init_db
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Lifespan Manager ───────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown events.
    Replaces deprecated @app.on_event("startup").
    """
    # Startup
    init_db()
    logger.info("Competitor Intelligence Engine API started")
    yield
    # Shutdown
    logger.info("Competitor Intelligence Engine API shutting down")


# ── Initialize App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Competitor Intelligence Engine",
    description="AI-Powered Competitor Analysis System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ────────────────────────────────────────────────────────
# For production use, replace with Redis or a persistent queue.
jobs: dict[str, dict] = {}

# ── Concurrency guard ──────────────────────────────────────────────────────────
_analysis_lock = threading.Lock()
_active_job_id: str | None = None


# ── Background Pipeline Worker ─────────────────────────────────────────────────


def _run_pipeline(job_id: str, url: str) -> None:
    """
    Run the full analysis pipeline as a background task.

    Args:
        job_id: Unique job identifier.
        url: URL to analyze.
    """

    def status_callback(status: str):
        jobs[job_id]["progress"] = status

    jobs[job_id]["status"] = "running"

    global _active_job_id
    try:
        _active_job_id = job_id
        orchestrator = PipelineOrchestrator(status_callback=status_callback)

        # Run async pipeline in a new event loop
        # On Windows, we MUST use ProactorEventLoop for subprocess support
        # (Playwright spawns browser processes via asyncio subprocesses)
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(orchestrator.run(url))
        finally:
            loop.close()

        if result.get("status") == "completed":
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["company_id"] = result.get("company_id")
            jobs[job_id]["report_path"] = result.get("report_path")
            jobs[job_id]["progress"] = (
                f"Complete! Analyzed {result.get('company_name', '')} "
                f"with {result.get('competitors_found', 0)} competitors."
            )
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = result.get("error", "Unknown error")

    except Exception as e:
        logger.error("Pipeline background task failed: %s", e)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
    finally:
        _active_job_id = None


# ── API Endpoints ──────────────────────────────────────────────────────────────


@app.post("/analyze", response_model=AnalyzeResponse)
def start_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start competitor intelligence analysis for a URL.
    Returns a job_id for status polling.
    """
    # Concurrency guard: only one analysis at a time
    if _active_job_id is not None:
        active_job = jobs.get(_active_job_id, {})
        if active_job.get("status") == "running":
            raise HTTPException(
                status_code=429,
                detail="An analysis is already in progress. Please wait for it to complete.",
            )

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "job_id": job_id,
        "url": request.url,
        "status": "pending",
        "progress": "Queued for analysis",
        "company_id": None,
        "error": None,
    }

    background_tasks.add_task(_run_pipeline, job_id, request.url)

    logger.info("Analysis job created: %s for URL: %s", job_id, request.url)
    return AnalyzeResponse(job_id=job_id)


@app.get("/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Poll the status of an analysis job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", ""),
        company_id=job.get("company_id"),
        error=job.get("error"),
    )


@app.get("/company/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db_dependency)):
    """Retrieve a company profile by ID."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return CompanyResponse(
        id=company.id,
        url=company.url,
        name=company.name,
        industry=company.industry,
        json_profile=company.get_profile(),
        visual_profile=company.get_visual_profile(),
        dom_features=company.get_dom_features(),
        created_at=company.created_at,
    )


@app.get("/company/{company_id}/competitors", response_model=CompetitorListResponse)
def get_competitors(company_id: int, db: Session = Depends(get_db_dependency)):
    """Retrieve all discovered competitors for a company, split by scope."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    competitors = (
        db.query(Competitor)
        .filter(
            Competitor.parent_company_id == company_id,
        )
        .order_by(Competitor.similarity_score.desc())
        .all()
    )

    all_list = []
    local_list = []
    global_list = []

    for c in competitors:
        resp = CompetitorResponse(
            id=c.id,
            url=c.url,
            name=c.name,
            similarity_score=c.similarity_score,
            json_profile=c.get_profile(),
            visual_profile=c.get_visual_profile(),
            scope=c.scope or "global",
        )
        all_list.append(resp)
        if c.scope == "local":
            local_list.append(resp)
        else:
            global_list.append(resp)

    return CompetitorListResponse(
        company_id=company_id,
        company_name=company.name,
        competitors=all_list,
        local_competitors=local_list,
        global_competitors=global_list,
    )


@app.get("/company/{company_id}/report")
def get_report(company_id: int, db: Session = Depends(get_db_dependency)):
    """Download the PDF report for a company."""
    report = (
        db.query(Report)
        .filter(
            Report.company_id == company_id,
        )
        .order_by(Report.created_at.desc())
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.report_pdf_path and Path(report.report_pdf_path).exists():
        return FileResponse(
            path=report.report_pdf_path,
            filename=f"competitor_report_{company_id}.pdf",
            media_type="application/pdf",
        )

    # Fallback: return JSON report
    if report.report_json:
        return {"report": json.loads(report.report_json)}

    raise HTTPException(status_code=404, detail="Report file not found")


@app.get("/company/{company_id}/report/json")
def get_report_json(company_id: int, db: Session = Depends(get_db_dependency)):
    """Get the report data as JSON."""
    report = (
        db.query(Report)
        .filter(
            Report.company_id == company_id,
        )
        .order_by(Report.created_at.desc())
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "company_id": report.company_id,
        "report": report.get_report(),
        "pdf_available": bool(
            report.report_pdf_path and Path(report.report_pdf_path).exists()
        ),
        "created_at": str(report.created_at),
    }


# ── Health Check ───────────────────────────────────────────────────────────────


@app.get("/health")
def health_check():
    """API health check endpoint."""
    return {"status": "healthy", "service": "Competitor Intelligence Engine"}
