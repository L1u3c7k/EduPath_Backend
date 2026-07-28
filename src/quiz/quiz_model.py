from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, Integer, Column
from sqlalchemy.orm import relationship
from src.database import Base



class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)

    chat_id = Column(
        Integer,
        ForeignKey("chats.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    chat = relationship(
        "Chat",
        back_populates="quiz"
    )

    questions = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan"
    )