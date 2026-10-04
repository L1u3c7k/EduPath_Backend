from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from src.question.schema.question_schema import (
    QuizQuestionResponse,
)


class QuizResponse(BaseModel):
    id: UUID
    chat_id: UUID
    last_message_id: UUID | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class QuizDetailResponse(BaseModel):
    id: UUID
    chat_id: UUID
    last_message_id: UUID | None = None
    completed_at: datetime | None = None
    created_at: datetime

    questions: list[QuizQuestionResponse] = Field(
        default_factory=list
    )

    model_config = ConfigDict(
        from_attributes=True
    )