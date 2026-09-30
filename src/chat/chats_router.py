from typing import List

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db

from src.chat.schema.chat_schema import (
    ChatCreate,
    ChatResponse,
    ChatBase,
    ChatSessionResponse,
)

from src.chat.schema.message_schema import (
    MessageCreate,
    MessageResponse,
    MessageUpdate,
)

from src.chat.chat_service import ChatService
from src.auth.utils.dependencies import AccessTokenBearer

from src.ai_model.chat.manager import ai_chat

from src.quiz.schema.quiz_schema import QuizResponse
from src.question.schema.question_schema import (
    QuizQuestionResponse,
    QuizAnswerRequest,
    QuizAnswerResponse,
)
from src.question.model.question_model import Question

from src.quiz.quiz_service import (
    get_quiz,
    get_current_question,
    generate_quiz_batch,
    answer_question,
)


chat_router = APIRouter()

chat_service = ChatService()
access_token_bearer = AccessTokenBearer()


@chat_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=List[ChatSessionResponse],
)
async def get_chat_sessions(
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    return await chat_service.get_chat_sessions(
        db=db,
        user_id=current_user_id,
    )


@chat_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatResponse,
)
async def initialize_chat(
    payload: ChatCreate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    # New chat has no subject yet.
    # AI determines the subject and hierarchy from RAG.
    (
        ai_response_text,
        subject,
        hierarchy,
    ) = await ai_chat(
        question=payload.message,
        db=db,
        current_subject=None,
    )

    return await chat_service.create_chat_session(
        db=db,
        user_id=current_user_id,
        user_text=payload.message,
        assistant_text=ai_response_text,
        subject=subject,
        hierarchy=hierarchy,
    )


@chat_router.post(
    "/{chat_id}/msg",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
)
async def continue_chat(
    chat_id: int,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    # First verify that this chat belongs to the current user.
    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found.",
        )

    # The chat's subject is the permanent subject boundary.
    current_subject = chat_history.subject

    (
        ai_response_text,
        subject,
        hierarchy,
    ) = await ai_chat(
        question=payload.message,
        db=db,
        current_subject=current_subject,
    )

    response = await chat_service.add_messages_to_existing_chat(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
        user_text=payload.message,
        assistant_text=ai_response_text,
        subject=subject,
        hierarchy=hierarchy,
    )

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found.",
        )

    return response


@chat_router.get(
    "/{chat_id}",
    status_code=status.HTTP_200_OK,
    response_model=ChatResponse,
)
async def get_all_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found.",
        )

    return chat_history


@chat_router.get(
    "/{chat_id}/latest_user_messages",
    status_code=status.HTTP_200_OK,
    response_model=List[MessageResponse],
)
async def get_latest_user_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    latest_messages = await chat_service.get_latest_chat(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not latest_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "You need at least 5 user messages in this "
                "chat session to perform this action."
            ),
        )

    return latest_messages


@chat_router.patch(
    "/{chat_id}",
    response_model=ChatBase,
)
async def update_title(
    chat_id: int,
    payload: ChatBase,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    updated_chat = await chat_service.update_chat_title(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
        new_title=payload.title,
    )

    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found.",
        )

    return updated_chat


@chat_router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    success = await chat_service.delete_chat(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found.",
        )


@chat_router.patch(
    "/{chat_id}/{message_id}",
    response_model=MessageResponse,
)
async def update_message(
    chat_id: int,
    message_id: int,
    payload: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(security["user"]["user_id"])

    # First verify ownership and get the chat subject.
    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found.",
        )

    current_subject = chat_history.subject

    (
        ai_response_text,
        subject,
        hierarchy,
    ) = await ai_chat(
        question=payload.message,
        db=db,
        current_subject=current_subject,
    )

    updated_response = await chat_service.update_message_in_chat(
        db=db,
        chat_id=chat_id,
        message_id=message_id,
        user_id=current_user_id,
        new_user_text=payload.message,
        new_assistant_text=ai_response_text,
        subject=subject,
        hierarchy=hierarchy,
    )

    if not updated_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Message with ID {message_id} "
                f"in chat {chat_id} not found."
            ),
        )

    return updated_response

@chat_router.post(
    "/{chat_id}/quiz",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizQuestionResponse,
)
async def create_or_extend_quiz(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(
        security["user"]["user_id"]
    )

    # --------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------

    chat = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    # --------------------------------------------------
    # Generate a quiz batch
    # --------------------------------------------------

    quiz, question, error = await generate_quiz_batch(
        db=db,
        chat=chat,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    if quiz is None or question is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz could not be created.",
        )

    await db.commit()

    return question


@chat_router.get(
    "/{chat_id}/quiz",
    status_code=status.HTTP_200_OK,
    response_model=QuizResponse,
)
async def get_chat_quiz(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(
        security["user"]["user_id"]
    )

    # --------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------

    chat = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    quiz = await get_quiz(
        db=db,
        chat_id=chat_id,
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz has not been created yet.",
        )

    return quiz


@chat_router.get(
    "/{chat_id}/quiz/current",
    status_code=status.HTTP_200_OK,
    response_model=QuizQuestionResponse,
)
async def get_current_quiz_question(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(
        security["user"]["user_id"]
    )

    # --------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------

    chat = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    # --------------------------------------------------
    # Get quiz
    # --------------------------------------------------

    quiz = await get_quiz(
        db=db,
        chat_id=chat_id,
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz has not been created yet.",
        )

    # --------------------------------------------------
    # Get current question
    # --------------------------------------------------

    question = await get_current_question(
        db=db,
        quiz=quiz,
    )

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "There is no current question. "
                "Generate another quiz batch."
            ),
        )

    return question


@chat_router.post(
    "/{chat_id}/quiz/{question_id}/answer",
    status_code=status.HTTP_200_OK,
    response_model=QuizAnswerResponse,
)
async def submit_quiz_answer(
    chat_id: int,
    question_id: int,
    payload: QuizAnswerRequest,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = int(
        security["user"]["user_id"]
    )

    # --------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------

    chat = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    # --------------------------------------------------
    # Get quiz
    # --------------------------------------------------

    quiz = await get_quiz(
        db=db,
        chat_id=chat_id,
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz has not been created yet.",
        )

    # --------------------------------------------------
    # Get the requested question
    # --------------------------------------------------

    result = await db.execute(
        select(Question)
        .where(
            Question.id == question_id,
            Question.quiz_id == quiz.id,
        )
    )

    question = result.scalar_one_or_none()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )

    # --------------------------------------------------
    # Make sure this is the current question
    # --------------------------------------------------

    if (
        question.question_number
        != quiz.current_question
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This is not the current quiz question."
            ),
        )

    # --------------------------------------------------
    # Evaluate and save the attempt
    # --------------------------------------------------

    result = await answer_question(
        db=db,
        quiz=quiz,
        question=question,
        user_answer=payload.answer,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    await db.commit()

    return result