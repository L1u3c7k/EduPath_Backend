from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func, Integer, Column,UUID
from sqlalchemy.orm import relationship
from src.database import Base
import uuid


class Chat(Base):
    __tablename__ = "chats"

    id = Column(
            UUID(as_uuid=True), 
            primary_key=True, 
            default=uuid.uuid4
        )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    title = Column(
        String(255), 
        nullable=True
    )

    subject = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    user = relationship(
        "User", 
        back_populates="chats"
    )

    quiz = relationship(
        "Quiz",
        back_populates="chat",
        uselist=False,
        cascade="all, delete-orphan",
    )

    messages = relationship(
        "Message", 
        back_populates="chat", 
        cascade="all, delete-orphan"
    )