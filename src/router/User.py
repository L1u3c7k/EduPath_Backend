from datetime import datetime, timezone
from typing import List
from fastapi import Depends
from src.database import get_db
from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException
from src.schemas import *
from src.mockData.userData import users
from sqlalchemy.orm import Session
from src.models import User
from sqlalchemy import select
user_router = APIRouter()


@user_router.get("/", response_model=List[UserResponse])
async def get_users():
    return users


@user_router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int,db:Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(user_data: UserCreate,db:Session = Depends(get_db)):
    existing_user = db.execute(select(User).where(User.email == user_data.email)).scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )
    new_user = User(**user_data.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
