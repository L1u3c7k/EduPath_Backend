from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column
from sqlalchemy import Enum as SQLEnum
from uuid import UUID

class MessageBase(BaseModel):
    message: str = Field(min_length=1)


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    message: str = Field(default=None, min_length=1)


class MessageResponse(MessageBase):
    id: UUID
    created_at: datetime
    role:str
    quiz_ready: bool = False
    chapter: str | None
    topic: str | None
    subtopic: str | None
    model_config = ConfigDict(from_attributes=True)