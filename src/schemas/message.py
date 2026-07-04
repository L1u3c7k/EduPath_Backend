from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    chat_id: int
    role: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
