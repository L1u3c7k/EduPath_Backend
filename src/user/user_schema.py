from datetime import datetime
import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, computed_field
from uuid import UUID
from typing import Optional

from src.user.image_utils import public_image_url

class UserBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.match(r"^[a-zA-Z\s]+$", value):
            raise ValueError(
                "Name can only contain alphabet letters and spaces (no numbers or special characters)"
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_miit_email(cls, v: str) -> str:
        if not v.lower().endswith("@miit.edu.mm"):
            raise ValueError(
                "Registration is restricted to @miit.edu.mm email addresses only."
            )
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    


class UserUpdate(UserBase):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = Field(default=None)
    
    
    
class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    
class UsernameUpdate(BaseModel):
    new_name: str = Field(..., min_length=3, max_length=50)

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
    image_file:str | None = Field(default=None)
    @computed_field
    @property
    def img_url(self) -> Optional[str]:
        return public_image_url(self.image_file)
    model_config = ConfigDict(from_attributes=True)


class UserInLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserWithToken(BaseModel):
    token: str