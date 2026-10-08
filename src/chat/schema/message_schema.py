from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Optional

class MessageBase(BaseModel):
    message: str = Field(min_length=1)


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    message: str = Field(default=None, min_length=1)


class MessageResponse(MessageBase):
    id: UUID
    created_at: datetime
    role: str

    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None

    quiz_ready: bool = False
    model_config = ConfigDict(from_attributes=True)