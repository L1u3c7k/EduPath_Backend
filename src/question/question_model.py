import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    quiz_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False
    )

    question = Column(String, nullable=False)
    model_answer = Column(String, nullable=False)  # Ideal rubric / standard answer
    user_answer = Column(String, nullable=True)   # Nullable in case user never answered

    # --- Added Fields for Evaluation & Attempt Tracking ---
    is_correct = Column(Boolean, nullable=False, default=False)
    ai_feedback = Column(String, nullable=True)
    attempts_used = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    quiz = relationship(
        "Quiz",
        back_populates="questions"
    )