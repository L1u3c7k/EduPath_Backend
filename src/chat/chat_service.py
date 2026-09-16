from sqlalchemy.ext.asyncio import AsyncSession
from src.chat.model.chat_model import Chat
from src.chat.model.message_model import Message
from src.chat.schema.chat_schema import ChatResponse, ChatBase, ChatCreate
from sqlalchemy import select, update, func
from src.chat.schema.message_schema import MessageResponse
from fastapi import HTTPException, status
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
            new_chat = Chat(title=generated_title, user_id=user_id)
            user_msg = Message(role="user", message=user_text)
            assistant_msg = Message(role="assistant", message=assistant_text)
            
            new_chat.messages.append(user_msg)
            new_chat.messages.append(assistant_msg)
            
            db.add(new_chat)
            await db.flush()
            
            statement = (
                select(Chat)
                .where(Chat.id == new_chat.id, Chat.user_id == user_id)
                .options(selectinload(Chat.messages))
            )
            result = await db.execute(statement)
            chat_record = result.scalar_one()
            
            response_data = ChatResponse.model_validate(chat_record)
            await db.commit()
            return response_data
            
        except Exception as e:
            await db.rollback()
            raise e

    async def get_chat_sessions(self, db: AsyncSession, user_id: int):
        query = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.created_at.desc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_chat_with_history(self, db: AsyncSession, chat_id: int, user_id: int) -> ChatResponse:
        """
        Fetches chat history and enforces user ownership.
        Throws HTTP 403 if the chat exists but belongs to another user.
        """
        statement = (
            select(Chat)
            .where(Chat.id == chat_id)
            .options(selectinload(Chat.messages))
        )
        result = await db.execute(statement)
        chat_record = result.scalar_one_or_none()
        
        if not chat_record:
            return None
            
        # Check ownership
        if chat_record.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this chat session."
            )
            
        return ChatResponse.model_validate(chat_record)
        
    async def add_messages_to_existing_chat(
        self, db: AsyncSession, chat_id: int, user_id: int, user_text: str, assistant_text: str
    ) -> MessageResponse:
        try:
            # Verify chat existence and ownership first
            chat_stmt = select(Chat).where(Chat.id == chat_id)
            chat_result = await db.execute(chat_stmt)
            chat_record = chat_result.scalar_one_or_none()

            if not chat_record:
                return None
            if chat_record.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to modify this chat session."
                )

            user_msg = Message(chat_id=chat_id, role="user", message=user_text)
            assistant_msg = Message(chat_id=chat_id, role="assistant", message=assistant_text)
            
            db.add_all([user_msg, assistant_msg])
            await db.flush()
            
            response_data = MessageResponse.model_validate(assistant_msg)
            await db.commit()
            return response_data
            
        except Exception as e:
            await db.rollback()
            raise e

    async def update_chat_title(self, db: AsyncSession, chat_id: int, user_id: int, new_title: str) -> ChatBase:
        try:
            stmt = (
                update(Chat)
                .where(Chat.id == chat_id, Chat.user_id == user_id)
                .values(title=new_title)
                .returning(Chat)
            )
            result = await db.execute(stmt)
            updated_chat = result.scalar_one_or_none()

            if not updated_chat:
                # Check if chat exists under another user
                check_stmt = select(Chat).where(Chat.id == chat_id)
                if (await db.execute(check_stmt)).scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to update this chat session."
                    )
                return None

            response_data = ChatBase.model_validate(updated_chat)
            await db.commit()
            return response_data

        except Exception as e:
            await db.rollback()
            raise e
    
    async def get_latest_chat(self, db: AsyncSession, chat_id: int, user_id: int) -> list[MessageResponse] | None:
        # Verify ownership
        chat_stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        if not (await db.execute(chat_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this chat session."
            )

        stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.role == "user"
            )
            .order_by(Message.created_at.desc())
            .limit(5)
        )
        
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        if len(messages) < 5:
            return None

        chronological_msgs = list(reversed(messages))
        return [MessageResponse.model_validate(msg) for msg in chronological_msgs]

    async def delete_chat(self, db: AsyncSession, chat_id: int, user_id: int) -> bool:
        try:
            stmt = select(Chat).where(Chat.id == chat_id)
            result = await db.execute(stmt)
            chat_record = result.scalar_one_or_none()

            if not chat_record:
                return False

            if chat_record.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to delete this chat session."
                )

            await db.delete(chat_record)
            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            raise e

    async def update_message_in_chat(
        self,
        db: AsyncSession,
        chat_id: int,
        message_id: int,
        user_id: int,
        new_user_text: str,
        new_assistant_text: str
    ):
        # 1. Guard against null, empty, or whitespace-only inputs
        if not new_user_text or not new_user_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User message content cannot be null or empty."
            )

        # 2. Verify chat ownership
        chat_stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        if not (await db.execute(chat_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update messages in this chat."
            )

        latest_user_stmt = select(func.max(Message.id)).where(
            Message.chat_id == chat_id,
            Message.role == "user"
        )
        latest_result = await db.execute(latest_user_stmt)
        latest_user_msg_id = latest_result.scalar()

        if not latest_user_msg_id:
            return None

        if message_id != latest_user_msg_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only the latest message in the chat can be updated."
            )

        stmt = select(Message).where(
            Message.id == message_id,
            Message.chat_id == chat_id,
            Message.role == "user"
        )
        result = await db.execute(stmt)
        user_message = result.scalars().first()

        # 3. Add safety check if target message is not found
        if not user_message:
            return None

        # 4. Assign non-null text to user message
        user_message.message = new_user_text.strip()

        assistant_stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.role == "assistant",
                Message.id > user_message.id
            )
            .order_by(Message.id.asc()).limit(1)
        )
        assistant_result = await db.execute(assistant_stmt)
        assistant_message = assistant_result.scalars().first()

        if assistant_message:
            assistant_message.message = new_assistant_text
        else:
            assistant_message = Message(
                chat_id=chat_id,
                role="assistant",
                message=new_assistant_text,
            )
            db.add(assistant_message)

        await db.commit()
        await db.refresh(assistant_message)

        return assistant_message