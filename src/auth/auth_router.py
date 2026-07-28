from fastapi import APIRouter, Depends, HTTPException, status
from src.user.user_schema import UserInLogin,UserCreate,UserResponse
from src.auth.utils.utils import decode_token,create_access_token,verify_password
from src.user.user_service import UserService
from src.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from src.config import settings
from datetime import timedelta
from src.user.user_model import User
from src.auth.utils.dependencies import RefreshTokenBearer
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
import hashlib

authRouter = APIRouter()
user_service = UserService()
refresh_token = RefreshTokenBearer()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

@authRouter.post("/login")
async def login(loginDetails: UserInLogin, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user_by_email(db, loginDetails.email)

    if user and verify_password(loginDetails.password, user.password):
        # 1. Create the tokens
        access_token = create_access_token(user_data={"email": user.email, "user_id": str(user.id)})
        
        refresh_expiry = timedelta(days=7)
        refresh_token = create_access_token(
            user_data={"email": user.email, "user_id": str(user.id)},
            refresh=True,
            expiry=refresh_expiry
        )

        # 2. Save token hash & expiry to the DB model
        user.refresh_token = hash_token(refresh_token)
        user.refresh_token_expires_at = datetime.now(timezone.utc) + refresh_expiry
        
        # 3. Commit changes to the DB
        await db.commit()

        return JSONResponse(
            content={
                "message": "Login Successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )


@authRouter.post("/signup",response_model=UserResponse)
async def signUp(signUpDetails: UserCreate,db:AsyncSession =Depends(get_db)):
  email = signUpDetails.email
  print(email)
  user_exists = await user_service.user_exists(email,db)
  if user_exists:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="User with email already exits")
  
  new_user = await user_service.create_user(db,signUpDetails)

  return new_user


@authRouter.post("/refresh_token")
async def get_new_access_token(token_details:dict = Depends(refresh_token)):
  expirey_timeStamp = token_details["exp"]
  if datetime.fromtimestamp(expirey_timeStamp)> datetime.now():
    new_access_token = create_access_token(
      user_data= token_details["user"]
    )
    return JSONResponse(
      content={
        
        "access_token":new_access_token
      }
    )
  raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Refresh token expired")

@authRouter.post("/logout")
async def logout(
    token_details: dict = Depends(refresh_token),
    db: AsyncSession = Depends(get_db)
):
    user_id = int(token_details["user"]["user_id"])
    
    # 1. Fetch user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user:
        # 2. Clear token data from DB (Revokes token)
        user.refresh_token = None
        user.refresh_token_expires_at = None
        
        # 3. Commit changes to DB
        await db.commit()

    return JSONResponse(content={"message": "Logged out successfully"})