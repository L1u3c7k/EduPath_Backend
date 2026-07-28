from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.chat.schema.chat_schema import ChatCreate, ChatResponse
from src.chat.schema.message_schema import MessageCreate, MessageResponse
from fastapi import HTTPException
from src.chat.chat_service import ChatService
from src.auth.utils.dependencies import AccessTokenBearer  

chat_router = APIRouter()
chat_service = ChatService()
access_token_bearer = AccessTokenBearer()  

@chat_router.post("/", status_code=status.HTTP_201_CREATED, response_model=ChatResponse)
async def initialize_chat(
    payload: ChatCreate, 
    db: AsyncSession = Depends(get_db),security=Depends(access_token_bearer)
):
    current_user_id = int(security["user"]["user_id"])
    print(security)
    
    # Generate response text from LLM provider
    ai_response_text = f"Hello! This is an AI response to: '{payload.message}'"
    
    # The service returns a fully hydrated Chat model instance (with relationship data)
    new_chat = await chat_service.create_chat_session(
        db=db, 
        user_id=current_user_id, 
        user_text=payload.message,
        assistant_text=ai_response_text
    )
    return new_chat


@chat_router.post("/{chat_id}/msg", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
async def continue_chat(
    chat_id: int,
    payload: MessageCreate, 
    db: AsyncSession = Depends(get_db),
    security=Depends(access_token_bearer)
):
    ai_response_text = f"Continuing context. Answer to: '{payload.content}'"
    
    # Save messages and return the specific assistant response back to the client
    assistant_message = await chat_service.add_messages_to_existing_chat(
        db=db,
        chat_id=chat_id,
        user_text=payload.content,
        assistant_text=ai_response_text
    )
    return assistant_message

@chat_router.get("/{chat_id}", status_code=status.HTTP_200_OK, response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db)
):
    # Call our new service method
    chat_history = await chat_service.get_chat_with_history(db=db, chat_id=chat_id)
    
    # If the database returned nothing, throw a clean 404 error
    if not chat_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {chat_id} not found."
        )
        
    return chat_history