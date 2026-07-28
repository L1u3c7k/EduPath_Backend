from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    quiz_id: int
    answer: str = Field(min_length=1)
    subject: str = Field(min_length=1)


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    quiz_id: int | None = None
    answer: str | None = Field(default=None, min_length=1)
    subject: str | None = Field(default=None, min_length=1)


class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
