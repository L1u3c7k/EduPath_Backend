from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from src.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from src.auth.auth_router import authRouter
from src.user.users_router import user_router
from src.chat.chats_router import chat_router
from sse_starlette.sse import EventSourceResponse# Double-check this matches your real import path
# from src.chat.stream import get_gemini_stream

version = "v1"

# 1. Define the async startup sequence
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"server is starting")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    allow_origins=["*"],  # Adjust to specific domains in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# @app.post("/api/chat")
# async def chat_stream(request: Request):
#     raw_body = await request.body()
#     print("--- RAW INCOMING BODY ---")
#     print(raw_body.decode("utf-8")) # This will print to your terminal console
#     print("-------------------------")

#     try:
#         # 2. Try to parse it as JSON
#         body = await request.json()
#     except Exception as e:
#         # If it fails, we return a helpful error instead of crashing the server
#         return {
#             "error": "Invalid JSON format sent in request body.",
#             "details": str(e),
#             "raw_body_received": raw_body.decode("utf-8")
#         }

#     messages = body.get("messages", [])
#     return EventSourceResponse(get_gemini_stream(request, messages))
app.include_router(user_router, prefix=f"/api/{version}/users", tags=["user"])

# 3. Register your routers
app.include_router(authRouter, prefix=f"/api/{version}/auth", tags=["auth"])



app.include_router(chat_router, prefix=f"/api/{version}/chat", tags=["chat"])


