from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.utils.dependencies import AccessTokenBearer
from src.chat.model.chat_model import Chat
from src.database import get_db, get_redis
from src.question.schema.question_schema import QuizAnswerRequest
from src.quiz import quiz_service


quiz_router = APIRouter()

access_token_bearer = AccessTokenBearer()


# ============================================================
# HELPERS
# ============================================================

def get_user_id_from_security(
    security: dict,
) -> UUID:
    """
    Extract and validate the authenticated user's UUID
    from the access token payload.
    """

    try:
        return UUID(
            str(
                security["user"]["user_id"]
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )


async def get_owned_chat(
    db: AsyncSession,
    chat_id: UUID,
    user_id: UUID,
) -> Chat:
    """
    Verify that the requested chat exists and belongs
    to the authenticated user.
    """

    result = await db.execute(
        select(Chat).where(
            Chat.id == chat_id,
            Chat.user_id == user_id,
        )
    )

    chat = (
        result.scalar_one_or_none()
    )

    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or permission denied.",
        )

    return chat


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
    """
    Generate a new quiz batch for a chat.

    The quiz service handles:

    - first quiz generation
    - additional quiz generation
    - five-message batch requirement
    - duplicate question prevention
    - Redis active quiz state
    """

    user_id = get_user_id_from_security(
        security
    )

    chat_record = await get_owned_chat(
        db=db,
        chat_id=chat_id,
        user_id=user_id,
    )

    quiz_data, error = (
        await quiz_service.generate_quiz_batch(
            db=db,
            redis_client=redis_client,
            chat=chat_record,
            user_id=user_id,
        )
    )

    # --------------------------------------------------------
    # Service returned an error/message.
    #
    # If quiz_data exists, it means an active Redis quiz
    # already exists, so return it normally.
    # --------------------------------------------------------

    if error:

        if quiz_data is not None:
            return {
                "message": error,
                "quiz": quiz_data,
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # --------------------------------------------------------
    # Successful generation
    # --------------------------------------------------------

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
    """
    Return the currently active Redis quiz for a chat.
    """

    user_id = get_user_id_from_security(
        security
    )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    await get_owned_chat(
        db=db,
        chat_id=chat_id,
        user_id=user_id,
    )

    # --------------------------------------------------------
    # Get active Redis quiz
    # --------------------------------------------------------

    quiz_data = await quiz_service.get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
        user_id=user_id,
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
    """
    Return one question from the active Redis quiz.

    Questions are identified by question_number, not by
    PostgreSQL question ID.
    """

    user_id = get_user_id_from_security(
        security
    )

    # --------------------------------------------------------
    # Validate question number
    # --------------------------------------------------------

    if question_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question number must be greater than 0.",
        )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    await get_owned_chat(
        db=db,
        chat_id=chat_id,
        user_id=user_id,
    )

    # --------------------------------------------------------
    # Get active quiz
    # --------------------------------------------------------

    quiz_data = await quiz_service.get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
        user_id=user_id,
    )

    if quiz_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active quiz found.",
        )

    # --------------------------------------------------------
    # Find question
    #
    # get_redis_question() raises 404 when the question
    # number does not exist.
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
    """
    Submit an answer for one question.

    The quiz service handles:

    - answering questions in any order
    - maximum three attempts
    - evaluation failures
    - correct answers
    - wrong attempt 1
    - wrong attempt 2
    - wrong attempt 3
    - question completion
    - complete quiz detection
    - PostgreSQL persistence
    - Redis deletion after successful commit
    """

    user_id = get_user_id_from_security(
        security
    )

    # --------------------------------------------------------
    # Validate question number
    # --------------------------------------------------------

    if question_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question number must be greater than 0.",
        )

    # --------------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------------

    await get_owned_chat(
        db=db,
        chat_id=chat_id,
        user_id=user_id,
    )

    # --------------------------------------------------------
    # Submit answer
    # --------------------------------------------------------

    result = await quiz_service.answer_question(
        db=db,
        redis_client=redis_client,
        chat_id=chat_id,
        user_id=user_id,
        question_number=question_number,
        user_answer=payload.answer,
    )

    return {
        "message": "Answer submitted successfully.",
        **result,
    }