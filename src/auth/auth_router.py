import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.utils.dependencies import RefreshTokenBearer
from src.auth.utils.utils import create_access_token, verify_password
from src.config import settings
from src.database import get_db
from src.user.user_model import User
from src.user.user_schema import UserCreate, UserInLogin, UserResponse
from src.user.user_service import UserService

authRouter = APIRouter()
user_service = UserService()
refresh_token_bearer = RefreshTokenBearer()  # Renamed to avoid name shadowing


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@authRouter.post("/login")
async def login(loginDetails: UserInLogin, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user_by_email(db, loginDetails.email)

    if not user or not verify_password(loginDetails.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # 1. Create the tokens
    access_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)}
    )
    
    refresh_expiry = timedelta(days=settings.REFRESH_TOKEN_EXPIRE)
    raw_refresh_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)},
        refresh=True,
        expiry=refresh_expiry
    )

    # 2. Save token hash & expiry to the DB model
    user.refresh_token = hash_token(raw_refresh_token)
    user.refresh_token_expires_at = datetime.now(timezone.utc) + refresh_expiry
    
    # 3. Commit changes
    await db.commit()

    return JSONResponse(
        content={
            "message": "Login Successful",
            "access_token": access_token,
            "refresh_token": raw_refresh_token,
        }
    )


@authRouter.post("/signup", response_model=UserResponse)
async def signUp(signUpDetails: UserCreate, db: AsyncSession = Depends(get_db)):
    user_exists = await user_service.user_exists(signUpDetails.email, db)
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
  
    new_user = await user_service.create_user(db, signUpDetails)
    return new_user


@authRouter.post("/refresh_token")
async def get_new_access_token(
    token_details: dict = Depends(refresh_token_bearer),
    db: AsyncSession = Depends(get_db)
):
    user_id = int(token_details["user"]["user_id"])

    # Verify user exists in database and token wasn't revoked
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token"
        )

    # Check expiration timestamp safely
    if user.refresh_token_expires_at and user.refresh_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    new_access_token = create_access_token(
        user_data={"email": user.email, "user_id": str(user.id)}
    )
    
    return JSONResponse(
        content={
            "access_token": new_access_token
        }
    )


@authRouter.post("/logout")
async def logout(
    token_details: dict = Depends(refresh_token_bearer),
    db: AsyncSession = Depends(get_db)
):
    user_id = int(token_details["user"]["user_id"])
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user:
        user.refresh_token = None
        user.refresh_token_expires_at = None
        await db.commit()

    return JSONResponse(content={"message": "Logged out successfully"})