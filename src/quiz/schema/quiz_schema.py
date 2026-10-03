from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.question.schema.question_schema import (
    QuizQuestionResponse,
)


class QuizResponse(BaseModel):
    id: int
    chat_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class QuizDetailResponse(BaseModel):
    id: int
    chat_id: int
    created_at: datetime

    questions: list[QuizQuestionResponse] = Field(
        default_factory=list
    )

    model_config = ConfigDict(
        from_attributes=True
    )