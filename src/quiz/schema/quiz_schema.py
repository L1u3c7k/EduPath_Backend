from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QuizResponse(BaseModel):
    id: int
    chat_id: int
    current_question: int
    completed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )