from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from src.chat.schema.message_schema import MessageResponse

class ChatBase(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    model_config = ConfigDict(from_attributes=True)


class ChatCreate(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(ChatBase):
    id: int
    user_id: int
    subject: str | None
    created_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)

class ChatSessionResponse(ChatBase):
    id:int
    user_id:int
    subject: str | None