from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func, Integer, Column
from sqlalchemy.orm import relationship
from src.database import Base



class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)

    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False
    )
    
    user_answer = Column(String, nullable=False)
    model_answer= Column(String, nullable=False)

    question = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    quiz = relationship(
        "Quiz",
        back_populates="questions"
    )