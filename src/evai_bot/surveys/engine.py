from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sqlmodel import select

from ..db import engine, get_session
from ..models import SurveyAnswer, SurveyRun, User
from .schema import QuestionSpec, SurveySpec


SURVEYS_DIR = Path(__file__).resolve().parent / "data"


def load_survey(key: str) -> SurveySpec:
    path = SURVEYS_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"Survey file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return SurveySpec.model_validate(data)


def get_or_create_user(tg_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]) -> User:
    with get_session() as session:
        statement = select(User).where(User.tg_id == tg_id)
        user = session.exec(statement).first()
        if user:
            # update basic fields opportunistically
            changed = False
            if username and user.username != username:
                user.username = username
                changed = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                changed = True
            if changed:
                session.add(user)
                session.commit()
            return user
        user = User(tg_id=tg_id, username=username, first_name=first_name, last_name=last_name)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def start_survey_run(user_id: int, survey_key: str) -> SurveyRun:
    with get_session() as session:
        # If an unfinished run exists, reuse it
        stmt = select(SurveyRun).where(
            (SurveyRun.user_id == user_id)
            & (SurveyRun.survey_key == survey_key)
            & (SurveyRun.completed_at.is_(None))
        )
        run = session.exec(stmt).first()
        if run:
            return run
        run = SurveyRun(user_id=user_id, survey_key=survey_key, current_index=0)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def get_current_question(run: SurveyRun, spec: SurveySpec) -> Optional[QuestionSpec]:
    if run.current_index >= len(spec.questions):
        return None
    return spec.questions[run.current_index]


def record_answer_and_advance(run_id: int, question_id: str, *, text: Optional[str] = None, choice: Optional[str] = None) -> SurveyRun:
    with get_session() as session:
        run = session.get(SurveyRun, run_id)
        if not run:
            raise ValueError("run not found")
        ans = SurveyAnswer(run_id=run.id, question_id=question_id, answer_text=text, answer_choice=choice)
        session.add(ans)
        run.current_index += 1
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def complete_run(run_id: int) -> None:
    from datetime import datetime

    with get_session() as session:
        run = session.get(SurveyRun, run_id)
        if not run:
            return
        run.completed_at = datetime.utcnow()
        session.add(run)
        session.commit()

