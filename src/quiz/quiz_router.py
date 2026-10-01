import json
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.database import get_db, get_redis
from src.auth.utils.dependencies import AccessTokenBearer
from src.chat.model.chat_model import Chat
from src.quiz.quiz_service import QuizService
from src.chat.chat_service import ChatService 
from src.quiz.quiz_schema import SingleAnswerSubmission  

logger = logging.getLogger(__name__)

quiz_router = APIRouter()
quiz_service = QuizService()
chat_service = ChatService()
access_token_bearer = AccessTokenBearer()


@quiz_router.post("/{chat_id}/generate", response_model=dict)
async def generate_quiz_session(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer)
):
    user_id = UUID(security["user"]["user_id"])
    session_key = f"quiz:{str(user_id).lower()}:{str(chat_id).lower()}"

    # 1. Check if an active quiz already exists in Redis
    if await redis_client.exists(session_key):
        raw_session = await redis_client.get(session_key)
        return {
            "message": "An active quiz session already exists.",
            "quiz": json.loads(raw_session)
        }

    # 2. Verify chat ownership
    chat_stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == security["user"]["user_id"])
    chat_result = await db.execute(chat_stmt)
    chat_record = chat_result.scalar_one_or_none()

    if not chat_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied."
        )

    # 3. Initialize quiz in Redis
    session_data = await quiz_service.initialize_quiz_session(
        redis_client=redis_client,
        user_id=user_id,
        chat_id=chat_id,
        topic_title=getattr(chat_record, "title", "General Chat")
    )

    return {
        "message": "Quiz session generated successfully.",
        "quiz": session_data
    }


@quiz_router.post("/{chat_id}/submit-item", response_model=dict)
async def submit_quiz_answer(
    chat_id: UUID,
    payload: SingleAnswerSubmission,
    db = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer)
):
    user_id = UUID(security["user"]["user_id"])

    updated_question = await quiz_service.evaluate_and_update_question(
        redis_client=redis_client,
        db = db,
        user_id=user_id,
        chat_id=chat_id,
        question_id=payload.question_id,
        user_answer=payload.user_answer,

    )

    return {
        "message": "Answer submitted and evaluated successfully.",
        "question": updated_question
    }


