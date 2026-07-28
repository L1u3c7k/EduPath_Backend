import bcrypt
import jwt
from datetime import timedelta,datetime
from src.config import settings
import uuid
import logging

def generate_passwd_hash(password: str) -> str:
    # 1. Convert the string password to bytes
    password_bytes = password.encode('utf-8')
    
    # 2. Generate a secure salt
    salt = bcrypt.gensalt()
    
    # 3. Hash the password and decode the final result back to a string for your DB
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Helper to check passwords later during login
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def create_access_token(user_data:dict,expiry:timedelta = None,refresh:bool=False):
    payload ={}
    payload["user"] = user_data
    payload["exp"] = datetime.now()+(expiry if expiry is not None else timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE))
    payload["jti"] =str(uuid.uuid4())

    payload["refresh"] = refresh

    token = jwt.encode(
        payload = payload,
        key=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return token

def decode_token(token:str) ->dict:
    try:
        token_data = jwt.decode(
            jwt = token,
            key=settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return token_data
    except jwt.PyJWKError as e:
        logging.exception(e)
        return None
        