from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


# class QuizBase(BaseModel):
#     chat_id: UUID


# class QuizCreate(QuizBase):
#     pass


# class QuizUpdate(BaseModel):
#     chat_id: UUID | None = None


# class QuizResponse(QuizBase):
#     id: UUID
#     created_at: datetime

#     model_config = ConfigDict(from_attributes=True)


class SingleAnswerSubmission(BaseModel):
    
    question_id: int
    user_answer: str


class EvaluationResult(BaseModel):
    is_correct: bool
    feedback: str
