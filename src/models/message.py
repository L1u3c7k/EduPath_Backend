from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .chat import Chat

from src.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True
    )

    role: Mapped[str] = mapped_column(String(50), nullable=False)

    content: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="messages"
    )
