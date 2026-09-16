from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils.utils import generate_passwd_hash, verify_password
from src.user.user_model import User
from src.user.user_schema import UserCreate, UserPasswordUpdate, UserUpdate


class UserService:
    async def get_users(self, db: AsyncSession):
        statement = select(User)
        result = await db.execute(statement)
        return result.scalars().all()

    async def get_user_by_email(self, db: AsyncSession, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_user_by_id(self, db: AsyncSession, id: str) -> User | None:
        statement = select(User).where(User.id == id)
        result = await db.execute(statement)
        return result.scalars().first()

    async def user_exists(self, db: AsyncSession, email: str) -> bool:
        user = await self.get_user_by_email(db, email)
        return user is not None

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> User:
        user_dict = user_data.model_dump()
        
        # Hash password before storing
        password = user_dict.pop("password")
        hashed_password = generate_passwd_hash(password)

        new_user = User(**user_dict, password=hashed_password)

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    async def update_user(self, db: AsyncSession, user_id: str, user_data: UserUpdate) -> User:
        user = await self.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )

        update_dict = user_data.model_dump(exclude_unset=True)

        # Handle Email Update & Duplication Checks
        if "email" in update_dict and update_dict["email"] is not None:
            new_email = update_dict["email"]

            if new_email == user.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New email cannot be the same as your current email.",
                )

            existing_user = await self.get_user_by_email(db, new_email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is already in use by another account.",
                )

        # Dynamically set all remaining update fields on the User model
        for key, value in update_dict.items():
            setattr(user, key, value)

        await db.commit()
        await db.refresh(user)
        return user

    async def delete_user(self, db: AsyncSession, user: User) -> None:
        await db.delete(user)
        await db.commit()

    async def change_password(self, db: AsyncSession, user: User, data: UserPasswordUpdate) -> dict:
        # 1. Verify current password
        if not verify_password(data.current_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Incorrect current password"
            )

        # 2. Prevent setting the same password
        if verify_password(data.new_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be the same as old password",
            )

        # 3. Hash and save
        user.password = generate_passwd_hash(data.new_password)
        await db.commit()
        return {"message": "Password updated successfully"}