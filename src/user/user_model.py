from datetime import datetime
from sqlalchemy import String, DateTime, func, Integer, Column
from sqlalchemy.orm import relationship
from src.database import Base





class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    
    name = Column(String(100), nullable=False)
    
    email = Column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True
    )
    
    password = Column(String(255), nullable=False)
    
    refresh_token = Column(String(512), nullable=True)
    
    refresh_token_expires_at = Column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    chats = relationship(
        "Chat", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )