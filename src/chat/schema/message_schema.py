from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    message: str = Field(min_length=1)


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    message: str = Field(default=None, min_length=1)


class MessageResponse(MessageBase):
    id: int
    created_at: datetime
    role: str

    chapter: str | None
    topic: str | None
    subtopic: str | None

    model_config = ConfigDict(from_attributes=True)