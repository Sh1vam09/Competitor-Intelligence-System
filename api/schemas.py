<<<<<<< HEAD
"""
Pydantic request/response schemas for the FastAPI backend.
"""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, HttpUrl, Field, field_validator


# ── Request Schemas ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Request body for starting a new analysis."""
    url: str = Field(..., description="URL of the website to analyze", examples=["https://example.com"])

    @field_validator("url")
    @classmethod
    def validate_and_normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        # Auto-prepend https:// if no scheme
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"

        parsed = urlparse(v)

        # Reject non-HTTP schemes
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")

        # Reject empty or invalid hosts
        host = parsed.netloc.lower()
        if not host or host in ("localhost", "127.0.0.1", "0.0.0.0"):
            raise ValueError("Please enter a valid public website URL")

        # Reject IP addresses
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$", host):
            raise ValueError("Please enter a domain name, not an IP address")

        # Reject URLs without a valid TLD
        domain_parts = host.replace("www.", "").split(".")
        if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
            raise ValueError("Please enter a valid domain (e.g., example.com)")

        # Normalize to root domain URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            "/",
            "", "", "",
        ))
        return normalized



# ── Response Schemas ───────────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    """Response for job status polling."""
    job_id: str
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    progress: str = Field("", description="Current progress description")
    company_id: Optional[int] = Field(None, description="Company ID once analysis starts")
    error: Optional[str] = Field(None, description="Error message if failed")


class CompanyResponse(BaseModel):
    """Response containing a company profile."""
    id: int
    url: str
    name: Optional[str]
    industry: Optional[str]
    json_profile: Optional[dict]
    visual_profile: Optional[dict]
    dom_features: Optional[dict]
    created_at: Optional[datetime]


class CompetitorResponse(BaseModel):
    """Response containing a competitor profile."""
    id: int
    url: str
    name: Optional[str]
    similarity_score: Optional[float]
    json_profile: Optional[dict]
    visual_profile: Optional[dict]
    scope: Optional[str] = "global"  # "local" or "global"


class CompetitorListResponse(BaseModel):
    """Response containing a list of competitors split by scope."""
    company_id: int
    company_name: Optional[str]
    competitors: list[CompetitorResponse]  # all competitors (backward compat)
    local_competitors: list[CompetitorResponse] = []
    global_competitors: list[CompetitorResponse] = []


class ReportResponse(BaseModel):
    """Response for report endpoint."""
    id: int
    company_id: int
    report_json: Optional[dict]
    report_pdf_path: Optional[str]
    created_at: Optional[datetime]


class AnalyzeResponse(BaseModel):
    """Response for the analyze endpoint."""
    job_id: str
    message: str = "Analysis started"
    status: str = "pending"
=======
"""
Pydantic request/response schemas for the FastAPI backend.
"""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, HttpUrl, Field, field_validator


# ── Request Schemas ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Request body for starting a new analysis."""
    url: str = Field(..., description="URL of the website to analyze", examples=["https://example.com"])

    @field_validator("url")
    @classmethod
    def validate_and_normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        # Auto-prepend https:// if no scheme
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"

        parsed = urlparse(v)

        # Reject non-HTTP schemes
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")

        # Reject empty or invalid hosts
        host = parsed.netloc.lower()
        if not host or host in ("localhost", "127.0.0.1", "0.0.0.0"):
            raise ValueError("Please enter a valid public website URL")

        # Reject IP addresses
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$", host):
            raise ValueError("Please enter a domain name, not an IP address")

        # Reject URLs without a valid TLD
        domain_parts = host.replace("www.", "").split(".")
        if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
            raise ValueError("Please enter a valid domain (e.g., example.com)")

        # Normalize to root domain URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            "/",
            "", "", "",
        ))
        return normalized



# ── Response Schemas ───────────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    """Response for job status polling."""
    job_id: str
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    progress: str = Field("", description="Current progress description")
    company_id: Optional[int] = Field(None, description="Company ID once analysis starts")
    error: Optional[str] = Field(None, description="Error message if failed")


class CompanyResponse(BaseModel):
    """Response containing a company profile."""
    id: int
    url: str
    name: Optional[str]
    industry: Optional[str]
    json_profile: Optional[dict]
    visual_profile: Optional[dict]
    dom_features: Optional[dict]
    created_at: Optional[datetime]


class CompetitorResponse(BaseModel):
    """Response containing a competitor profile."""
    id: int
    url: str
    name: Optional[str]
    similarity_score: Optional[float]
    json_profile: Optional[dict]
    visual_profile: Optional[dict]
    scope: Optional[str] = "global"  # "local" or "global"


class CompetitorListResponse(BaseModel):
    """Response containing a list of competitors split by scope."""
    company_id: int
    company_name: Optional[str]
    competitors: list[CompetitorResponse]  # all competitors (backward compat)
    local_competitors: list[CompetitorResponse] = []
    global_competitors: list[CompetitorResponse] = []


class ReportResponse(BaseModel):
    """Response for report endpoint."""
    id: int
    company_id: int
    report_json: Optional[dict]
    report_pdf_path: Optional[str]
    created_at: Optional[datetime]


class AnalyzeResponse(BaseModel):
    """Response for the analyze endpoint."""
    job_id: str
    message: str = "Analysis started"
    status: str = "pending"
>>>>>>> c8b6483 (updated the report and fixed bugs)
