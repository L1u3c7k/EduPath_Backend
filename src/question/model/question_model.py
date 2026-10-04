from sqlalchemy import (
    ForeignKey,
    String,
    DateTime,
    func,
    Integer,
    Column,
    Boolean,
    UUID,
)
from sqlalchemy.orm import relationship

from src.database import Base
import uuid


class Question(Base):
    __tablename__ = "questions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    quiz_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )

    question_number = Column(
        Integer,
        nullable=False,
    )

    question = Column(
        String,
        nullable=False,
    )

    model_answer = Column(
        String,
        nullable=False,
    )

    user_answer = Column(
        String,
        nullable=True,
    )

    is_correct = Column(
        Boolean,
        nullable=False,
    )

    ai_feedback = Column(
        String,
        nullable=True,
    )

    attempts_used = Column(
        Integer,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    quiz = relationship(
        "Quiz",
        back_populates="questions",
    )