import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis  # ✅ Async module
from dotenv import load_dotenv

from src.auth.auth_router import authRouter
from src.chat.chats_router import chat_router
from src.database import Base, engine
from src.user.users_router import user_router
from src.quiz.quiz_router import quiz_router

load_dotenv()
version = "v1"

# Global reference for Redis client
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server starting...")

    # 1. Initialize Database Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Assign the Redis client directly to app.state.redis
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    app.state.redis = aioredis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=redis_port,
        username=os.getenv("REDIS_USERNAME"),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
    )

    try:
        # Ping the client after assigning it to state
        is_alive = await app.state.redis.ping()
        if is_alive:
            print("Connected to Redis Cloud successfully!")
    except Exception as e:
        print("Redis Cloud connection failed:", e)

    yield  # Application runs here

    print("Server shutting down...")
    # Clean up resources safely
    if getattr(app.state, "redis", None):
        await app.state.redis.aclose()
        print("Redis connection closed.")

    await engine.dispose()


app = FastAPI(
    title="EduPath Backend",
    description="A REST API for RAG",
    version=version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix=f"/api/{version}/user", tags=["user"])
app.include_router(authRouter, prefix=f"/api/{version}/auth", tags=["auth"])
app.include_router(chat_router, prefix=f"/api/{version}/chat", tags=["chat"])

app.include_router(quiz_router, prefix=f"/api/{version}/quiz", tags=["quiz"])