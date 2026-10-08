import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat.model.chat_model import Chat
from src.chat.model.message_model import MessageRole
from src.question.model.question_model import Question
from src.quiz.evaluator import evaluate_answer
from src.quiz.generator import generate_quiz_questions
from src.quiz.history import get_quiz_messages
from src.quiz.model.quiz_model import Quiz


# ============================================================
# SETTINGS
# ============================================================

BATCH_SIZE = 5
MAX_ATTEMPTS = 3
REDIS_TTL = 1800


# ============================================================
# REDIS
# ============================================================

def get_quiz_redis_key(
    chat_id: UUID,
) -> str:
    return f"quiz:{str(chat_id)}"


async def get_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
    user_id: UUID,
) -> dict | None:
    """
    Get the active quiz from Redis.

    Redis is the source of truth for an in-progress quiz.
    """

    key = get_quiz_redis_key(
        chat_id
    )

    raw = await redis_client.get(
        key
    )

    if not raw:
        return None

    if isinstance(raw, bytes):
        raw = raw.decode(
            "utf-8"
        )

    try:
        quiz_data = json.loads(
            raw
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    # --------------------------------------------------------
    # Verify ownership.
    # --------------------------------------------------------

    if quiz_data.get(
        "user_id"
    ) != str(user_id):

        return None

    return quiz_data


async def save_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
    quiz_data: dict,
) -> None:
    """
    Save active quiz state to Redis with a TTL.
    """

    key = get_quiz_redis_key(
        chat_id
    )

    await redis_client.set(
        key,
        json.dumps(
            quiz_data
        ),
        ex=REDIS_TTL,
    )


async def delete_redis_quiz(
    redis_client: redis.Redis,
    chat_id: UUID,
) -> None:
    """
    Delete the active Redis quiz.
    """

    await redis_client.delete(
        get_quiz_redis_key(
            chat_id
        )
    )


# ============================================================
# CHAT HISTORY
# ============================================================

def format_chat_history(
    messages: list,
) -> str:
    """
    Convert chat messages into text for quiz generation.

    The history contains both USER and ASSISTANT messages.
    """

    history = []

    for message in messages:

        if message.role == MessageRole.USER:
            role = "USER"

        else:
            role = "ASSISTANT"

        history.append(
            f"{role}:\n{message.message}"
        )

    return "\n\n".join(
        history
    )


# ============================================================
# GET POSTGRES QUIZ
# ============================================================

