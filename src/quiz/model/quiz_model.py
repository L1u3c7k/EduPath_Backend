from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func,UUID, Integer, Column
from sqlalchemy.orm import relationship

from src.database import Base
import uuid



class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(
            UUID(as_uuid=True), 
            primary_key=True, 
            default=uuid.uuid4
        )
        

    chat_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    current_question = Column(
        Integer,
        nullable=False,
        default=1
    )

    last_message_id = Column(
        Integer,
        nullable=True
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
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