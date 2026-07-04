from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chat import Chat
    from .question import Question


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)

    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        unique=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="quiz"
    )

    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan"
    )