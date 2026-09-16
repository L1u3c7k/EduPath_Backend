from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.user.user_schema import UserCreate, UserResponse, UserUpdate, UserPasswordUpdate
from src.user.user_service import UserService
from src.auth.utils.dependencies import AccessTokenBearer

user_router = APIRouter()
user_service = UserService()
access_token_bearer = AccessTokenBearer()


@user_router.get("/", response_model=UserResponse)
async def get_user_by_id(
    db: AsyncSession = Depends(get_db), 
    security: dict = Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    user = await user_service.get_user_by_id(db, current_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
    return user


@user_router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    user_data: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    existing_user = await user_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User already exists"
        )

    return await user_service.create_user(db, user_data)


@user_router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    db: AsyncSession = Depends(get_db), 
    security: dict = Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])

    user = await user_service.get_user_by_id(db, current_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )

    await user_service.delete_user(db, user)


@user_router.patch("/profile", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    security: dict = Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    current_user = await user_service.get_user_by_id(db, current_user_id)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
        
    return await user_service.update_user(db, current_user.id, user_data)


@user_router.patch("/change-password")
async def change_password(
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    security: dict = Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])

    current_user = await user_service.get_user_by_id(db, current_user_id)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
        
    return await user_service.change_password(db, current_user, password_data)