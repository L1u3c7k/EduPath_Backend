from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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

    source_documents: list[dict] | None = None

    quiz_ready: bool = False

    model_config = ConfigDict(
        from_attributes=True
    )