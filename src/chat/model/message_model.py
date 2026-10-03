from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    String,
    DateTime,
    func,
    Integer,
    Column,
    Enum as SQLEnum, UUID
)
from sqlalchemy.orm import relationship
from src.database import Base
from enum import Enum
import uuid

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id = Column(
            UUID(as_uuid=True), 
            primary_key=True, 
            default=uuid.uuid4
        )

    chat_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    role = Column(
        SQLEnum(MessageRole),
        nullable=False,
        default=MessageRole.USER
    )

    message = Column(
        String,
        nullable=False
    )

    chapter = Column(
        String(255),
        nullable=True
    )

    topic = Column(
        String(255),
        nullable=True
    )

    subtopic = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    chat = relationship(
        "Chat",
        back_populates="messages"
    )