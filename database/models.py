
"""
SQLAlchemy ORM models for the Competitor Intelligence Engine.

Tables:
    - companies: Analyzed company profiles
    - competitors: Discovered competitor profiles
    - reports: Generated intelligence reports
"""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Company(Base):
    """
    Stores the analyzed profile for a primary company.
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, unique=True)
    name = Column(String(512), nullable=True)
    industry = Column(String(256), nullable=True)
    json_profile = Column(Text, nullable=True)
    visual_profile = Column(Text, nullable=True)
    dom_features = Column(Text, nullable=True)
    embedding_vector = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    competitors = relationship("Competitor", back_populates="parent_company", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="company", cascade="all, delete-orphan")

    def get_profile(self) -> dict:
        """Parse and return the JSON profile as a dictionary."""
        if self.json_profile:
            return json.loads(self.json_profile)
        return {}

    def get_visual_profile(self) -> dict:
        """Parse and return the visual profile as a dictionary."""
        if self.visual_profile:
            return json.loads(self.visual_profile)
        return {}

    def get_dom_features(self) -> dict:
        """Parse and return DOM features as a dictionary."""
        if self.dom_features:
            return json.loads(self.dom_features)
        return {}

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name='{self.name}', url='{self.url}')>"


class Competitor(Base):
    """
    Stores a discovered competitor linked to a parent company.
    """
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    url = Column(String(2048), nullable=False)
    name = Column(String(512), nullable=True)
    similarity_score = Column(Float, nullable=True)
    json_profile = Column(Text, nullable=True)
    visual_profile = Column(Text, nullable=True)
    dom_features = Column(Text, nullable=True)
    embedding_vector = Column(LargeBinary, nullable=True)
    scope = Column(String(16), default="global", nullable=True)  # "local" or "global"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    parent_company = relationship("Company", back_populates="competitors")

    def get_profile(self) -> dict:
        """Parse and return the JSON profile as a dictionary."""
        if self.json_profile:
            return json.loads(self.json_profile)
        return {}

    def get_visual_profile(self) -> dict:
        """Parse and return the visual profile as a dictionary."""
        if self.visual_profile:
            return json.loads(self.visual_profile)
        return {}

    def __repr__(self) -> str:
        return f"<Competitor(id={self.id}, name='{self.name}', score={self.similarity_score})>"


class Report(Base):
    """
    Stores a generated intelligence report for a company.
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    report_json = Column(Text, nullable=True)
    report_pdf_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    company = relationship("Company", back_populates="reports")

    def get_report(self) -> dict:
        """Parse and return the report JSON as a dictionary."""
        if self.report_json:
            return json.loads(self.report_json)
        return {}

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, company_id={self.company_id})>"

"""
SQLAlchemy ORM models for the Competitor Intelligence Engine.

Tables:
    - companies: Analyzed company profiles
    - competitors: Discovered competitor profiles
    - reports: Generated intelligence reports
"""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Company(Base):
    """
    Stores the analyzed profile for a primary company.
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, unique=True)
    name = Column(String(512), nullable=True)
    industry = Column(String(256), nullable=True)
    json_profile = Column(Text, nullable=True)
    visual_profile = Column(Text, nullable=True)
    dom_features = Column(Text, nullable=True)
    embedding_vector = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    competitors = relationship("Competitor", back_populates="parent_company", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="company", cascade="all, delete-orphan")

    def get_profile(self) -> dict:
        """Parse and return the JSON profile as a dictionary."""
        if self.json_profile:
            return json.loads(self.json_profile)
        return {}

    def get_visual_profile(self) -> dict:
        """Parse and return the visual profile as a dictionary."""
        if self.visual_profile:
            return json.loads(self.visual_profile)
        return {}

    def get_dom_features(self) -> dict:
        """Parse and return DOM features as a dictionary."""
        if self.dom_features:
            return json.loads(self.dom_features)
        return {}

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name='{self.name}', url='{self.url}')>"


class Competitor(Base):
    """
    Stores a discovered competitor linked to a parent company.
    """
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    url = Column(String(2048), nullable=False)
    name = Column(String(512), nullable=True)
    similarity_score = Column(Float, nullable=True)
    json_profile = Column(Text, nullable=True)
    visual_profile = Column(Text, nullable=True)
    dom_features = Column(Text, nullable=True)
    embedding_vector = Column(LargeBinary, nullable=True)
    scope = Column(String(16), default="global", nullable=True)  # "local" or "global"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    parent_company = relationship("Company", back_populates="competitors")

    def get_profile(self) -> dict:
        """Parse and return the JSON profile as a dictionary."""
        if self.json_profile:
            return json.loads(self.json_profile)
        return {}

    def get_visual_profile(self) -> dict:
        """Parse and return the visual profile as a dictionary."""
        if self.visual_profile:
            return json.loads(self.visual_profile)
        return {}

    def __repr__(self) -> str:
        return f"<Competitor(id={self.id}, name='{self.name}', score={self.similarity_score})>"


class Report(Base):
    """
    Stores a generated intelligence report for a company.
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    report_json = Column(Text, nullable=True)
    report_pdf_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    company = relationship("Company", back_populates="reports")

    def get_report(self) -> dict:
        """Parse and return the report JSON as a dictionary."""
        if self.report_json:
            return json.loads(self.report_json)
        return {}

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, company_id={self.company_id})>"

