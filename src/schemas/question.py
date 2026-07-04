from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    quiz_id: int
    content: str = Field(min_length=1)


class QuestionCreate(QuestionBase):
    pass


class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
