from sqlalchemy.ext.asyncio import AsyncSession
from src.chat.model.chat_model import Chat
from src.chat.model.message_model import Message
from src.chat.schema.chat_schema import ChatResponse
from sqlalchemy import select
from src.chat.schema.message_schema import MessageResponse
from sqlalchemy.orm import selectinload

class ChatService:
    async def create_chat_session(
        self, db: AsyncSession, user_id: int, user_text: str, assistant_text: str
    ) -> ChatResponse:
        """
        Creates a Chat, appends BOTH the initial user message 
        and the initial assistant response, then commits them together.
        """
        generated_title = user_text[:40] + "..." if len(user_text) > 40 else user_text
        
        try:
            # 1. Instantiate database rows
            new_chat = Chat(title=generated_title, user_id=user_id)
            user_msg = Message(role="user", content=user_text)
            
            assistant_msg = Message(role="assistant", content=assistant_text)
            
            new_chat.messages.append(user_msg)
            new_chat.messages.append(assistant_msg)
            
            # 2. Add and flush to populate IDs
            db.add(new_chat)
            await db.flush()
            
            # 3. Query the fresh data with its relationship loaded
            statement = (
                select(Chat)
                .where(Chat.id == new_chat.id)
                .options(selectinload(Chat.messages))
            )
            result = await db.execute(statement)
            chat_record = result.scalar_one()
            
            # 4. CONVERT TO PYDANTIC OBJECT IMMEDIATELY
            # This safely copies all attributes into regular Python memory
            response_data = ChatResponse.model_validate(chat_record)
            
            # 5. Commit the database transaction permanently
            await db.commit()
            
            # 6. Return the safe Pydantic schema object
            return response_data
            
        except Exception as e:
            await db.rollback()
            raise e
        
    async def add_messages_to_existing_chat(
        self, db: AsyncSession, chat_id: int, user_text: str, assistant_text: str
    ) -> MessageResponse:
        """
        Appends a user and assistant message to an existing chat, 
        and returns the assistant's message formatted via Pydantic.
        """
        try:
            # 1. Instantiate the two message records bound to this chat_id
            user_msg = Message(chat_id=chat_id, role="user", content=user_text)
            assistant_msg = Message(chat_id=chat_id, role="assistant", content=assistant_text)
            

            db.add_all([user_msg, assistant_msg])
            await db.flush()
            response_data = MessageResponse.model_validate(assistant_msg)
            await db.commit()
            return response_data
            
        except Exception as e:
            await db.rollback()
            raise e
        
    async def get_chat_with_history(self, db: AsyncSession, chat_id: int) -> ChatResponse:
        """
        Fetches an existing chat room and all its historical messages,
        returning it formatted safely as a Pydantic ChatResponse.
        """
        # Query the chat and eagerly load the messages relationship
        statement = (
            select(Chat)
            .where(Chat.id == chat_id)
            .options(selectinload(Chat.messages))
        )
        result = await db.execute(statement)
        chat_record = result.scalar_one_or_none()
        
        # If the chat ID doesn't exist in the database, return None
        if not chat_record:
            return None
            
        # Safely validate into your Pydantic schema before returning
        return ChatResponse.model_validate(chat_record)