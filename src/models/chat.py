from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
if TYPE_CHECKING:
    from .user import User
    from .quiz import Quiz
    from .message import Message
from src.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Put quotes here so SQLAlchemy looks them up dynamically
    user: Mapped["User"] = relationship(
        back_populates="chats"
    )

    quiz: Mapped["Quiz"] = relationship(
        back_populates="chat",
        uselist=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan"
    )
