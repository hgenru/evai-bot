from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Telegram identity
    tg_id: int = Field(index=True, unique=True)
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Registration status flags (expand later with survey progress)
    is_registered: bool = Field(default=False)


# Placeholder entities for upcoming survey engine
class Survey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    key: str = Field(index=True, unique=True)
    title: str
    description: Optional[str] = None


class ParticipantResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    user_id: int = Field(foreign_key="user.id")
    survey_id: int = Field(foreign_key="survey.id")
    # JSON blob with answers (temporary, later we’ll normalize or keep hybrid)
    payload_json: str

