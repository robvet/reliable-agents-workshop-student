"""SQLAlchemy engine/session factory for the data generator."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class GeneratorDatabase:
    """Owns the SQLAlchemy engine and session factory used by the data generator.

    This is the only place in the app that talks to PostgreSQL directly; every
    other feature goes through MCP instead.
    """

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)

    def create_session(self) -> Session:
        return self._session_factory()
