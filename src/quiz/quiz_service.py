import json
import logging
from uuid import UUID
from fastapi import HTTPException, status
import redis.asyncio as redis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Models
from src.chat.model.chat_model import Chat
from src.chat.model.message_model import MessageRole
from src.quiz.model.quiz_model import Quiz
from src.question.model.question_model import Question
from src.quiz.model.quiz_attempt_model import QuizAttempt

# LLM & History Helpers
from src.quiz.history import get_quiz_messages
from src.quiz.generator import generate_quiz_questions
from src.quiz.evaluator import evaluate_answer

logger = logging.getLogger(__name__)

BATCH_SIZE = 5
MAX_ATTEMPTS = 3


class QuizService:
    # ============================================================
    # HELPER: CHAT HISTORY FORMATTER
    # ============================================================
    @staticmethod
    def format_chat_history(messages) -> str:
        history = []
        for message in messages:
            role = "USER" if message.role == MessageRole.USER else "ASSISTANT"
            history.append(f"{role}:\n{message.message}")
        return "\n\n".join(history)

    # ============================================================
    # 1. INITIALIZE / GENERATE QUIZ SESSION
    # ============================================================
    async def initialize_quiz_session(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
        user_id: UUID,
        chat: Chat,
    ) -> tuple[dict | None, str | None]:
        """
        Check for an active session in Redis or generate a new batch of 5 questions
        using LLM based on unread chat messages.
        """
        session_key = f"quiz:{user_id}:{chat.id}"

        # 1. Return active Redis session if present (Cache-first)
        raw_session = await redis_client.get(session_key)
        if raw_session:
            return json.loads(raw_session), None

        # 2. Check PostgreSQL for existing quiz record to get last processed message ID
        result = await db.execute(select(Quiz).where(Quiz.chat_id == chat.id))
        quiz = result.scalar_one_or_none()
        last_message_id = quiz.last_message_id if quiz else None

        # 3. Retrieve new unread chat messages
        messages = await get_quiz_messages(db, chat.id, last_message_id)
        if len(messages) < BATCH_SIZE:
            return None, "Not enough new chat messages to generate a quiz batch."

        # 4. Generate questions using LLM based on chat history
        chat_history = self.format_chat_history(messages)
        generated_questions = generate_quiz_questions(chat_history)

        if len(generated_questions) != BATCH_SIZE:
            return None, "The quiz generator did not return exactly 5 questions."

        # 5. Build full active question objects for Redis state
        questions = [
            {
                "id": index + 1,
                "question": q["question"],
                "model_answer": q["model_answer"],
                "attempts_left": MAX_ATTEMPTS,
                "attempts_used": 0,
                "is_finished": False,
                "last_user_answer": None,
                "last_feedback": None,
                "hint": None,
                "passed": False,
            }
            for index, q in enumerate(generated_questions)
        ]

        session_data = {
            "chat_id": str(chat.id),
            "user_id": str(user_id),
            "last_message_id": messages[-1].id,
            "questions": questions,
        }

        # Cache session in Redis with 30-minute TTL
        await redis_client.set(session_key, json.dumps(session_data), ex=1800)

        return session_data, None

    # ============================================================
    # 2. EVALUATE AND UPDATE QUESTION (REDIS STATE)
    # ============================================================
    async def evaluate_and_update_question(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
        user_id: UUID,
        chat_id: UUID,
        question_id: int,
        user_answer: str,
    ) -> dict:
        """
        Evaluates a question attempt via LLM, updates attempt counts and state in Redis,
        and persists to PostgreSQL if all 5 questions are complete.
        """
        session_key = f"quiz:{user_id}:{chat_id}"
        logger.info(f"[Redis Read] Looking for session key: '{session_key}'")

        raw_session = await redis_client.get(session_key)
        if not raw_session:
            logger.error(f"[Redis Read Failed] Key '{session_key}' not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active quiz session found or session has expired.",
            )

        session_data = json.loads(raw_session)
        questions = session_data.get("questions", [])

        # Validate target question
        target_q = next((q for q in questions if q["id"] == question_id), None)
        if not target_q:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question with ID {question_id} not found in active session.",
            )

        if target_q["is_finished"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This question is already completed.",
            )

        if target_q["attempts_left"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No attempts remaining for this question.",
            )

        # Evaluate answer using LLM
        evaluation = evaluate_answer(
            question=target_q["question"],
            model_answer=target_q["model_answer"],
            user_answer=user_answer,
        )

        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The answer could not be evaluated by the LLM.",
            )

        is_correct = evaluation["is_correct"]
        feedback = evaluation["feedback"]
        hint = evaluation["hint"]

        # Update attempt counters
        target_q["attempts_left"] -= 1
        target_q["attempts_used"] += 1
        target_q["last_user_answer"] = user_answer
        target_q["last_feedback"] = feedback

        # Determine attempt state transitions
        if is_correct:
            target_q["passed"] = True
            target_q["is_finished"] = True
            target_q["hint"] = None
        elif target_q["attempts_left"] == 0:
            # Exhausted all 3 attempts
            target_q["passed"] = False
            target_q["is_finished"] = True
            target_q["hint"] = None
        else:
            # Failed attempt; remaining attempts available
            target_q["passed"] = False
            target_q["hint"] = hint

        # Check if all 5 batch questions are finished
        all_completed = all(q.get("is_finished", False) for q in questions)

        if all_completed:
            last_msg_id = session_data.get("last_message_id")
            quiz_record = await self.save_completed_quiz_to_db(
                db=db,
                user_id=user_id,
                chat_id=chat_id,
                questions=questions,
                last_message_id=last_msg_id,
            )

            # Evict Redis cache once persisted to DB
            await redis_client.delete(session_key)

            return {
                "question": target_q,
                "quiz_summary": {
                    "is_completed": True,
                    "quiz_id": str(quiz_record.id),
                    "message": "Quiz completed and saved successfully!",
                },
            }

        # Update Redis state if questions remain incomplete
        await redis_client.set(session_key, json.dumps(session_data), ex=1800)

        return {
            "question": target_q,
            "quiz_summary": {
                "is_completed": False,
            },
        }

    # ============================================================
    # 3. PERSISTENCE: SAVE COMPLETED QUIZ TO POSTGRESQL
    # ============================================================
    async def save_completed_quiz_to_db(
        self,
        db: AsyncSession,
        user_id: UUID,
        chat_id: UUID,
        questions: list[dict],
        last_message_id: int | None = None,
    ) -> Quiz:
        """
        Persists completed quiz batch, question entries, and individual attempts to PostgreSQL.
        """
        # Fetch existing or create new parent Quiz record
        result = await db.execute(select(Quiz).where(Quiz.chat_id == chat_id))
        quiz_record = result.scalar_one_or_none()

        if not quiz_record:
            quiz_record = Quiz(
                user_id=user_id,
                chat_id=chat_id,
                current_question=len(questions),
                last_message_id=last_message_id,
            )
            db.add(quiz_record)
            await db.flush()
        else:
            quiz_record.last_message_id = last_message_id
            quiz_record.current_question += len(questions)

        # Get offset for question numbers across batches
        max_q_result = await db.execute(
            select(func.max(Question.question_number)).where(
                Question.quiz_id == quiz_record.id
            )
        )
        last_q_num = max_q_result.scalar_one() or 0

        # Persist questions and attempt logs
        for idx, q in enumerate(questions):
            question_obj = Question(
                quiz_id=quiz_record.id,
                question_number=last_q_num + idx + 1,
                question=q["question"],
                model_answer=q["model_answer"],
            )
            db.add(question_obj)
            await db.flush()

            attempt_obj = QuizAttempt(
                question_id=question_obj.id,
                attempt_number=q["attempts_used"],
                user_answer=q["last_user_answer"] or "",
                is_correct=q["passed"],
                feedback=q["last_feedback"] or "",
            )
            db.add(attempt_obj)

        await db.commit()
        await db.refresh(quiz_record)

        return quiz_record