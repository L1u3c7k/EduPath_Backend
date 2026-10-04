import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat.model.chat_model import Chat
from src.chat.model.message_model import MessageRole

from src.quiz.model.quiz_model import Quiz
from src.question.model.question_model import Question
from src.quiz.model.quiz_attempt_model import QuizAttempt

from src.quiz.history import get_quiz_messages
from src.quiz.generator import generate_quiz_questions
from src.quiz.evaluator import evaluate_answer


BATCH_SIZE = 5
MAX_ATTEMPTS = 3
REDIS_TTL = 1800


# ============================================================
# REDIS
# ============================================================

def get_quiz_redis_key(chat_id: UUID) -> str:
    return f"quiz:{str(chat_id)}"


async def get_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
) -> dict | None:

    key = get_quiz_redis_key(chat_id)

    raw = await redis_client.get(key)

    if not raw:
        return None

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    return json.loads(raw)


async def save_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
    quiz_data: dict,
) -> None:

    key = get_quiz_redis_key(chat_id)

    await redis_client.set(
        key,
        json.dumps(quiz_data),
        ex=REDIS_TTL,
    )


async def delete_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
) -> None:

    await redis_client.delete(
        get_quiz_redis_key(chat_id)
    )


# ============================================================
# CHAT HISTORY
# ============================================================

def format_chat_history(messages) -> str:

    history = []

    for message in messages:

        if message.role == MessageRole.USER:
            role = "USER"
        else:
            role = "ASSISTANT"

        history.append(
            f"{role}:\n{message.message}"
        )

    return "\n\n".join(history)


# ============================================================
# GET POSTGRES QUIZ
# ============================================================

async def get_quiz(
    db: AsyncSession,
    chat_id: UUID,
) -> Quiz | None:

    result = await db.execute(
        select(Quiz)
        .where(
            Quiz.chat_id == chat_id
        )
    )

    return result.scalar_one_or_none()


# ============================================================
# GET EXISTING QUESTIONS
# ============================================================

async def get_existing_questions(
    db: AsyncSession,
    quiz_id: UUID,
) -> list[Question]:

    result = await db.execute(
        select(Question)
        .where(
            Question.quiz_id == quiz_id
        )
        .order_by(
            Question.question_number
        )
    )

    return list(
        result.scalars().all()
    )


# ============================================================
# GENERATE QUIZ BATCH
# ============================================================

async def generate_quiz_batch(
    db: AsyncSession,
    redis_client: redis.Redis,
    chat: Chat,
) -> tuple[dict | None, str | None]:

    # --------------------------------------------------------
    # Check active Redis quiz
    # --------------------------------------------------------

    active_quiz = await get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat.id,
    )

    if active_quiz is not None:

        return (
            active_quiz,
            "An active quiz already exists."
        )

    # --------------------------------------------------------
    # Get completed PostgreSQL quiz
    # --------------------------------------------------------

    postgres_quiz = await get_quiz(
        db=db,
        chat_id=chat.id,
    )

    last_message_id = None

    if postgres_quiz is not None:
        last_message_id = postgres_quiz.last_message_id

    # --------------------------------------------------------
    # Get next unprocessed messages
    # --------------------------------------------------------

    messages = await get_quiz_messages(
        db=db,
        chat_id=chat.id,
        last_message_id=last_message_id,
    )

    if len(messages) < BATCH_SIZE:

        return (
            None,
            "Not enough new chat messages "
            "to generate another quiz batch."
        )

    # --------------------------------------------------------
    # Existing completed questions
    # --------------------------------------------------------

    existing_questions = []

    if postgres_quiz is not None:

        existing_questions = (
            await get_existing_questions(
                db=db,
                quiz_id=postgres_quiz.id,
            )
        )

    existing_question_texts = [
        question.question
        for question in existing_questions
    ]

    # --------------------------------------------------------
    # Format history
    # --------------------------------------------------------

    chat_history = format_chat_history(
        messages
    )

    # --------------------------------------------------------
    # Generate questions
    # --------------------------------------------------------

    generated_questions = generate_quiz_questions(
        chat_history=chat_history,
        existing_questions=existing_question_texts,
    )

    # --------------------------------------------------------
    # LLM FAILURE
    # --------------------------------------------------------

    if generated_questions is None:

        return (
            None,
            "Quiz generation failed. Please try again."
        )

    # --------------------------------------------------------
    # NO NEW QUESTIONS
    # --------------------------------------------------------

    if not generated_questions:

        if postgres_quiz is not None:

            postgres_quiz.last_message_id = messages[-1].id

            await db.commit()

        return (
            None,
            "No new quiz questions could be generated "
            "from the new material."
        )

    # --------------------------------------------------------
    # Determine starting question number
    # --------------------------------------------------------

    starting_number = 1

    if existing_questions:

        starting_number = (
            max(
                question.question_number
                for question in existing_questions
            )
            + 1
        )

    # --------------------------------------------------------
    # Create temporary Redis quiz
    # --------------------------------------------------------

    quiz_data = {
        "chat_id": str(chat.id),
        "last_message_id": messages[-1].id,
        "questions": [],
    }

    for index, item in enumerate(generated_questions):

        quiz_data["questions"].append(
            {
                "question_number": (
                    starting_number + index
                ),
                "question": item["question"],
                "model_answer": item["model_answer"],
                "attempts": [],
                "completed": False,
            }
        )

    # --------------------------------------------------------
    # Save ONLY to Redis
    # --------------------------------------------------------

    await save_redis_quiz(
        redis_client=redis_client,
        chat_id=chat.id,
        quiz_data=quiz_data,
    )

    return (
        quiz_data,
        None,
    )


