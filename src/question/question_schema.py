from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    quiz_id: int
    user_answer: str = Field(min_length=1)
    question: str = Field(min_length=1)


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    quiz_id: int | None = None
    user_answer: str | None = Field(default=None, min_length=1)
    question: str | None = Field(default=None, min_length=1)


class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
