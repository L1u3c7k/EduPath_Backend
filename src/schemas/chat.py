from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatBase(BaseModel):
    user_id: int
    title: str | None = Field(default=None, max_length=255)


class ChatCreate(ChatBase):
    pass


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatResponse(ChatBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
