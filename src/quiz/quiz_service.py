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
# GET CURRENT QUESTION
# ============================================================

async def get_current_question(
    db: AsyncSession,
    quiz: Quiz,
) -> Question | None:

    result = await db.execute(
        select(Question)
        .where(
            Question.quiz_id == quiz.id,
            Question.question_number
            == quiz.current_question,
        )
    )

    return result.scalar_one_or_none()


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
        db,
        chat.id,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # If a current question already exists,
    # do NOT generate another batch.
    #
    # This allows the frontend to safely call
    # POST /{chat_id}/quiz multiple times without
    # creating duplicate questions.
    # --------------------------------------------------------

    if quiz is not None:

        current_question = await get_current_question(
            db=db,
            quiz=quiz,
        )

        if current_question is not None:
            return (
                quiz,
                current_question,
                None,
            )

    # --------------------------------------------------------
    # Determine which messages have already been used
    # --------------------------------------------------------

    last_message_id = None

    if quiz is not None:
        last_message_id = quiz.last_message_id

    # --------------------------------------------------------
    # Get new chat messages
    # --------------------------------------------------------

    messages = await get_quiz_messages(
        db,
        chat.id,
        last_message_id,
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
    # Format history for LLM
    # --------------------------------------------------------

    chat_history = format_chat_history(
        messages
    )

    # --------------------------------------------------------
    # Generate 5 questions
    # --------------------------------------------------------

    generated_questions = generate_quiz_questions(
        chat_history
    )

    if len(generated_questions) != BATCH_SIZE:
        return (
            quiz,
            None,
            "The quiz generator did not return "
            "exactly 5 questions.",
        )

    # --------------------------------------------------------
    # Create quiz if this is the first batch
    # --------------------------------------------------------

    if quiz is None:

        quiz = Quiz(
            chat_id=chat.id,
            current_question=1,
            last_message_id=messages[-1].id,
        )

        db.add(quiz)

        await db.flush()

        starting_number = 1

    # --------------------------------------------------------
    # Existing quiz:
    # generate questions after the previous batch
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
    # Remember the last chat message used
    # --------------------------------------------------------

    quiz.last_message_id = messages[-1].id

    await db.flush()

    # --------------------------------------------------------
    # Return first question of this batch
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
            func.count(QuizAttempt.id)
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
# GET NEXT QUESTION
# ============================================================

async def get_next_question(
    db: AsyncSession,
    quiz: Quiz,
) -> Question | None:

    result = await db.execute(
        select(Question)
        .where(
            Question.quiz_id == quiz.id,
            Question.question_number
            == quiz.current_question,
        )
    )

    return result.scalar_one_or_none()


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
        db,
        question.id,
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

    # ========================================================
    # CORRECT ANSWER
    # ========================================================

    if is_correct:

        # Move to next question
        quiz.current_question += 1

        next_question = await get_next_question(
            db,
            quiz,
        )

        return {
            "correct": True,
            "explanation": feedback,
            "hint": None,
            "question_completed": True,
            "quiz_completed": (
                next_question is None
            ),
            "next_question": next_question,
            "model_answer": None,
        }

    # ========================================================
    # WRONG ANSWER — ATTEMPTS REMAIN
    # ========================================================

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

    # ========================================================
    # WRONG ANSWER — THIRD ATTEMPT
    # ========================================================

    # Third wrong attempt:
    # reveal the model answer and move on.

    quiz.current_question += 1

    next_question = await get_next_question(
        db,
        quiz,
    )

    return {
        "correct": False,
        "explanation": feedback,
        "hint": None,
        "question_completed": True,
        "quiz_completed": (
            next_question is None
        ),
        "next_question": next_question,
        "model_answer": question.model_answer,
    }