import asyncio

from src.database import AsyncSessionLocal
from src.ai_model.chat.manager import ai_chat


async def main():
    current_subject = None

    async with AsyncSessionLocal() as db:

        while True:
            question = input("\nUser: ")

            if question.lower() == "exit":
                break

            (
                answer,
                current_subject,
                hierarchy,
            ) = await ai_chat(
                question=question,
                db=db,
                current_subject=current_subject,
            )

            print("\nAI:", answer)


if __name__ == "__main__":
    asyncio.run(main())