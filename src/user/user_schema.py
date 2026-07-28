from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field,field_validator, ValidationInfo

class UserBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    email: EmailStr

    @field_validator('name')
    @classmethod
    def username_must_be_alphabet(cls, value: str) -> str:
        # Check if the string contains only alphabet letters
        if not value.isalpha():
            raise ValueError('Username must contain only alphabet letters')
        return value


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    @field_validator('email')
    @classmethod
    def validate_miit_email(cls, v: str) -> str:
        # Convert to lowercase to prevent case-sensitivity workarounds (e.g., @Miit.Edu.Mm)
        if not v.lower().endswith('@miit.edu.mm'):
            raise ValueError('Registration is restricted to @miit.edu.mm email addresses only.')
        return v


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserResponse(UserBase):
    id: int
    password:str 
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserInLogin(BaseModel):
    email:EmailStr
    password:str = Field(min_length=8, max_length=128)


class UserWithToken(BaseModel):
    token:str
