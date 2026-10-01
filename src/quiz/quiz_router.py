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
from src.quiz.quiz_schema import SingleAnswerSubmission

logger = logging.getLogger(__name__)

quiz_router = APIRouter(prefix="/quiz", tags=["quiz"])
quiz_service = QuizService()
access_token_bearer = AccessTokenBearer()


# --------------------------------------------------
# 1. GENERATE OR FETCH ACTIVE QUIZ SESSION
# --------------------------------------------------
@quiz_router.post("/{chat_id}/generate", response_model=dict)
async def generate_quiz_session(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):
    user_id = UUID(security["user"]["user_id"])

    # Verify chat ownership
    chat_stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    chat_result = await db.execute(chat_stmt)
    chat_record = chat_result.scalar_one_or_none()

    if not chat_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    # Delegate cache lookup, message fetching, and LLM generation to QuizService
    session_data, error = await quiz_service.initialize_quiz_session(
        db=db,
        redis_client=redis_client,
        user_id=user_id,
        chat=chat_record,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    return {
        "message": "Quiz session initialized successfully.",
        "quiz": session_data,
    }


# --------------------------------------------------
# 2. SUBMIT SINGLE ANSWER ITEM (REDIS STATE)
# --------------------------------------------------
@quiz_router.post("/{chat_id}/submit-item", response_model=dict)
async def submit_quiz_answer(
    chat_id: UUID,
    payload: SingleAnswerSubmission,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):
    user_id = UUID(security["user"]["user_id"])

    # Evaluate answer in Redis and persist to PostgreSQL if completed
    evaluation_result = await quiz_service.evaluate_and_update_question(
        db=db,
        redis_client=redis_client,
        user_id=user_id,
        chat_id=chat_id,
        question_id=payload.question_id,
        user_answer=payload.user_answer,
    )

    return {
        "message": "Answer submitted and evaluated successfully.",
        "result": evaluation_result,
    }