from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.chat.schema.chat_schema import ChatCreate, ChatResponse, ChatBase, ChatSessionResponse
from src.chat.schema.message_schema import MessageCreate, MessageResponse, MessageUpdate
from src.chat.chat_service import ChatService
from src.auth.utils.dependencies import AccessTokenBearer 
from src.ai_model.chat.manager import ai_chat

chat_router = APIRouter()
chat_service = ChatService()
access_token_bearer = AccessTokenBearer()

@chat_router.get("/", status_code=status.HTTP_200_OK, response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    return await chat_service.get_chat_sessions(db=db, user_id=current_user_id)


@chat_router.post("/", status_code=status.HTTP_201_CREATED, response_model=ChatResponse)
async def initialize_chat(
    payload: ChatCreate, 
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    ai_response_text = ai_chat(payload.message);
    # ai_response_text = f"this is the ai Response of {payload.message}"
    
    return await chat_service.create_chat_session(
        db=db, 
        user_id=current_user_id, 
        user_text=payload.message,
        assistant_text=ai_response_text
    )


@chat_router.post("/{chat_id}/msg", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
async def continue_chat(
    chat_id: int,
    payload: MessageCreate, 
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    ai_response_text = ai_chat(payload.message);
    # ai_response_text = f"this is the response of the {payload.message}"
    
    response = await chat_service.add_messages_to_existing_chat(
        db=db,
        chat_id=chat_id,
        user_id=current_user_id,
        user_text=payload.message,
        assistant_text=ai_response_text
    )
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found."
        )
    return response


@chat_router.get("/{chat_id}", status_code=status.HTTP_200_OK, response_model=ChatResponse)
async def get_all_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    
    chat_history = await chat_service.get_chat_with_history(
        db=db, 
        chat_id=chat_id, 
        user_id=current_user_id
    )
    
    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found."
        )
        
    return chat_history


@chat_router.get("/{chat_id}/latest_user_messages", status_code=status.HTTP_200_OK, response_model=List[MessageResponse])
async def get_latest_user_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    latest_messages = await chat_service.get_latest_chat(
        db=db, 
        chat_id=chat_id, 
        user_id=current_user_id
    )
    
    if not latest_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You need at least 5 user messages in this chat session to perform this action."
        )
        
    return latest_messages


@chat_router.patch("/{chat_id}", response_model=ChatBase)
async def update_title(
    chat_id: int,
    payload: ChatBase,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    updated_chat = await chat_service.update_chat_title(
        db=db, 
        chat_id=chat_id, 
        user_id=current_user_id,
        new_title=payload.title
    )
    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found."
        )
    return updated_chat


@chat_router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    success = await chat_service.delete_chat(
        db=db, 
        chat_id=chat_id, 
        user_id=current_user_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found."
        )


@chat_router.patch("/{chat_id}/{message_id}", response_model=MessageResponse)
async def update_message(
    chat_id: int,
    message_id: int,
    payload: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    ai_response_text = ai_chat(payload.message);
    # ai_response_text = f"this is the updated response for: {payload.message}"

    updated_response = await chat_service.update_message_in_chat(
        db=db,
        chat_id=chat_id,
        message_id=message_id,
        user_id=current_user_id,
        new_user_text=payload.message,
        new_assistant_text=ai_response_text
    )

    if not updated_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} in chat {chat_id} not found."
        )

    return updated_response