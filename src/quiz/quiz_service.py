import json
import logging
from uuid import UUID
from fastapi import HTTPException, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from src.quiz.quiz_model import Quiz
from src.question.question_model import Question

logger = logging.getLogger(__name__)


class QuizService:
    async def mock_generate_questions(self, topic_title: str = "General") -> list[dict]:
        return [
            {
                "id": i,
                "text": f"Mock Question {i} based on chat topic: {topic_title}",
                "rubric": f"Mock ideal answer / rubric for question {i}.",
                "attempts_left": 3,
                "attempts_used": 0,
                "is_finished": False,
                "last_user_answer": None,
                "last_feedback": None,
                "passed": False
            }
            for i in range(1, 6)
        ]

    async def initialize_quiz_session(
        self,
        redis_client: redis.Redis,
        user_id: UUID,
        chat_id: UUID,
        topic_title: str = "General Chat"
    ) -> dict:
        questions = await self.mock_generate_questions(topic_title=topic_title)

        session_data = {
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "questions": questions
        }

        # Keep UUID objects and convert directly in key string interpolation
        session_key = f"quiz:{user_id}:{chat_id}"
        await redis_client.set(session_key, json.dumps(session_data), ex=1800)
        
        return session_data

    async def evaluate_and_update_question(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
        user_id: UUID,
        chat_id: UUID,
        question_id: int,
        user_answer: str
    ) -> dict:
        session_key = f"quiz:{user_id}:{chat_id}"
        logger.info(f"[Redis Read] Looking for session key: '{session_key}'")

        raw_session = await redis_client.get(session_key)

        if not raw_session:
            logger.error(f"[Redis Read Failed] Key '{session_key}' not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active quiz session found for key '{session_key}' or session has expired."
            )

        session_data = json.loads(raw_session)
        questions = session_data.get("questions", [])

        # 1. Find target question
        target_q = next((q for q in questions if q["id"] == question_id), None)
        if not target_q:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question with ID {question_id} not found in this quiz."
            )

        # 2. Check question availability
        if target_q["is_finished"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This question is already completed."
            )

        if target_q["attempts_left"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No attempts remaining for this question."
            )

        # 3. Evaluate answer
        is_correct = len(user_answer.strip()) > 5  # Placeholder
        
        target_q["attempts_left"] -= 1
        target_q["attempts_used"] = target_q.get("attempts_used", 0) + 1
        target_q["last_user_answer"] = user_answer

        if is_correct:
            target_q["passed"] = True
            target_q["is_finished"] = True
            target_q["last_feedback"] = "Correct! You demonstrated a solid understanding."
        elif target_q["attempts_left"] == 0:
            target_q["passed"] = False
            target_q["is_finished"] = True
            target_q["last_feedback"] = f"Out of attempts. Expected criteria: {target_q['rubric']}"
        else:
            target_q["passed"] = False
            target_q["last_feedback"] = f"Incorrect answer. You have {target_q['attempts_left']} attempt(s) remaining."

        # 4. Save to DB if all questions completed
        all_completed = all(q.get("is_finished", False) for q in questions)

        if all_completed:
            quiz_record = await self.save_completed_quiz_to_db(
                db=db,
                user_id=user_id,
                chat_id=chat_id,
                questions=questions
            )

            # Clear cache from Redis
            await redis_client.delete(session_key)

            return {
                "question": target_q,
                "quiz_summary": {
                    "is_completed": True,
                    "quiz_id": str(quiz_record.id),
                    "message": "Quiz completed and saved to database successfully!"
                }
            }

        # If quiz in progress, update Redis cache
        await redis_client.set(session_key, json.dumps(session_data), ex=1800)

        return {
            "question": target_q,
            "quiz_summary": {
                "is_completed": False
            }
        }

    async def save_completed_quiz_to_db(
        self,
        db: AsyncSession,
        user_id: UUID,
        chat_id: UUID,
        questions: list[dict]
    ) -> Quiz:
        """
        Persists completed quiz session and individual question attempts to PostgreSQL.
        """
        # 1. Create parent Quiz entry directly with UUIDs
        quiz_record = Quiz(
            user_id=user_id,
            chat_id=chat_id
        )
        db.add(quiz_record)
        await db.flush()  # Generates quiz_record.id for foreign key assignment

        # 2. Map Redis question dictionaries to Question ORM models
        question_objects = [
            Question(
                quiz_id=quiz_record.id,
                question=q["text"],
                model_answer=q["rubric"],
                user_answer=q.get("last_user_answer"),
                is_correct=q.get("passed", False),
                ai_feedback=q.get("last_feedback"),
                attempts_used=q.get("attempts_used", 1)
            )
            for q in questions
        ]

        db.add_all(question_objects)
        await db.commit()
        await db.refresh(quiz_record)

        return quiz_record