async def get_quiz(
    db: AsyncSession,
    chat_id: UUID,
) -> Quiz | None:
    """
    Get the persistent quiz belonging to a chat.

    quizzes.chat_id is unique, so there is only one
    persistent Quiz row per chat.
    """

    result = await db.execute(
        select(Quiz).where(
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
    """
    Get all previously persisted questions for this quiz.
    """

    result = await db.execute(
        select(Question)
        .where(
            Question.quiz_id == quiz_id
        )
        .order_by(
            Question.question_number.asc()
        )
    )

    return list(
        result.scalars().all()
    )


def serialize_stored_question(
    question: Question,
) -> dict:
    """
    Convert a persisted question into the same plain-dict
    shape the frontend already uses for quiz rendering.
    """

    return {
        "id": str(
            question.id
        ),
        "question_number": (
            question.question_number
        ),
        "question": (
            question.question
        ),
        "model_answer": (
            question.model_answer
        ),
        "user_answer": (
            question.user_answer
        ),
        "is_correct": (
            question.is_correct
        ),
        "ai_feedback": (
            question.ai_feedback
        ),
        "attempts_used": (
            question.attempts_used
        ),
        "created_at": (
            question.created_at.isoformat()
            if question.created_at
            else None
        ),
        "source": "stored",
        "completed": True,
    }


async def get_stored_questions_for_chat(
    db: AsyncSession,
    chat_id: UUID,
) -> list[dict]:
    """
    Return all completed PostgreSQL questions for a chat.
    """

    postgres_quiz = await get_quiz(
        db=db,
        chat_id=chat_id,
    )

    if postgres_quiz is None:

        return []

    questions = await get_existing_questions(
        db=db,
        quiz_id=postgres_quiz.id,
    )

    return [
        serialize_stored_question(
            question
        )
        for question in questions
    ]


# ============================================================
# GENERATE QUIZ BATCH
# ============================================================

async def generate_quiz_batch(
    db: AsyncSession,
    redis_client: redis.Redis,
    chat: Chat,
    user_id: UUID,
) -> tuple[dict | None, str | None]:
    """
    Generate the next quiz batch.

    Rules:

    1. An active Redis quiz cannot be replaced.
    2. Five NEW USER messages are required.
    3. Quiz generation receives USER + ASSISTANT messages
       belonging to those five USER turns.
    4. Generation failure does NOT advance the cursor.
    5. Successful empty generation consumes the batch.
    6. New questions are stored only in Redis.
    7. PostgreSQL questions are created only after the entire
       active quiz has been completed.
    8. Question numbering continues from the previous maximum.
    """

    # ========================================================
    # CHECK ACTIVE REDIS QUIZ
    # ========================================================

    active_quiz = await get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat.id,
        user_id=user_id,
    )

    if active_quiz is not None:

        return (
            active_quiz,
            "An active quiz already exists.",
        )

    # ========================================================
    # GET PERSISTENT QUIZ
    # ========================================================

    postgres_quiz = await get_quiz(
        db=db,
        chat_id=chat.id,
    )

    last_message_id = None

    if postgres_quiz is not None:

        last_message_id = (
            postgres_quiz.last_message_id
        )

    # ========================================================
    # GET NEXT QUIZ HISTORY
    #
    # history.py:
    #
    # - requires FIVE new USER messages
    # - returns USER + ASSISTANT context
    # - includes the assistant response after USER 5
    #   when available
    # ========================================================

    messages = await get_quiz_messages(
        db=db,
        chat_id=chat.id,
        last_message_id=last_message_id,
    )

    # ========================================================
    # NOT ENOUGH NEW USER MESSAGES
    # ========================================================

    if not messages:

        return (
            None,
            "Not enough new user messages "
            "to generate another quiz batch.",
        )

    # ========================================================
    # GET HISTORICAL QUESTIONS
    # ========================================================

    existing_questions: list[Question] = []

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

    # ========================================================
    # FORMAT USER + ASSISTANT HISTORY
    # ========================================================

    chat_history = format_chat_history(
        messages
    )

    # ========================================================
    # GENERATE NEW QUESTIONS
    # ========================================================

    generated_questions = (
        generate_quiz_questions(
            chat_history=chat_history,
            existing_questions=(
                existing_question_texts
            ),
        )
    )

    # ========================================================
    # GENERATION FAILURE
    #
    # None means the LLM/provider failed.
    #
    # DO NOT advance the cursor.
    # ========================================================

    if generated_questions is None:

        return (
            None,
            "Quiz generation failed. Please try again.",
        )

    # ========================================================
    # GENERATION SUCCEEDED BUT PRODUCED NO NEW QUESTIONS
    #
    # The five USER messages were successfully processed.
    #
    # We therefore consume the batch.
    # ========================================================

    if not generated_questions:

        # ----------------------------------------------------
        # The cursor must always point to the FIFTH USER
        # message, not the ASSISTANT response.
        #
        # history.py returns:
        #
        # USER 1
        # ASSISTANT 1
        # ...
        # USER 5
        # ASSISTANT 5
        #
        # Therefore messages[-1] is no longer guaranteed to be
        # the fifth USER message.
        #
        # Find it explicitly.
        # ----------------------------------------------------

        fifth_user_message = None

        for message in reversed(messages):

            if message.role == MessageRole.USER:

                fifth_user_message = message

                break

        if fifth_user_message is None:

            return (
                None,
                "Quiz generation could not determine "
                "the batch cursor.",
            )

        # ----------------------------------------------------
        # Existing persistent quiz:
        # advance its cursor.
        # ----------------------------------------------------

        if postgres_quiz is not None:

            postgres_quiz.last_message_id = (
                fifth_user_message.id
            )

            await db.commit()

            return (
                None,
                "No new quiz questions could be generated "
                "from the new material.",
            )

        # ----------------------------------------------------
        # First batch:
        #
        # Create the persistent Quiz row so the cursor is
        # remembered even though this batch generated no
        # questions.
        # ----------------------------------------------------

        postgres_quiz = Quiz(
            chat_id=chat.id,
            last_message_id=fifth_user_message.id,
            completed_at=None,
        )

        db.add(
            postgres_quiz
        )

        await db.commit()

        return (
            None,
            "No new quiz questions could be generated "
            "from the new material.",
        )

    # ========================================================
    # DETERMINE FIFTH USER MESSAGE
    #
    # The returned history ends after ASSISTANT 5 when that
    # response exists, so messages[-1] cannot be used as the
    # cursor.
    # ========================================================

    fifth_user_message = None

    for message in reversed(messages):

        if message.role == MessageRole.USER:

            fifth_user_message = message

            break

    if fifth_user_message is None:

        return (
            None,
            "Quiz generation could not determine "
            "the batch cursor.",
        )

    # ========================================================
    # DETERMINE QUESTION NUMBERING
    # ========================================================

    starting_number = 1

    if existing_questions:

        starting_number = (
            max(
                question.question_number
                for question in existing_questions
            )
            + 1
        )

    # ========================================================
    # CREATE ACTIVE REDIS QUIZ
    # ========================================================

    quiz_data = {
        "chat_id": str(
            chat.id
        ),
        "user_id": str(
            user_id
        ),

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # The cursor is ALWAYS the fifth USER message.
        #
        # The assistant response is generation context only.
        # ----------------------------------------------------

        "last_message_id": str(
            fifth_user_message.id
        ),

        "questions": [],
    }

    # ========================================================
    # STORE GENERATED QUESTIONS
    # ========================================================

    for index, item in enumerate(
        generated_questions[:BATCH_SIZE]
    ):

        quiz_data["questions"].append(
            {
                "question_number": (
                    starting_number
                    + index
                ),
                "question": (
                    item["question"]
                ),
                "model_answer": (
                    item["model_answer"]
                ),
                "attempts": [],
                "completed": False,
            }
        )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not quiz_data["questions"]:

        # ----------------------------------------------------
        # Successful generation that resulted in no usable
        # Redis questions.
        #
        # Consume the batch.
        # ----------------------------------------------------

        if postgres_quiz is None:

            postgres_quiz = Quiz(
                chat_id=chat.id,
                last_message_id=(
                    fifth_user_message.id
                ),
                completed_at=None,
            )

            db.add(
                postgres_quiz
            )

        else:

            postgres_quiz.last_message_id = (
                fifth_user_message.id
            )

        await db.commit()

        return (
            None,
            "No new quiz questions could be generated "
            "from the new material.",
        )

    # ========================================================
    # SAVE ACTIVE QUIZ TO REDIS
    #
    # PostgreSQL is NOT modified here.
    # ========================================================

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
    """
    Find one question in the active Redis quiz.
    """

    for question in quiz_data.get(
        "questions",
        [],
    ):

        if (
            question["question_number"]
            == question_number
        ):

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
    """
    Determine whether a question is complete.

    A question is complete when:

    - it has already been marked completed,
    - any evaluated attempt was correct,
    - or three evaluated attempts were used.
    """

    if question.get(
        "completed",
        False,
    ):

        return True

    attempts = question.get(
        "attempts",
        [],
    )

    # --------------------------------------------------------
    # Correct attempt.
    # --------------------------------------------------------

    if any(
        attempt.get(
            "is_correct",
            False,
        )
        for attempt in attempts
    ):

        return True

    # --------------------------------------------------------
    # Maximum attempts.
    # --------------------------------------------------------

    if len(attempts) >= MAX_ATTEMPTS:

        return True

    return False


# ============================================================
# CHECK QUIZ COMPLETION
# ============================================================

def is_redis_quiz_completed(
    quiz_data: dict,
) -> bool:
    """
    A quiz is complete only when every question is complete.
    """

    questions = quiz_data.get(
        "questions",
        [],
    )

    if not questions:

        return False

    return all(
        is_question_completed(
            question
        )
        for question in questions
    )


# ============================================================
# ANSWER QUESTION
# ============================================================

async def answer_question(
    db: AsyncSession,
    redis_client: redis.Redis,
    chat_id: UUID,
    user_id: UUID,
    question_number: int,
    user_answer: str,
) -> dict:
    """
    Submit an answer to any question in the active quiz.

    Questions may be answered in any order.

    Attempt rules:

        Attempt 1 wrong:
            incomplete + hint

        Attempt 2 wrong:
            incomplete + hint

        Attempt 3 wrong:
            complete + model answer

        Any correct attempt:
            complete

        Evaluation failure:
            no attempt consumed
    """

    # ========================================================
    # LOAD ACTIVE QUIZ
    # ========================================================

    quiz_data = await get_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
        user_id=user_id,
    )

    if quiz_data is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active quiz found.",
        )

    # ========================================================
    # FIND QUESTION
    # ========================================================

    question = get_redis_question(
        quiz_data=quiz_data,
        question_number=question_number,
    )

    # ========================================================
    # PREVENT ANSWERING COMPLETED QUESTIONS
    # ========================================================

    if is_question_completed(
        question
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is already completed.",
        )

    # ========================================================
    # GET ATTEMPTS
    # ========================================================

    attempts = question.setdefault(
        "attempts",
        [],
    )

    # ========================================================
    # MAXIMUM ATTEMPTS
    # ========================================================

    if len(attempts) >= MAX_ATTEMPTS:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum attempts reached.",
        )

    attempt_number = (
        len(attempts) + 1
    )

    # ========================================================
    # EVALUATE ANSWER
    # ========================================================

    evaluation = evaluate_answer(
        question=question["question"],
        model_answer=question["model_answer"],
        user_answer=user_answer,
    )

    # ========================================================
    # EVALUATION FAILURE
    #
    # Do NOT consume an attempt.
    # ========================================================

    if evaluation is None:

        return {
            "error": (
                "The answer could not be evaluated. "
                "Please try again."
            ),
            "question_number": (
                question_number
            ),
            "question_completed": False,
            "quiz_completed": False,
        }

    # ========================================================
    # EXTRACT EVALUATION
    # ========================================================

    is_correct = evaluation[
        "is_correct"
    ]

    feedback = evaluation[
        "feedback"
    ]

    hint = evaluation.get(
        "hint"
    )

    # ========================================================
    # STORE SUCCESSFULLY EVALUATED ATTEMPT
    # ========================================================

    attempts.append(
        {
            "attempt_number": (
                attempt_number
            ),
            "user_answer": user_answer,
            "is_correct": is_correct,
            "feedback": feedback,
        }
    )

    # ========================================================
    # CORRECT ANSWER
    # ========================================================

    if is_correct:

        question["completed"] = True

    # ========================================================
    # THIRD WRONG ATTEMPT
    # ========================================================

    elif attempt_number == MAX_ATTEMPTS:

        question["completed"] = True

    # ========================================================
    # CHECK WHOLE QUIZ
    # ========================================================

    quiz_completed = (
        is_redis_quiz_completed(
            quiz_data
        )
    )

    # ========================================================
    # WHOLE QUIZ COMPLETED
    # ========================================================

    if quiz_completed:

        quiz_record = (
            await save_completed_quiz_to_db(
                db=db,
                chat_id=chat_id,
                quiz_data=quiz_data,
            )
        )

        # ----------------------------------------------------
        # Redis is deleted ONLY after the DB transaction
        # has successfully committed.
        # ----------------------------------------------------

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
            "question_number": (
                question_number
            ),
            "model_answer": (
                None
                if is_correct
                else question[
                    "model_answer"
                ]
            ),
            "quiz_id": str(
                quiz_record.id
            ),
        }

    # ========================================================
    # QUIZ STILL ACTIVE
    #
    # Save updated attempts/completion state to Redis.
    # ========================================================

    await save_redis_quiz(
        redis_client=redis_client,
        chat_id=chat_id,
        quiz_data=quiz_data,
    )

    # ========================================================
    # WRONG ANSWER
    # ========================================================

    if not is_correct:

        return {
            "correct": False,
            "explanation": feedback,
            "hint": (
                hint
                if attempt_number
                < MAX_ATTEMPTS
                else None
            ),
            "question_completed": (
                attempt_number
                == MAX_ATTEMPTS
            ),
            "quiz_completed": False,
            "question_number": (
                question_number
            ),
            "model_answer": (
                question["model_answer"]
                if attempt_number
                == MAX_ATTEMPTS
                else None
            ),
        }

    # ========================================================
    # CORRECT ANSWER
    # ========================================================

    return {
        "correct": True,
        "explanation": feedback,
        "hint": None,
        "question_completed": True,
        "quiz_completed": False,
        "question_number": (
            question_number
        ),
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
    """
    Persist a completed Redis quiz to PostgreSQL.

    PostgreSQL stores ONLY the final evaluated attempt for
    each question.

    Redis stores:
        - all evaluated attempts
        - active question state

    PostgreSQL stores:
        - final user answer
        - final correctness
        - final feedback
        - number of evaluated attempts
    """

    questions = quiz_data.get(
        "questions",
        [],
    )

    # ========================================================
    # VALIDATE QUIZ
    # ========================================================

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

        # ====================================================
        # GET EXISTING QUIZ
        # ====================================================

        result = await db.execute(
            select(Quiz).where(
                Quiz.chat_id == chat_id
            )
        )

        quiz_record = (
            result.scalar_one_or_none()
        )

        # ====================================================
        # CREATE QUIZ IF FIRST COMPLETED BATCH
        # ====================================================

        if quiz_record is None:

            quiz_record = Quiz(
                chat_id=chat_id,
                last_message_id=UUID(
                    quiz_data[
                        "last_message_id"
                    ]
                ),
                completed_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )

            db.add(
                quiz_record
            )

            await db.flush()

        # ====================================================
        # UPDATE EXISTING QUIZ
        # ====================================================

        else:

            # ------------------------------------------------
            # The cursor is advanced only after the active
            # batch has been completely completed.
            # ------------------------------------------------

            quiz_record.last_message_id = UUID(
                quiz_data[
                    "last_message_id"
                ]
            )

            # ------------------------------------------------
            # completed_at represents the last successfully
            # completed batch.
            # ------------------------------------------------

            quiz_record.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

        # ====================================================
        # PERSIST ONE QUESTION PER REDIS QUESTION
        #
        # ONLY THE FINAL SUCCESSFULLY EVALUATED ATTEMPT IS
        # SAVED.
        # ====================================================

        for redis_question in questions:

            attempts = (
                redis_question.get(
                    "attempts",
                    [],
                )
            )

            if not attempts:

                raise ValueError(
                    "Completed question has no attempts."
                )

            # ------------------------------------------------
            # Because evaluation failures are never appended,
            # the final item in this list is the final
            # successfully evaluated attempt.
            # ------------------------------------------------

            final_attempt = attempts[-1]

            question_record = Question(
                quiz_id=quiz_record.id,
                question_number=(
                    redis_question[
                        "question_number"
                    ]
                ),
                question=(
                    redis_question[
                        "question"
                    ]
                ),
                model_answer=(
                    redis_question[
                        "model_answer"
                    ]
                ),
                user_answer=(
                    final_attempt[
                        "user_answer"
                    ]
                ),
                is_correct=(
                    final_attempt[
                        "is_correct"
                    ]
                ),
                ai_feedback=(
                    final_attempt[
                        "feedback"
                    ]
                ),
                attempts_used=len(
                    attempts
                ),
            )

            db.add(
                question_record
            )

        # ====================================================
        # COMMIT EVERYTHING AT ONCE
        # ====================================================

        await db.commit()

        # ====================================================
        # REFRESH QUIZ
        # ====================================================

        await db.refresh(
            quiz_record
        )

        return quiz_record

    except Exception:

        await db.rollback()

        raise
