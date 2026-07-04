from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .quiz import Quiz


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)

    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE")
    )
    answer: Mapped[str] = mapped_column(String, nullable=False)

    subject: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    quiz: Mapped["Quiz"] = relationship(
        back_populates="questions"
    )