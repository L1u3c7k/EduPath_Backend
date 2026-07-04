from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
