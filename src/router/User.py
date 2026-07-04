from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException

from src.schemas import *
from src.mockData.userData import users

user_router = APIRouter()


@user_router.get("/", response_model=List[UserResponse])
async def get_users():
    return users


@user_router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


@user_router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(user_data: UserCreate):
    now = datetime.now(timezone.utc)
    new_user = {
        "id": max((user["id"] for user in users), default=100) + 1,
        "name": user_data.name,
        "email": user_data.email,
        "password_hash": user_data.password,
        "created_at": now,
        "updated_at": now,
    }
    users.append(new_user)
    return new_user
