import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.utils.utils import create_access_token, decode_token, verify_password
from src.config import settings
from src.database import get_db
from src.user.user_model import User
from src.user.user_schema import UserCreate, UserInLogin, UserResponse
from src.user.user_service import UserService

authRouter = APIRouter()
user_service = UserService()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@authRouter.post("/login")
async def login(
    loginDetails: UserInLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user_by_email(db, loginDetails.email)

    if not user or not verify_password(loginDetails.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 1. Create access token
    access_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)},expiry=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE)
    )

    # 2. Create refresh token
    refresh_expiry = settings.REFRESH_TOKEN_EXPIRE
    raw_refresh_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)},
        refresh=True,
        expiry=timedelta(days=refresh_expiry),
    )

    # 3. Save token hash & expiry to DB
    user.refresh_token = hash_token(raw_refresh_token)
    user.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(days=refresh_expiry)
    await db.commit()

    # 4. Attach refresh token as HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=getattr(settings, "COOKIE_SECURE", False),
        samesite="lax",
        max_age=int(timedelta(days=refresh_expiry).total_seconds()),
        path="/",
    )

    return {"message": "Login Successful", "access_token": access_token}


@authRouter.post("/signup", response_model=UserResponse)
async def signUp(signUpDetails: UserCreate, db: AsyncSession = Depends(get_db)):
    user_exists = await user_service.user_exists( db,signUpDetails.email)
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    new_user = await user_service.create_user(db, signUpDetails)
    return new_user


@authRouter.post("/refresh_token")
async def get_new_access_token(
    request: Request, db: AsyncSession = Depends(get_db)
):
    raw_refresh_token = request.cookies.get("refresh_token")

    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookies",
        )

    token_data = decode_token(raw_refresh_token)

    if not token_data or token_data.get("refresh") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only refresh tokens are allowed on this endpoint",
        )

    user_id = int(token_data["user"]["user_id"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    incoming_hash = hash_token(raw_refresh_token)
    if not user or user.refresh_token != incoming_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    if user.refresh_token_expires_at:
        expires_at = user.refresh_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

    new_access_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)},expiry=timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE)
    )

    return {"access_token": new_access_token}


@authRouter.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    raw_refresh_token = request.cookies.get("refresh_token")
    if raw_refresh_token:
        token_data = decode_token(raw_refresh_token)
        if token_data and "user" in token_data:
            user_id = int(token_data["user"]["user_id"])
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            if user:
                user.refresh_token = None
                user.refresh_token_expires_at = None
                await db.commit()

    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully"}