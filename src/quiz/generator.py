import json

from src.ai_model.llm.client import (
    client,
    is_client_available,
)

from src.ai_model.config import MODEL


MAX_GENERATED_QUESTIONS = 5


QUIZ_PROMPT = """
You are generating study questions for an AI tutoring system.

The questions must be based ONLY on the provided new chat history.

NEW CHAT HISTORY:
{chat_history}

EXISTING QUIZ QUESTIONS:
{existing_questions}

Generate up to 5 NEW study questions.

Requirements:

1. Questions must be directly based on the new chat history.
2. Do not introduce concepts that were not discussed in the new chat history.
3. Do NOT repeat an existing quiz question.
4. Do NOT substantially rephrase an existing quiz question.
5. A question is redundant if it tests essentially the same knowledge
   as an existing quiz question, even if the wording is different.
6. Generate as many genuinely new questions as the material supports,
   up to a maximum of 5.
7. If the material supports 5 genuinely new questions, generate 5.
8. If the material supports only 4 genuinely new questions, return 4.
9. If the material supports only 3 genuinely new questions, return 3.
10. If the material supports only 2 genuinely new questions, return 2.
11. If the material supports only 1 genuinely new question, return 1.
12. If there are no genuinely new questions, return an empty list.
13. Do not create questions merely to reach 5.
14. Questions should test understanding, not merely copy wording.
15. Each question must have one clear expected answer.
16. Do not include explanations, hints, or feedback.
17. Return ONLY valid JSON.
18. Do not wrap the JSON in markdown code fences.

Before returning the questions:

- Compare every generated question against every existing quiz question.
- Compare every generated question against every other generated question.
- Remove questions that test substantially the same knowledge.
- Remove questions that are only rewordings of existing questions.
- Keep only genuinely distinct questions.

A question is considered a duplicate when it tests substantially
the same:

- fact
- definition
- concept
- relationship
- process
- rule
- mechanism
- understanding

Do not keep two questions merely because their wording is different.

Return exactly this structure:

{{
    "questions": [
        {{
            "question": "Question 1",
            "model_answer": "Expected answer 1"
        }}
    ]
}}
"""


def normalize_question(
    text: str,
) -> str:

    return " ".join(
        text.lower()
        .strip()
        .split()
    )


def generate_quiz_questions(
    chat_history: str,
    existing_questions: list[str],
) -> list[dict] | None:

    # --------------------------------------------------------
    # Check LLM availability.
    # --------------------------------------------------------

    if not is_client_available():

        print(
            "⚠️ Quiz generator unavailable."
        )

        return None

    # --------------------------------------------------------
    # Format existing questions.
    # --------------------------------------------------------

    existing_text = "\n".join(
        f"- {question}"
        for question in existing_questions
    )

    if not existing_text:

        existing_text = (
            "No existing quiz questions."
        )

    # --------------------------------------------------------
    # Build prompt.
    # --------------------------------------------------------

    prompt = QUIZ_PROMPT.format(
        chat_history=chat_history,
        existing_questions=existing_text,
    )

    try:

        # ----------------------------------------------------
        # Call LLM.
        # ----------------------------------------------------

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
        )

        # ----------------------------------------------------
        # Provider returned no choices.
        # ----------------------------------------------------

        if not response.choices:

            print(
                "⚠️ Quiz generator returned no choices."
            )

            print(response)

            return None

        # ----------------------------------------------------
        # Extract content.
        # ----------------------------------------------------

        content = (
            response.choices[0]
            .message
            .content
            .strip()
        )

        # ----------------------------------------------------
        # Parse JSON.
        # ----------------------------------------------------

        try:

            data = json.loads(
                content
            )

        except json.JSONDecodeError:

            print(
                "⚠️ Quiz generator returned invalid JSON:"
            )

            print(content)

            return None

        # ----------------------------------------------------
        # Validate top-level structure.
        # ----------------------------------------------------

        if not isinstance(
            data,
            dict,
        ):

            print(
                "⚠️ Quiz generator returned invalid data."
            )

            return None

        questions = data.get(
            "questions"
        )

        if not isinstance(
            questions,
            list,
        ):

            print(
                "⚠️ Quiz generator response does not "
                "contain a valid questions list."
            )

            return None

        # ----------------------------------------------------
        # Never allow more than 5 questions.
        # ----------------------------------------------------

        questions = questions[
            :MAX_GENERATED_QUESTIONS
        ]

        # ----------------------------------------------------
        # Normalize existing questions.
        #
        # This is a deterministic exact-duplicate check.
        #
        # Semantic duplicate detection is handled by the LLM
        # instructions in QUIZ_PROMPT.
        # ----------------------------------------------------

        existing_normalized = {
            normalize_question(
                question
            )
            for question in existing_questions
        }

        valid_questions = []

        # ----------------------------------------------------
        # Validate generated questions.
        # ----------------------------------------------------

        for item in questions:

            if not isinstance(
                item,
                dict,
            ):
                continue

            question = item.get(
                "question"
            )

            model_answer = item.get(
                "model_answer"
            )

            # ------------------------------------------------
            # Validate question.
            # ------------------------------------------------

            if not isinstance(
                question,
                str,
            ):
                continue

            # ------------------------------------------------
            # Validate model answer.
            # ------------------------------------------------

            if not isinstance(
                model_answer,
                str,
            ):
                continue

            question = question.strip()
            model_answer = model_answer.strip()

            # ------------------------------------------------
            # Reject empty values.
            # ------------------------------------------------

            if not question:
                continue

            if not model_answer:
                continue

            # ------------------------------------------------
            # Normalize question.
            # ------------------------------------------------

            normalized = normalize_question(
                question
            )

            # ------------------------------------------------
            # Reject exact duplicate against historical
            # questions OR an earlier generated question.
            # ------------------------------------------------

            if normalized in existing_normalized:

                continue

            # ------------------------------------------------
            # Reserve this question text so another generated
            # question cannot be exactly identical.
            # ------------------------------------------------

            existing_normalized.add(
                normalized
            )

            valid_questions.append(
                {
                    "question": question,
                    "model_answer": model_answer,
                }
            )

            # ------------------------------------------------
            # Maximum batch size.
            # ------------------------------------------------

            if (
                len(valid_questions)
                >= MAX_GENERATED_QUESTIONS
            ):

                break

        # ----------------------------------------------------
        # Return however many genuinely valid questions the
        # LLM generated.
        #
        # The service decides whether this counts as a valid
        # batch.
        # ----------------------------------------------------

        return valid_questions

    except Exception as e:

        print(
            f"⚠️ Quiz generator exception: {e}"
        )

        return None