from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.user.user_model import User
from src.user.user_schema import UserCreate, UserUpdate
from src.auth.utils.utils import generate_passwd_hash






# def get_user_by_id(db: Session, user_id: int) -> User | None:
#     return base.get_by_id(db, User, user_id)


# def get_user_by_email(db: Session, email: str) -> User | None:
#     return db.execute(select(User).where(User.email == email)).scalars().first()


# def create_user(db: Session, user_data: UserCreate) -> User:
#     return base.create(db, User, user_data)


# def update_user(db: Session, user: User, user_data: UserUpdate) -> User:
#     return base.update(db, user, user_data)


# def delete_user(db: Session, user: User) -> None:
#     base.delete(db, user)

class UserService:
  async def get_users(self,db:AsyncSession):
    statement= select(User)
    result = await db.execute(statement)
    return result.scalars().all()
  

  async def get_user_by_email(self,db:AsyncSession,email:str):
    statement = select(User).where(User.email == email)
    result = await db.execute(statement)
    user = result.scalars().first()
    
    return user
    
  
  async def user_exists(self,db:AsyncSession,email):
    user =await self.get_user_by_email(email,db)
    return True if user is not None else False
  
  async def create_user(self,db:AsyncSession,user_data:UserCreate):
    user_data_dict = user_data.model_dump()
    new_user = User(
      **user_data_dict
    )
    new_user.password = generate_passwd_hash(user_data_dict["password"])

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


    