# ============================================================
# GET REDIS QUESTION
# ============================================================

def get_redis_question(
    quiz_data: dict,
    question_number: int,
) -> dict:

    for question in quiz_data.get("questions", []):

        if question["question_number"] == question_number:
            return question

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Question not found.",
    )


# ============================================================
# CHECK QUESTION COMPLETION
# ============================================================

def is_question_completed(
    question: dict,
) -> bool:

    if question.get("completed", False):
        return True

    attempts = question.get(
        "attempts",
        []
    )

    if any(
        attempt["is_correct"]
        for attempt in attempts
    ):
        return True

    if len(attempts) >= MAX_ATTEMPTS:
        return True

    return False


# ============================================================
# CHECK QUIZ COMPLETION
# ============================================================

def is_redis_quiz_completed(
    quiz_data: dict,
) -> bool:

    questions = quiz_data.get(
        "questions",
        []
    )

    if not questions:
        return False

    return all(
        is_question_completed(question)
        for question in questions
    )


# ============================================================
# ANSWER QUESTION
# ============================================================

async def answer_question(
    db: AsyncSession,
    redis_client: redis.Redis,
    chat_id: UUID,
    question_number: int,
    user_answer: str,
) -> dict:

    # --------------------------------------------------------
    # Load Redis quiz
    # --------------------------------------------------------

    quiz_data = await get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
    )

    if quiz_data is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active quiz found.",
        )

    # --------------------------------------------------------
    # Find question
    # --------------------------------------------------------

    question = get_redis_question(
        quiz_data=quiz_data,
        question_number=question_number,
    )

    # --------------------------------------------------------
    # Check completion
    # --------------------------------------------------------

    if is_question_completed(question):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is already completed.",
        )

    # --------------------------------------------------------
    # Attempts
    # --------------------------------------------------------

    attempts = question.get(
        "attempts",
        []
    )

    if len(attempts) >= MAX_ATTEMPTS:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum attempts reached.",
        )

    attempt_number = len(attempts) + 1

    # --------------------------------------------------------
    # Evaluate answer
    # --------------------------------------------------------

    evaluation = evaluate_answer(
        question=question["question"],
        model_answer=question["model_answer"],
        user_answer=user_answer,
    )

    # --------------------------------------------------------
    # Evaluation failure
    # --------------------------------------------------------

    if evaluation is None:

        return {
            "error": "The answer could not be evaluated."
        }

    is_correct = evaluation["is_correct"]
    feedback = evaluation["feedback"]
    hint = evaluation["hint"]

    # --------------------------------------------------------
    # Save attempt
    # --------------------------------------------------------

    attempt = {
        "attempt_number": attempt_number,
        "user_answer": user_answer,
        "is_correct": is_correct,
        "feedback": feedback,
    }

    question.setdefault("attempts", []).append(
        attempt
    )

    # --------------------------------------------------------
    # Correct
    # --------------------------------------------------------

    if is_correct:

        question["completed"] = True

    # --------------------------------------------------------
    # Third wrong attempt
    # --------------------------------------------------------

    elif attempt_number == MAX_ATTEMPTS:

        question["completed"] = True

    # --------------------------------------------------------
    # Check entire quiz
    # --------------------------------------------------------

    quiz_completed = is_redis_quiz_completed(
        quiz_data
    )

    # --------------------------------------------------------
    # Save completed quiz
    # --------------------------------------------------------

    if quiz_completed:

        quiz_record = await save_completed_quiz_to_db(
            db=db,
            chat_id=chat_id,
            quiz_data=quiz_data,
        )

        # Redis is deleted ONLY after DB commit succeeds.

        await delete_redis_quiz(
            redis_client=redis_client,
            chat_id=chat_id,
        )

        return {
            "correct": is_correct,
            "explanation": feedback,
            "hint": None,
            "question_completed": True,
            "quiz_completed": True,
            "question_number": question_number,
            "model_answer": (
                None
                if is_correct
                else question["model_answer"]
            ),
            "quiz_id": str(quiz_record.id),
        }

    # --------------------------------------------------------
    # Quiz still active
    # --------------------------------------------------------

    await save_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
        quiz_data=quiz_data,
    )

    # --------------------------------------------------------
    # Wrong answer
    # --------------------------------------------------------

    if not is_correct:

        return {
            "correct": False,
            "explanation": feedback,
            "hint": hint,
            "question_completed": False,
            "quiz_completed": False,
            "question_number": question_number,
            "model_answer": (
                question["model_answer"]
                if attempt_number == MAX_ATTEMPTS
                else None
            ),
        }

    # --------------------------------------------------------
    # Correct answer
    # --------------------------------------------------------

    return {
        "correct": True,
        "explanation": feedback,
        "hint": None,
        "question_completed": True,
        "quiz_completed": False,
        "question_number": question_number,
        "model_answer": None,
    }


