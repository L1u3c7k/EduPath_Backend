from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionResponse(BaseModel):
    id: int
    question_number: int
    question: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class QuizQuestionResponse(BaseModel):
    id: int
    question_number: int
    question: str

    model_config = ConfigDict(
        from_attributes=True
    )


class QuizAnswerRequest(BaseModel):
    answer: str = Field(
        min_length=1
    )


class QuizAnswerResponse(BaseModel):
    correct: bool
    explanation: str
    hint: str | None = None
    question_completed: bool
    quiz_completed: bool
    next_question: QuizQuestionResponse | None = None

    # Only returned after 3 incorrect attempts.
    model_answer: str | None = None