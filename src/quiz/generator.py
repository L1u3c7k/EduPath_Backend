import json

from src.ai_model.llm.client import (
    client,
    is_client_available,
)

from src.ai_model.config import MODEL


QUIZ_PROMPT = """
You are generating study questions for an AI tutoring system.

The questions must be based ONLY on the provided new chat history.

NEW CHAT HISTORY:
{chat_history}

EXISTING QUIZ QUESTIONS:
{existing_questions}

Generate UP TO 5 NEW study questions.

Requirements:

1. Questions must be directly based on the new chat history.
2. Do not introduce concepts that were not discussed in the new chat history.
3. Do NOT repeat an existing quiz question.
4. Do NOT substantially rephrase an existing quiz question.
5. A question is redundant if it tests essentially the same knowledge
   as an existing quiz question, even if the wording is different.
6. Generate as many genuinely new questions as the material supports,
   up to a maximum of 5.
7. If the material supports only 2 genuinely new questions, return 2.
8. If the material supports only 1 genuinely new question, return 1.
9. If there are no genuinely new questions, return an empty list.
10. Do not create questions merely to reach 5.
11. Questions should test understanding, not merely copy wording.
12. Each question must have one clear expected answer.
13. Do not include explanations, hints, or feedback.
14. Return ONLY valid JSON.
15. Do not wrap the JSON in markdown code fences.

Before returning the questions, compare every generated question
against every existing quiz question and against every other generated
question.

Do not generate a question if it tests substantially the same knowledge,
concept, relationship, definition, or fact as an existing quiz question.

Among the newly generated questions, keep only questions that test
distinct knowledge or understanding.

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


def normalize_question(text: str) -> str:
    return " ".join(
        text.lower().strip().split()
    )


def generate_quiz_questions(
    chat_history: str,
    existing_questions: list[str],
) -> list[dict] | None:

    if not is_client_available():
        print("⚠️ Quiz generator unavailable.")
        return None

    existing_text = "\n".join(
        f"- {question}"
        for question in existing_questions
    )

    if not existing_text:
        existing_text = "No existing quiz questions."

    prompt = QUIZ_PROMPT.format(
        chat_history=chat_history,
        existing_questions=existing_text,
    )

    try:

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

        if not response.choices:
            print(
                "⚠️ Quiz generator returned no choices."
            )
            print(response)
            return None

        content = (
            response.choices[0]
            .message
            .content
            .strip()
        )

        try:

            data = json.loads(content)

        except json.JSONDecodeError:

            print(
                "⚠️ Quiz generator returned invalid JSON:"
            )
            print(content)

            return None

        if not isinstance(data, dict):
            print(
                "⚠️ Quiz generator returned invalid data."
            )
            return None

        questions = data.get("questions")

        if not isinstance(questions, list):
            print(
                "⚠️ Quiz generator response does not "
                "contain a valid questions list."
            )
            return None

        # Never allow more than 5 questions.
        questions = questions[:5]

        existing_normalized = {
            normalize_question(question)
            for question in existing_questions
        }

        valid_questions = []

        for item in questions:

            if not isinstance(item, dict):
                continue

            question = item.get("question")
            model_answer = item.get("model_answer")

            if not isinstance(question, str):
                continue

            if not isinstance(model_answer, str):
                continue

            question = question.strip()
            model_answer = model_answer.strip()

            if not question:
                continue

            if not model_answer:
                continue

            normalized = normalize_question(
                question
            )

            # Prevent exact duplicates against
            # existing quiz questions.
            if normalized in existing_normalized:
                continue

            # Prevent exact duplicates within
            # the newly generated batch.
            existing_normalized.add(normalized)

            valid_questions.append(
                {
                    "question": question,
                    "model_answer": model_answer,
                }
            )

            if len(valid_questions) >= 5:
                break

        return valid_questions

    except Exception as e:

        print(
            f"⚠️ Quiz generator exception: {e}"
        )

        return None