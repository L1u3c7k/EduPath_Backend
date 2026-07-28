from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func, Integer, Column
from sqlalchemy.orm import relationship
from src.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    title = Column(
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
        uselist=False
    )

    messages = relationship(
        "Message", 
        back_populates="chat", 
        cascade="all, delete-orphan"
    )