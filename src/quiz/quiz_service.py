from datetime import datetime, timezone

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
# GET QUIZ
# ============================================================

async def get_quiz(
    db: AsyncSession,
    chat_id: int,
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
    quiz_id: int,
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
    chat: Chat,
) -> tuple[
    Quiz | None,
    Question | None,
    str | None,
]:

    # --------------------------------------------------------
    # Get existing quiz
    # --------------------------------------------------------

    quiz = await get_quiz(
        db=db,
        chat_id=chat.id,
    )

    # --------------------------------------------------------
    # Determine the last processed message
    # --------------------------------------------------------

    last_message_id = None

    if quiz is not None:
        last_message_id = quiz.last_message_id

    # --------------------------------------------------------
    # Get the next batch of unprocessed messages
    #
    # history.py returns the FIRST 5 messages after
    # last_message_id, so older messages are never skipped.
    # --------------------------------------------------------

    messages = await get_quiz_messages(
        db=db,
        chat_id=chat.id,
        last_message_id=last_message_id,
    )

    # --------------------------------------------------------
    # Need at least 5 new messages
    # --------------------------------------------------------

    if len(messages) < BATCH_SIZE:

        return (
            quiz,
            None,
            "Not enough new chat messages "
            "to generate another quiz batch.",
        )

    # --------------------------------------------------------
    # Get existing questions
    # --------------------------------------------------------

    existing_questions = []

    if quiz is not None:

        existing_questions = (
            await get_existing_questions(
                db=db,
                quiz_id=quiz.id,
            )
        )

    existing_question_texts = [
        question.question
        for question in existing_questions
    ]

    # --------------------------------------------------------
    # Format new message batch
    # --------------------------------------------------------

    chat_history = format_chat_history(
        messages
    )

    # --------------------------------------------------------
    # Generate up to 5 new questions
    # --------------------------------------------------------

    generated_questions = (
        generate_quiz_questions(
            chat_history=chat_history,
            existing_questions=(
                existing_question_texts
            ),
        )
    )

    # --------------------------------------------------------
    # GENERATION FAILURE
    #
    # None means the LLM/API failed.
    #
    # IMPORTANT:
    # Do NOT advance last_message_id.
    #
    # This allows the same messages to be retried later.
    # --------------------------------------------------------

    if generated_questions is None:

        return (
            quiz,
            None,
            "Quiz generation failed. "
            "Please try again.",
        )

    # --------------------------------------------------------
    # NO NEW QUESTIONS
    #
    # [] means generation succeeded, but the LLM found
    # no genuinely new questions.
    #
    # These messages have been successfully processed,
    # so we can advance the cursor.
    # --------------------------------------------------------

    if not generated_questions:

        if quiz is not None:

            quiz.last_message_id = messages[-1].id

            await db.flush()

        return (
            quiz,
            None,
            "No new quiz questions could be generated "
            "from the new material.",
        )

    # --------------------------------------------------------
    # Create quiz if this is the first batch
    # --------------------------------------------------------

    if quiz is None:

        quiz = Quiz(
            chat_id=chat.id,
            last_message_id=messages[-1].id,
        )

        db.add(quiz)

        await db.flush()

        starting_number = 1

    # --------------------------------------------------------
    # Existing quiz
    #
    # Continue question numbering.
    # --------------------------------------------------------

    else:

        result = await db.execute(
            select(
                func.max(
                    Question.question_number
                )
            )
            .where(
                Question.quiz_id == quiz.id
            )
        )

        last_question_number = (
            result.scalar_one()
        )

        starting_number = (
            (last_question_number or 0)
            + 1
        )

        # ----------------------------------------------------
        # A new batch makes the quiz incomplete again.
        #
        # This matters if the previous batch had already
        # completed the quiz.
        # ----------------------------------------------------

        quiz.completed_at = None

    # --------------------------------------------------------
    # Save generated questions
    # --------------------------------------------------------

    questions = []

    for index, item in enumerate(
        generated_questions
    ):

        question = Question(
            quiz_id=quiz.id,
            question_number=(
                starting_number + index
            ),
            question=item["question"],
            model_answer=item["model_answer"],
        )

        db.add(question)

        questions.append(question)

    # --------------------------------------------------------
    # Advance cursor only after successful generation
    # --------------------------------------------------------

    quiz.last_message_id = messages[-1].id

    await db.flush()

    # --------------------------------------------------------
    # Return first newly generated question.
    #
    # This is NOT a current_question.
    # Questions can still be answered in any order.
    # --------------------------------------------------------

    return (
        quiz,
        questions[0],
        None,
    )


# ============================================================
# GET ATTEMPT COUNT
# ============================================================

async def get_attempt_count(
    db: AsyncSession,
    question_id: int,
) -> int:

    result = await db.execute(
        select(
            func.count(
                QuizAttempt.id
            )
        )
        .where(
            QuizAttempt.question_id
            == question_id
        )
    )

    return int(
        result.scalar() or 0
    )


# ============================================================
# CHECK QUIZ COMPLETION
# ============================================================

