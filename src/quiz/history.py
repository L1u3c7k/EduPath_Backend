from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat.model.message_model import Message


QUIZ_MESSAGE_COUNT = 5


async def get_quiz_messages(
    db: AsyncSession,
    chat_id: UUID,
    last_message_id: UUID | None = None,
) -> list[Message]:
    """
    Return the next quiz-generation conversation batch.

    The batch is triggered by FIVE NEW USER messages.

    Example:

        USER 1
        ASSISTANT 1
        USER 2
        ASSISTANT 2
        USER 3
        ASSISTANT 3
        USER 4
        ASSISTANT 4
        USER 5
        ASSISTANT 5

    The five USER messages determine whether a new batch
    is available.

    Once the five USER messages are found, the returned
    history contains the conversation from the first USER
    message through the ASSISTANT response corresponding to
    the fifth USER message, when that response exists.

    Message ordering is based on:

        created_at ASC
        id ASC

    UUIDs are random and therefore cannot be used alone
    to determine chronological order.
    """

    # ========================================================
    # STEP 1
    # Find the next FIVE USER messages.
    # ========================================================

    user_query = select(Message).where(
        Message.chat_id == chat_id,
        Message.role == "user",
    )

    # ========================================================
    # Continue after the previous batch cursor.
    #
    # last_message_id represents the fifth USER message
    # from the previously processed batch.
    # ========================================================

    if last_message_id is not None:

        cursor_result = await db.execute(
            select(Message).where(
                Message.id == last_message_id,
                Message.chat_id == chat_id,
                Message.role == "user",
            )
        )

        cursor_message = (
            cursor_result.scalar_one_or_none()
        )

        # ----------------------------------------------------
        # Invalid cursor.
        #
        # Do not silently start from the beginning.
        # ----------------------------------------------------

        if cursor_message is None:
            return []

        # ----------------------------------------------------
        # Only USER messages after the cursor.
        # ----------------------------------------------------

        user_query = user_query.where(
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
            )
        )

    # ========================================================
    # Chronological ordering.
    # ========================================================

    user_query = user_query.order_by(
        Message.created_at.asc(),
        Message.id.asc(),
    )

    # ========================================================
    # Only retrieve the next FIVE USER messages.
    # ========================================================

    user_query = user_query.limit(
        QUIZ_MESSAGE_COUNT
    )

    user_result = await db.execute(
        user_query
    )

    user_messages = list(
        user_result.scalars().all()
    )

    # ========================================================
    # Fewer than FIVE new USER messages means the next
    # quiz batch is not ready.
    # ========================================================

    if len(user_messages) < QUIZ_MESSAGE_COUNT:
        return []

    # ========================================================
    # The first and fifth USER messages define the batch.
    # ========================================================

    first_user_message = user_messages[0]
    fifth_user_message = user_messages[-1]

    # ========================================================
    # STEP 2
    #
    # Find the ASSISTANT response immediately following the
    # fifth USER message.
    #
    # Normally the chat flow produces:
    #
    # USER 5
    # ASSISTANT 5
    #
    # If the assistant response has not been created yet,
    # the history still ends at USER 5.
    # ========================================================

    assistant_query = select(Message).where(
        Message.chat_id == chat_id,
        Message.role == "assistant",
        or_(
            Message.created_at
            > fifth_user_message.created_at,

            (
                Message.created_at
                == fifth_user_message.created_at
            )
            & (
                Message.id
                > fifth_user_message.id
            ),
        ),
    ).order_by(
        Message.created_at.asc(),
        Message.id.asc(),
    ).limit(1)

    assistant_result = await db.execute(
        assistant_query
    )

    fifth_assistant_message = (
        assistant_result.scalar_one_or_none()
    )

    # ========================================================
    # STEP 3
    #
    # Determine the end of the returned conversation.
    #
    # If ASSISTANT 5 exists:
    #
    #     first USER
    #         ↓
    #     fifth USER
    #         ↓
    #     fifth ASSISTANT
    #
    # Otherwise:
    #
    #     first USER
    #         ↓
    #     fifth USER
    # ========================================================

    if fifth_assistant_message is not None:

        end_message = (
            fifth_assistant_message
        )

    else:

        end_message = (
            fifth_user_message
        )

    # ========================================================
    # STEP 4
    #
    # Retrieve ALL messages between the first USER message
    # and the end of the fifth turn.
    #
    # This intentionally includes:
    #
    #     USER
    #     ASSISTANT
    #
    # messages.
    # ========================================================

    message_query = select(Message).where(
        Message.chat_id == chat_id,

        # ----------------------------------------------------
        # Start at the first USER message.
        # ----------------------------------------------------

        or_(
            Message.created_at
            > first_user_message.created_at,

            (
                Message.created_at
                == first_user_message.created_at
            )
            & (
                Message.id
                >= first_user_message.id
            ),
        ),

        # ----------------------------------------------------
        # End at ASSISTANT 5 when it exists, otherwise USER 5.
        # ----------------------------------------------------

        or_(
            Message.created_at
            < end_message.created_at,

            (
                Message.created_at
                == end_message.created_at
            )
            & (
                Message.id
                <= end_message.id
            ),
        ),
    )

    # ========================================================
    # Chronological order.
    # ========================================================

    message_query = message_query.order_by(
        Message.created_at.asc(),
        Message.id.asc(),
    )

    result = await db.execute(
        message_query
    )

    return list(
        result.scalars().all()
    )