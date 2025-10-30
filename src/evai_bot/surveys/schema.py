from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


QuestionType = Literal["text", "choice"]


class ChoiceOption(BaseModel):
    label: str
    value: str
    color: Optional[str] = None  # hex or CSS color for charts


class QuestionSpec(BaseModel):
    id: str
    type: QuestionType
    prompt: str
    required: bool = True
    image_url: Optional[str] = None
    choices: Optional[List[ChoiceOption]] = None  # for type="choice"


class SurveySpec(BaseModel):
    key: str
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    questions: List[QuestionSpec] = Field(default_factory=list)