# ============================================================
# SAVE COMPLETED QUIZ TO POSTGRESQL
# ============================================================

async def save_completed_quiz_to_db(
    db: AsyncSession,
    chat_id: UUID,
    quiz_data: dict,
) -> Quiz:

    questions = quiz_data.get(
        "questions",
        []
    )

    if not questions:

        raise ValueError(
            "Cannot save an empty quiz."
        )

    if not is_redis_quiz_completed(
        quiz_data
    ):

        raise ValueError(
            "Cannot save an incomplete quiz."
        )

    try:

        # ----------------------------------------------------
        # Get existing Quiz
        # ----------------------------------------------------

        result = await db.execute(
            select(Quiz)
            .where(
                Quiz.chat_id == chat_id
            )
        )

        quiz_record = result.scalar_one_or_none()

        # ----------------------------------------------------
        # Create Quiz if necessary
        # ----------------------------------------------------

        if quiz_record is None:

            quiz_record = Quiz(
                chat_id=chat_id,
                last_message_id=(
                    quiz_data["last_message_id"]
                ),
                completed_at=datetime.now(
                    timezone.utc
                ),
            )

            db.add(quiz_record)

            await db.flush()

        else:

            quiz_record.last_message_id = (
                quiz_data["last_message_id"]
            )

            quiz_record.completed_at = (
                datetime.now(timezone.utc)
            )

        # ----------------------------------------------------
        # Save every question
        # ----------------------------------------------------

        for redis_question in questions:

            question_record = Question(
                quiz_id=quiz_record.id,
                question_number=(
                    redis_question["question_number"]
                ),
                question=redis_question["question"],
                model_answer=redis_question["model_answer"],
            )

            db.add(question_record)

            await db.flush()

            # ------------------------------------------------
            # Save EVERY attempt
            # ------------------------------------------------

            for attempt in redis_question.get(
                "attempts",
                []
            ):

                attempt_record = QuizAttempt(
                    question_id=question_record.id,
                    attempt_number=(
                        attempt["attempt_number"]
                    ),
                    user_answer=(
                        attempt["user_answer"]
                    ),
                    is_correct=(
                        attempt["is_correct"]
                    ),
                    feedback=(
                        attempt["feedback"]
                    ),
                )

                db.add(attempt_record)

        # ----------------------------------------------------
        # One PostgreSQL transaction
        # ----------------------------------------------------

        await db.commit()

        await db.refresh(
            quiz_record
        )

        return quiz_record

    except Exception:

        await db.rollback()

        raise