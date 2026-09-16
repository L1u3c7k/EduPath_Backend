from datetime import datetime
from src.chat.model.message_model import MessageRole
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column
from sqlalchemy import Enum as SQLEnum


class MessageBase(BaseModel):
    
    message: str = Field(min_length=1)


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    
    message: str = Field(default=None, min_length=1)


class MessageResponse(MessageBase):
    id: int
    created_at: datetime
    role:str
    model_config = ConfigDict(from_attributes=True)
