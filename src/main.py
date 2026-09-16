from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from src.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from src.auth.auth_router import authRouter
from src.user.users_router import user_router
from src.chat.chats_router import chat_router
from sse_starlette.sse import EventSourceResponse# Double-check this matches your real import path
from src.ai_model.rag.embedding import init_embedding_model # Import the function to 

version = "v1"

# 1. Define the async startup sequence
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"server is starting")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"Loading embedding model...")
    init_embedding_model()  
    yield
    print(f"server has been stopped")

# 2. Instantiate the FastAPI app with the lifespan hook
app = FastAPI(
    title="EduPath Backend",
    description="A REST API for RAG",
    version=version,
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],  # Adjust to specific domains in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix=f"/api/{version}/user", tags=["user"])
app.include_router(authRouter, prefix=f"/api/{version}/auth", tags=["auth"])
app.include_router(chat_router, prefix=f"/api/{version}/chat", tags=["chat"])