async def is_quiz_completed(
    db: AsyncSession,
    quiz_id: int,
) -> bool:

    # --------------------------------------------------------
    # Get all question IDs
    # --------------------------------------------------------

    result = await db.execute(
        select(Question.id)
        .where(
            Question.quiz_id == quiz_id
        )
    )

    question_ids = result.scalars().all()

    # A quiz with no questions is not completed.
    if not question_ids:
        return False

    # --------------------------------------------------------
    # Find correctly answered questions
    # --------------------------------------------------------

    result = await db.execute(
        select(
            QuizAttempt.question_id
        )
        .where(
            QuizAttempt.question_id.in_(question_ids),
            QuizAttempt.is_correct.is_(True),
        )
        .distinct()
    )

    correctly_answered = set(
        result.scalars().all()
    )

    # --------------------------------------------------------
    # Get attempt counts
    # --------------------------------------------------------

    result = await db.execute(
        select(
            QuizAttempt.question_id,
            func.count(
                QuizAttempt.id
            ).label("attempt_count"),
        )
        .where(
            QuizAttempt.question_id.in_(question_ids)
        )
        .group_by(
            QuizAttempt.question_id
        )
    )

    attempt_counts = {
        question_id: attempt_count
        for question_id, attempt_count
        in result.all()
    }

    # --------------------------------------------------------
    # Every question must be completed.
    #
    # A question is completed if:
    #
    # 1. It was answered correctly at least once
    # OR
    # 2. It reached 3 attempts
    # --------------------------------------------------------

    for question_id in question_ids:

        if question_id in correctly_answered:
            continue

        if attempt_counts.get(
            question_id,
            0
        ) >= MAX_ATTEMPTS:
            continue

        return False

    return True


# ============================================================
# SAVE ATTEMPT
# ============================================================

async def save_attempt(
    db: AsyncSession,
    question: Question,
    attempt_number: int,
    user_answer: str,
    is_correct: bool,
    feedback: str,
) -> QuizAttempt:

    attempt = QuizAttempt(
        question_id=question.id,
        attempt_number=attempt_number,
        user_answer=user_answer,
        is_correct=is_correct,
        feedback=feedback,
    )

    db.add(attempt)

    await db.flush()

    return attempt


# ============================================================
# ANSWER QUESTION
# ============================================================

async def answer_question(
    db: AsyncSession,
    quiz: Quiz,
    question: Question,
    user_answer: str,
) -> dict:

    # --------------------------------------------------------
    # Count previous attempts
    # --------------------------------------------------------

    attempts = await get_attempt_count(
        db=db,
        question_id=question.id,
    )

    # --------------------------------------------------------
    # Maximum 3 attempts
    # --------------------------------------------------------

    if attempts >= MAX_ATTEMPTS:

        return {
            "error": "Maximum attempts reached."
        }

    attempt_number = attempts + 1

    # --------------------------------------------------------
    # Evaluate answer using LLM
    # --------------------------------------------------------

    evaluation = evaluate_answer(
        question=question.question,
        model_answer=question.model_answer,
        user_answer=user_answer,
    )

    # --------------------------------------------------------
    # LLM/API evaluation failure
    #
    # Do NOT save an attempt.
    # --------------------------------------------------------

    if evaluation is None:

        return {
            "error": "The answer could not be evaluated."
        }

    is_correct = evaluation["is_correct"]
    feedback = evaluation["feedback"]
    hint = evaluation["hint"]

    # --------------------------------------------------------
    # Save student's attempt
    # --------------------------------------------------------

    await save_attempt(
        db=db,
        question=question,
        attempt_number=attempt_number,
        user_answer=user_answer,
        is_correct=is_correct,
        feedback=feedback,
    )

    # --------------------------------------------------------
    # CORRECT ANSWER
    #
    # Question is completed immediately.
    # --------------------------------------------------------

    if is_correct:

        quiz_completed = await is_quiz_completed(
            db=db,
            quiz_id=quiz.id,
        )

        if quiz_completed:

            quiz.completed_at = datetime.now(
                timezone.utc
            )

        await db.flush()

        return {
            "correct": True,
            "explanation": feedback,
            "hint": None,
            "question_completed": True,
            "quiz_completed": quiz_completed,
            "next_question": None,
            "model_answer": None,
        }

    # --------------------------------------------------------
    # WRONG ANSWER — ATTEMPTS REMAIN
    # --------------------------------------------------------

    if attempt_number < MAX_ATTEMPTS:

        return {
            "correct": False,
            "explanation": feedback,
            "hint": hint,
            "question_completed": False,
            "quiz_completed": False,
            "next_question": None,
            "model_answer": None,
        }

    # --------------------------------------------------------
    # WRONG ANSWER — THIRD ATTEMPT
    #
    # Question becomes completed.
    # Model answer is revealed.
    # --------------------------------------------------------

    quiz_completed = await is_quiz_completed(
        db=db,
        quiz_id=quiz.id,
    )

    if quiz_completed:

        quiz.completed_at = datetime.now(
            timezone.utc
        )

    await db.flush()

    return {
        "correct": False,
        "explanation": feedback,
        "hint": None,
        "question_completed": True,
        "quiz_completed": quiz_completed,
        "next_question": None,
        "model_answer": question.model_answer,
    }