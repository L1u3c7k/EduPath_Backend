from typing import List
import logging
from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import UnidentifiedImageError
from src.database import get_db
from src.user.user_schema import UserCreate, UserResponse, UserUpdate, UserPasswordUpdate, UsernameUpdate
from src.user.user_service import UserService
from src.auth.utils.dependencies import AccessTokenBearer
from starlette.concurrency import run_in_threadpool
from src.user.image_utils import delete_profile_image, process_profile_image
from src.config import settings
from uuid import UUID
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

user_router = APIRouter()
user_service = UserService()
access_token_bearer = AccessTokenBearer()


@user_router.get("/", response_model=UserResponse)
async def get_user_by_id(
    db: AsyncSession = Depends(get_db), 
    security: dict = Depends(access_token_bearer)
):
    current_user_id = UUID(str(security["user"]["user_id"]))
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
    current_user_id = UUID(str(security["user"]["user_id"]))

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
    current_user_id = UUID(str(security["user"]["user_id"]))
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
    current_user_id = UUID(str(security["user"]["user_id"]))

    current_user = await user_service.get_user_by_id(db, current_user_id)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
        
    return await user_service.change_password(db, current_user, password_data)

@user_router.patch("/upload_picture", response_model=UserResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    security: dict = Depends(access_token_bearer)
):
    current_user_id = UUID(str(security["user"]["user_id"]))
    current_user = await user_service.get_user_by_id(db, current_user_id)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB",
        )

    try:
        new_filename = await run_in_threadpool(
            process_profile_image, content, str(current_user_id)
        )
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.exception("Profile picture upload failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload image to storage: {err}",
        ) from err

    old_filename = current_user.image_file

    current_user.image_file = new_filename
    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        try:
            delete_profile_image(old_filename)
        except Exception:
            pass # Log exception here so DB state remains consistent

    return current_user


@user_router.delete("/delete-picture", response_model=UserResponse)
async def delete_user_picture(
    
    db: AsyncSession = Depends(get_db),
    security: dict = Depends(access_token_bearer)
):
    current_user_id = UUID(str(security["user"]["user_id"]))
    current_user = await user_service.get_user_by_id(db, current_user_id)

    

    old_filename = current_user.image_file

    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete",
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)

    return current_user

@user_router.patch("/change_username", response_model=UserResponse)
async def update_username(
    payload: UsernameUpdate,
    db: AsyncSession = Depends(get_db),
    security: dict = Depends(access_token_bearer)
):
    current_user_id = UUID(str(security["user"]["user_id"]))
    current_user = await user_service.get_user_by_id(db, current_user_id)

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )

    if payload.new_name == current_user.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New username must be different from current username"
        )

    current_user.name = payload.new_name

    try:
        await db.commit()
        await db.refresh(current_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken"
        )

    return current_user