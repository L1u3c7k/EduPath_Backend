from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_model.chat.manager import ai_chat
from src.auth.utils.dependencies import AccessTokenBearer
from src.chat.chat_service import ChatService
from src.chat.schema.chat_schema import (
    ChatBase,
    ChatCreate,
    ChatResponse,
    ChatSessionResponse,
)
from src.chat.schema.message_schema import (
    MessageCreate,
    MessageResponse,
    MessageUpdate,
)
from src.database import get_db


chat_router = APIRouter()

chat_service = ChatService()
access_token_bearer = AccessTokenBearer()


# ============================================================
# GET CHAT SESSIONS
# ============================================================

@chat_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=List[ChatSessionResponse],
)
async def get_chat_sessions(
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    return await chat_service.get_chat_sessions(
        db=db,
        user_id=current_user_id,
    )


# ============================================================
# CREATE CHAT
# ============================================================

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
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    # --------------------------------------------------------
    # A new chat has no subject yet.
    #
    # AI determines the subject, hierarchy, and RAG sources.
    # --------------------------------------------------------

    (
        ai_response_text,
        subject,
        hierarchy,
        source_documents,
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
        source_documents=source_documents,
    )


# ============================================================
# CONTINUE CHAT
# ============================================================

@chat_router.post(
    "/{chat_id}/msg",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
)
async def continue_chat(
    chat_id: UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    # --------------------------------------------------------
    # Verify chat ownership and retrieve current subject.
    # --------------------------------------------------------

    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    # --------------------------------------------------------
    # Subject is the permanent boundary of this chat.
    # --------------------------------------------------------

    current_subject = chat_history.subject

    (
        ai_response_text,
        subject,
        hierarchy,
        source_documents,
    ) = await ai_chat(
        question=payload.message,
        db=db,
        current_subject=current_subject,
    )

    response = (
        await chat_service.add_messages_to_existing_chat(
            db=db,
            chat_id=chat_id,
            user_id=current_user_id,
            user_text=payload.message,
            assistant_text=ai_response_text,
            subject=subject,
            hierarchy=hierarchy,
            source_documents=source_documents,
        )
    )

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    return response


# ============================================================
# GET CHAT HISTORY
# ============================================================

@chat_router.get(
    "/{chat_id}",
    status_code=status.HTTP_200_OK,
    response_model=ChatResponse,
)
async def get_all_messages(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    return chat_history


# ============================================================
# GET LATEST USER MESSAGES
# ============================================================

@chat_router.get(
    "/{chat_id}/latest_user_messages",
    status_code=status.HTTP_200_OK,
    response_model=List[MessageResponse],
)
async def get_latest_user_messages(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

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


# ============================================================
# UPDATE CHAT TITLE
# ============================================================

@chat_router.patch(
    "/{chat_id}",
    response_model=ChatBase,
)
async def update_title(
    chat_id: UUID,
    payload: ChatBase,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    updated_chat = await chat_service.update_chat_title(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
        new_title=payload.title,
    )

    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat with ID "
                f"{chat_id} not found."
            ),
        )

    return updated_chat


# ============================================================
# DELETE CHAT
# ============================================================

@chat_router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    success = await chat_service.delete_chat(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat with ID "
                f"{chat_id} not found."
            ),
        )

    return None


# ============================================================
# UPDATE MESSAGE
# ============================================================

@chat_router.patch(
    "/{chat_id}/{message_id}",
    response_model=MessageResponse,
)
async def update_message(
    chat_id: UUID,
    message_id: UUID,
    payload: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer),
):
    current_user_id = UUID(
        str(
            security["user"]["user_id"]
        )
    )

    # --------------------------------------------------------
    # Verify ownership and get the current chat subject.
    # --------------------------------------------------------

    chat_history = await chat_service.get_chat_with_history(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
    )

    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Chat session with ID "
                f"{chat_id} not found."
            ),
        )

    current_subject = chat_history.subject

    # --------------------------------------------------------
    # Generate the new AI response using the permanent
    # subject boundary.
    # --------------------------------------------------------

    (
        ai_response_text,
        subject,
        hierarchy,
        source_documents,
    ) = await ai_chat(
        question=payload.message,
        db=db,
        current_subject=current_subject,
    )

    updated_response = (
        await chat_service.update_message_in_chat(
            db=db,
            chat_id=chat_id,
            message_id=message_id,
            user_id=current_user_id,
            new_user_text=payload.message,
            new_assistant_text=ai_response_text,
            subject=subject,
            hierarchy=hierarchy,
            source_documents=source_documents,
        )
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