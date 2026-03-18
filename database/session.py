<<<<<<< HEAD
"""
Database session management and initialization.

Provides a SQLAlchemy engine, session factory, and database init function.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from utils.config import DATABASE_URL
from database.models import Base
from utils.logger import get_logger

logger = get_logger(__name__)

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # Required for SQLite + threads
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    Call this once at application startup.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at: %s", DATABASE_URL)


def get_db() -> Session:
    """
    Create and return a new database session.
    Caller is responsible for closing the session.

    Returns:
        SQLAlchemy Session instance.
    """
    db = SessionLocal()
    return db


def get_db_dependency():
    """
    FastAPI dependency that provides a database session
    and ensures it is closed after the request.

    Yields:
        SQLAlchemy Session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
=======
"""
Database session management and initialization.

Provides a SQLAlchemy engine, session factory, and database init function.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from utils.config import DATABASE_URL
from database.models import Base
from utils.logger import get_logger

logger = get_logger(__name__)

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # Required for SQLite + threads
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    Call this once at application startup.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at: %s", DATABASE_URL)


def get_db() -> Session:
    """
    Create and return a new database session.
    Caller is responsible for closing the session.

    Returns:
        SQLAlchemy Session instance.
    """
    db = SessionLocal()
    return db


def get_db_dependency():
    """
    FastAPI dependency that provides a database session
    and ensures it is closed after the request.

    Yields:
        SQLAlchemy Session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
>>>>>>> c8b6483 (updated the report and fixed bugs)
