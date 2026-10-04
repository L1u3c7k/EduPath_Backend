from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.chat.model.chat_model import Chat
from src.chat.model.message_model import (
    Message,
    MessageRole,
)
from src.chat.schema.chat_schema import (
    ChatBase,
    ChatCreate,
    ChatResponse,
)
from src.chat.schema.message_schema import MessageResponse
from src.quiz.model.quiz_model import Quiz


class ChatService:

    # ========================================================
    # CREATE CHAT
    # ========================================================

    async def create_chat_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        user_text: str,
        assistant_text: str,
        subject: str | None,
        hierarchy: dict | None,
    ) -> ChatResponse:

        generated_title = (
            user_text[:40] + "..."
            if len(user_text) > 40
            else user_text
        )

        try:
            hierarchy = hierarchy or {}

            new_chat = Chat(
                title=generated_title,
                user_id=user_id,
                subject=subject,
            )

            user_msg = Message(
                role=MessageRole.USER,
                message=user_text,
                chapter=hierarchy.get("chapter"),
                topic=hierarchy.get("topic"),
                subtopic=hierarchy.get("subtopic"),
            )

            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                message=assistant_text,
                chapter=hierarchy.get("chapter"),
                topic=hierarchy.get("topic"),
                subtopic=hierarchy.get("subtopic"),
            )

            new_chat.messages.append(user_msg)
            new_chat.messages.append(assistant_msg)

            db.add(new_chat)

            await db.flush()

            # ------------------------------------------------
            # Reload chat with messages.
            # ------------------------------------------------

            statement = (
                select(Chat)
                .where(
                    Chat.id == new_chat.id,
                    Chat.user_id == user_id,
                )
                .options(
                    selectinload(Chat.messages)
                )
            )

            result = await db.execute(statement)

            chat_record = result.scalar_one()

            response_data = ChatResponse.model_validate(
                chat_record
            )

            await db.commit()

            return response_data

        except Exception:
            await db.rollback()
            raise

    # ========================================================
    # GET CHAT SESSIONS
    # ========================================================

    async def get_chat_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
    ):
        query = (
            select(Chat)
            .where(
                Chat.user_id == user_id
            )
            .order_by(
                Chat.created_at.desc()
            )
        )

        result = await db.execute(query)

        return result.scalars().all()

    # ========================================================
    # GET CHAT WITH HISTORY
    # ========================================================

    async def get_chat_with_history(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user_id: UUID,
    ) -> ChatResponse | None:

        statement = (
            select(Chat)
            .where(
                Chat.id == chat_id
            )
            .options(
                selectinload(Chat.messages)
            )
        )

        result = await db.execute(statement)

        chat_record = (
            result.scalar_one_or_none()
        )

        if not chat_record:
            return None

        if chat_record.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to access "
                    "this chat session."
                ),
            )

        return ChatResponse.model_validate(
            chat_record
        )

    # ========================================================
    # ADD MESSAGES TO EXISTING CHAT
    # ========================================================

    async def add_messages_to_existing_chat(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user_id: UUID,
        user_text: str,
        assistant_text: str,
        subject: str | None,
        hierarchy: dict | None,
    ) -> MessageResponse | None:

        try:
            # ------------------------------------------------
            # Verify chat ownership.
            # ------------------------------------------------

            chat_stmt = (
                select(Chat)
                .where(
                    Chat.id == chat_id
                )
            )

            chat_result = await db.execute(
                chat_stmt
            )

            chat_record = (
                chat_result.scalar_one_or_none()
            )

            if not chat_record:
                return None

            if chat_record.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You do not have permission to modify "
                        "this chat session."
                    ),
                )

            # ------------------------------------------------
            # Preserve the permanent subject boundary.
            #
            # Once a chat has a subject, do not replace it.
            # ------------------------------------------------

            if (
                chat_record.subject is None
                and subject
            ):
                chat_record.subject = subject

            hierarchy = hierarchy or {}

            # ------------------------------------------------
            # Create user message.
            # ------------------------------------------------

            user_msg = Message(
                chat_id=chat_id,
                role=MessageRole.USER,
                message=user_text,
                chapter=hierarchy.get("chapter"),
                topic=hierarchy.get("topic"),
                subtopic=hierarchy.get("subtopic"),
            )

            # ------------------------------------------------
            # Create assistant message.
            # ------------------------------------------------

            assistant_msg = Message(
                chat_id=chat_id,
                role=MessageRole.ASSISTANT,
                message=assistant_text,
                chapter=hierarchy.get("chapter"),
                topic=hierarchy.get("topic"),
                subtopic=hierarchy.get("subtopic"),
            )

            db.add_all(
                [
                    user_msg,
                    assistant_msg,
                ]
            )

            await db.flush()

            # ------------------------------------------------
            # Determine whether enough NEW user messages exist
            # for another quiz batch.
            #
            # The database cursor belongs to the Quiz record.
            # ------------------------------------------------

            quiz_stmt = (
                select(Quiz)
                .where(
                    Quiz.chat_id == chat_id
                )
            )

            quiz_result = await db.execute(
                quiz_stmt
            )

            quiz_record = (
                quiz_result.scalar_one_or_none()
            )

            if quiz_record is None:
                # ------------------------------------------------
                # No quiz has ever been completed.
                #
                # Count all user messages.
                # ------------------------------------------------

                count_stmt = (
                    select(
                        func.count(Message.id)
                    )
                    .where(
                        Message.chat_id == chat_id,
                        Message.role == MessageRole.USER,
                    )
                )

            else:
                # ------------------------------------------------
                # A completed quiz exists.
                #
                # Count user messages chronologically AFTER
                # the quiz cursor.
                # ------------------------------------------------

                if quiz_record.last_message_id is None:

                    count_stmt = (
                        select(
                            func.count(Message.id)
                        )
                        .where(
                            Message.chat_id == chat_id,
                            Message.role == MessageRole.USER,
                        )
                    )

                else:

                    cursor_stmt = (
                        select(Message)
                        .where(
                            Message.id
                            == quiz_record.last_message_id,
                            Message.chat_id
                            == chat_id,
                        )
                    )

                    cursor_result = await db.execute(
                        cursor_stmt
                    )

                    cursor_message = (
                        cursor_result.scalar_one_or_none()
                    )

                    if cursor_message is None:

                        # ------------------------------------------------
                        # Invalid/missing cursor.
                        #
                        # Safest behavior is to count all user messages
                        # rather than silently claiming a batch exists.
                        # ------------------------------------------------

                        count_stmt = (
                            select(
                                func.count(Message.id)
                            )
                            .where(
                                Message.chat_id == chat_id,
                                Message.role == MessageRole.USER,
                            )
                        )

                    else:

                        count_stmt = (
                            select(
                                func.count(Message.id)
                            )
                            .where(
                                Message.chat_id == chat_id,
                                Message.role == MessageRole.USER,
                                or_(
                                    Message.created_at
                                    > cursor_message.created_at,
                                    (
                                        Message.created_at
                                        == cursor_message.created_at
                                    )
                                    & (
                                        Message.id
                                        > cursor_message.id
                                    ),
                                ),
                            )
                        )

            new_user_message_count = (
                await db.execute(
                    count_stmt
                )
            ).scalar() or 0

            is_quiz_ready = (
                new_user_message_count >= 5
            )

            # ------------------------------------------------
            # Build response before commit.
            # ------------------------------------------------

            response_data = MessageResponse(
                id=assistant_msg.id,
                chat_id=assistant_msg.chat_id,
                role=assistant_msg.role,
                message=assistant_msg.message,
                created_at=assistant_msg.created_at,
                quiz_ready=is_quiz_ready,
            )

            await db.commit()

            return response_data

        except Exception:
            await db.rollback()
            raise

    # ========================================================
    # UPDATE CHAT TITLE
    # ========================================================

    async def update_chat_title(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user_id: UUID,
        new_title: str,
    ) -> ChatBase | None:

        try:
            stmt = (
                update(Chat)
                .where(
                    Chat.id == chat_id,
                    Chat.user_id == user_id,
                )
                .values(
                    title=new_title
                )
                .returning(Chat)
            )

            result = await db.execute(stmt)

            updated_chat = (
                result.scalar_one_or_none()
            )

            if not updated_chat:

                check_stmt = (
                    select(Chat)
                    .where(
                        Chat.id == chat_id
                    )
                )

                check_result = await db.execute(
                    check_stmt
                )

                if (
                    check_result.scalar_one_or_none()
                ):
                    raise HTTPException(
                        status_code=(
                            status.HTTP_403_FORBIDDEN
                        ),
                        detail=(
                            "You do not have permission to update "
                            "this chat session."
                        ),
                    )

                return None

            response_data = ChatBase.model_validate(
                updated_chat
            )

            await db.commit()

            return response_data

        except Exception:
            await db.rollback()
            raise

    # ========================================================
    # GET LATEST USER MESSAGES
    # ========================================================

    async def get_latest_chat(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user_id: UUID,
    ) -> list[MessageResponse] | None:

        # ----------------------------------------------------
        # Verify chat ownership.
        # ----------------------------------------------------

        chat_stmt = (
            select(Chat)
            .where(
                Chat.id == chat_id,
                Chat.user_id == user_id,
            )
        )

        chat_result = await db.execute(
            chat_stmt
        )

        chat_record = (
            chat_result.scalar_one_or_none()
        )

        if not chat_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission to access "
                    "this chat session."
                ),
            )

        # ----------------------------------------------------
        # UUIDs are NOT chronological.
        #
        # Use created_at + id as the ordering.
        # ----------------------------------------------------

        stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.role == MessageRole.USER,
            )
            .order_by(
                Message.created_at.desc(),
                Message.id.desc(),
            )
            .limit(5)
        )

        result = await db.execute(stmt)

        messages = list(
            result.scalars().all()
        )

        if len(messages) < 5:
            return None

        # ----------------------------------------------------
        # Return chronological order.
        # ----------------------------------------------------

        messages.reverse()

        return [
            MessageResponse.model_validate(
                message
            )
            for message in messages
        ]

    # ========================================================
    # DELETE CHAT
    # ========================================================

    async def delete_chat(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user_id: UUID,
    ) -> bool:

        try:
            stmt = (
                select(Chat)
                .where(
                    Chat.id == chat_id
                )
            )

            result = await db.execute(stmt)

            chat_record = (
                result.scalar_one_or_none()
            )

            if not chat_record:
                return False

            if chat_record.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You do not have permission to delete "
                        "this chat session."
                    ),
                )

            await db.delete(
                chat_record
            )

            await db.commit()

            return True

        except Exception:
            await db.rollback()
            raise

    # ========================================================
    # UPDATE MESSAGE
    # ========================================================

    async def update_message_in_chat(
        self,
        db: AsyncSession,
        chat_id: UUID,
        message_id: UUID,
        user_id: UUID,
        new_user_text: str,
        new_assistant_text: str,
        subject: str | None,
        hierarchy: dict | None,
    ):

        if (
            not new_user_text
            or not new_user_text.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "User message content cannot be null "
                    "or empty."
                ),
            )

        # ----------------------------------------------------
        # Verify chat ownership.
        # ----------------------------------------------------

        chat_stmt = (
            select(Chat)
            .where(
                Chat.id == chat_id,
                Chat.user_id == user_id,
            )
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
                detail="Chat session not found.",
            )

        # ----------------------------------------------------
        # Preserve the permanent subject boundary.
        # ----------------------------------------------------

        if (
            chat_record.subject is None
            and subject
        ):
            chat_record.subject = subject

        # ----------------------------------------------------
        # Get the latest USER message chronologically.
        #
        # UUID values cannot be used as timestamps.
        # ----------------------------------------------------

        latest_user_stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.role == MessageRole.USER,
            )
            .order_by(
                Message.created_at.desc(),
                Message.id.desc(),
            )
            .limit(1)
        )

        latest_result = await db.execute(
            latest_user_stmt
        )

        latest_user_message = (
            latest_result.scalars().first()
        )

        if not latest_user_message:
            return None

        # ----------------------------------------------------
        # Only the latest user message can be updated.
        # ----------------------------------------------------

        if message_id != latest_user_message.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Only the latest message in the chat "
                    "can be updated."
                ),
            )

        # ----------------------------------------------------
        # Get the actual user message.
        # ----------------------------------------------------

        stmt = (
            select(Message)
            .where(
                Message.id == message_id,
                Message.chat_id == chat_id,
                Message.role == MessageRole.USER,
            )
        )

        result = await db.execute(stmt)

        user_message = (
            result.scalars().first()
        )

        if not user_message:
            return None

        hierarchy = hierarchy or {}

        # ----------------------------------------------------
        # Update user message.
        # ----------------------------------------------------

        user_message.message = (
            new_user_text.strip()
        )

        user_message.chapter = (
            hierarchy.get("chapter")
        )

        user_message.topic = (
            hierarchy.get("topic")
        )

        user_message.subtopic = (
            hierarchy.get("subtopic")
        )

        # ----------------------------------------------------
        # Find the first assistant message AFTER the edited
        # user message chronologically.
        #
        # The previous implementation used:
        #
        # created_at >= user_message.created_at
        #
        # which could select an earlier assistant message
        # when timestamps were equal.
        # ----------------------------------------------------

        assistant_stmt = (
            select(Message)
            .where(
                Message.chat_id == chat_id,
                Message.role == MessageRole.ASSISTANT,
                or_(
                    Message.created_at
                    > user_message.created_at,
                    (
                        Message.created_at
                        == user_message.created_at
                    )
                    & (
                        Message.id
                        > user_message.id
                    ),
                ),
            )
            .order_by(
                Message.created_at.asc(),
                Message.id.asc(),
            )
            .limit(1)
        )

        assistant_result = await db.execute(
            assistant_stmt
        )

        assistant_message = (
            assistant_result.scalars().first()
        )

        # ----------------------------------------------------
        # Update existing assistant response.
        # ----------------------------------------------------

        if assistant_message:

            assistant_message.message = (
                new_assistant_text
            )

            assistant_message.chapter = (
                hierarchy.get("chapter")
            )

            assistant_message.topic = (
                hierarchy.get("topic")
            )

            assistant_message.subtopic = (
                hierarchy.get("subtopic")
            )

        # ----------------------------------------------------
        # If no assistant response exists, create one.
        # ----------------------------------------------------

        else:

            assistant_message = Message(
                chat_id=chat_id,
                role=MessageRole.ASSISTANT,
                message=new_assistant_text,
                chapter=hierarchy.get("chapter"),
                topic=hierarchy.get("topic"),
                subtopic=hierarchy.get("subtopic"),
            )

            db.add(
                assistant_message
            )

        await db.commit()

        await db.refresh(
            assistant_message
        )

        return MessageResponse.model_validate(
            assistant_message
        )