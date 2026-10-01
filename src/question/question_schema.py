from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    quiz_id: UUID
    user_answer: str = Field(min_length=1)
    question: str = Field(min_length=1)


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    quiz_id: UUID | None = None
    user_answer: str | None = Field(default=None, min_length=1)
    question: str | None = Field(default=None, min_length=1)


class QuestionResponse(QuestionBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
