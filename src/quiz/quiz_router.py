import json
import logging
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db, get_redis
from src.auth.utils.dependencies import AccessTokenBearer
from src.chat.model.chat_model import Chat
from src.quiz import quiz_service
from src.question.schema.question_schema import QuizAnswerRequest


logger = logging.getLogger(__name__)

quiz_router = APIRouter()

access_token_bearer = AccessTokenBearer()


# ============================================================
# GENERATE QUIZ
# ============================================================

@quiz_router.post(
    "/{chat_id}/generate",
    response_model=dict,
)
async def generate_quiz_session(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):

    # --------------------------------------------------------
    # User ID is UUID
    # --------------------------------------------------------

    user_id = UUID(
        security["user"]["user_id"]
    )

    # --------------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------------

    chat_stmt = select(Chat).where(
        Chat.id == chat_id,
        Chat.user_id == user_id,
    )

    chat_result = await db.execute(
        chat_stmt
    )

    chat_record = (
        chat_result.scalar_one_or_none()
    )

    if not chat_record:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    # --------------------------------------------------------
    # Generate quiz
    # --------------------------------------------------------

    quiz_data, error = (
        await quiz_service.generate_quiz_batch(
            db=db,
            redis_client=redis_client,
            chat=chat_record,
        )
    )

    if error:

        # Active quiz is not really an HTTP error.
        if quiz_data is not None:
            return {
                "message": error,
                "quiz": quiz_data,
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    return {
        "message": "Quiz generated successfully.",
        "quiz": quiz_data,
    }


# ============================================================
# GET ACTIVE QUIZ
# ============================================================

@quiz_router.get(
    "/{chat_id}/active",
    response_model=dict,
)
async def get_active_quiz(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):

    user_id = UUID(
        security["user"]["user_id"]
    )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    chat_stmt = select(Chat).where(
        Chat.id == chat_id,
        Chat.user_id == user_id,
    )

    chat_result = await db.execute(
        chat_stmt
    )

    chat_record = (
        chat_result.scalar_one_or_none()
    )

    if not chat_record:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    # --------------------------------------------------------
    # Get Redis quiz
    # --------------------------------------------------------

    quiz_data = await quiz_service.get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
    )

    if quiz_data is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active quiz found.",
        )

    return {
        "quiz": quiz_data,
    }


# ============================================================
# GET ONE ACTIVE QUESTION
# ============================================================

@quiz_router.get(
    "/{chat_id}/question/{question_number}",
    response_model=dict,
)
async def get_active_question(
    chat_id: UUID,
    question_number: int,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):

    user_id = UUID(
        security["user"]["user_id"]
    )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    chat_stmt = select(Chat).where(
        Chat.id == chat_id,
        Chat.user_id == user_id,
    )

    chat_result = await db.execute(
        chat_stmt
    )

    chat_record = (
        chat_result.scalar_one_or_none()
    )

    if not chat_record:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    # --------------------------------------------------------
    # Get Redis quiz
    # --------------------------------------------------------

    quiz_data = await quiz_service.get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
    )

    if quiz_data is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active quiz found.",
        )

    # --------------------------------------------------------
    # Find question
    # --------------------------------------------------------

    question = quiz_service.get_redis_question(
        quiz_data=quiz_data,
        question_number=question_number,
    )

    return {
        "question": question,
    }


# ============================================================
# ANSWER QUESTION
# ============================================================

@quiz_router.post(
    "/{chat_id}/question/{question_number}/answer",
    response_model=dict,
)
async def answer_quiz_question(
    chat_id: UUID,
    question_number: int,
    payload: QuizAnswerRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    security: dict = Depends(access_token_bearer),
):

    user_id = UUID(
        security["user"]["user_id"]
    )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    chat_stmt = select(Chat).where(
        Chat.id == chat_id,
        Chat.user_id == user_id,
    )

    chat_result = await db.execute(
        chat_stmt
    )

    chat_record = (
        chat_result.scalar_one_or_none()
    )

    if not chat_record:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    # --------------------------------------------------------
    # Submit answer
    # --------------------------------------------------------

    result = await quiz_service.answer_question(
        db=db,
        redis_client=redis_client,
        chat_id=chat_id,
        question_number=question_number,
        user_answer=payload.answer,
    )

    return {
        "message": "Answer submitted successfully.",
        **result,
    }