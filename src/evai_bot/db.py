from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

from .config import Settings


_settings = Settings()
engine = create_engine(_settings.database_url, echo=False)


def init_db() -> None:
    """Create tables if they do not exist."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

