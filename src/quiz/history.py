from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat.model.message_model import Message


QUIZ_MESSAGE_COUNT = 5


async def get_quiz_messages(
    db: AsyncSession,
    chat_id: int,
    last_message_id: int | None = None,
) -> list[Message]:

    query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.id.desc())
    )

    if last_message_id is not None:
        query = query.where(
            Message.id > last_message_id
        )

    result = await db.execute(query)

    messages = result.scalars().all()

    messages = list(reversed(messages))

    return messages[-QUIZ_MESSAGE_COUNT:]