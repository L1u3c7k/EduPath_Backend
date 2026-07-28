from __future__ import annotations

from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func, Integer, Column,Enum as SQLEnum
from sqlalchemy.orm import relationship
from src.database import Base
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    chat_id = Column(
        Integer,
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    role = Column(SQLEnum(MessageRole), nullable=False, default=MessageRole.USER)

    content = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    chat = relationship(
        "Chat",
        back_populates="messages"
    )