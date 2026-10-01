from datetime import datetime
from sqlalchemy import String, DateTime, func, Column, UUID
from sqlalchemy.orm import relationship, mapped_column, Mapped
from src.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    name = Column(String(100), nullable=False)
    
    email = Column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True
    )
    image_file: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        default=None,
    )
    @property
    def image_path(self) -> str | None:
        from src.user.image_utils import public_image_url

        return public_image_url(self.image_file)
    
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