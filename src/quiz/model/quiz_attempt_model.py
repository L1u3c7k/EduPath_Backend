from sqlalchemy import (
    ForeignKey,
    String,
    DateTime,
    func,
    Integer,
    Column,
    Boolean,
)
from sqlalchemy.orm import relationship

from src.database import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(
        Integer,
        primary_key=True
    )

    question_id = Column(
        Integer,
        ForeignKey(
            "questions.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    attempt_number = Column(
        Integer,
        nullable=False
    )

    user_answer = Column(
        String,
        nullable=False
    )

    is_correct = Column(
        Boolean,
        nullable=False
    )

    feedback = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    question = relationship(
        "Question",
        back_populates="attempts"
    )