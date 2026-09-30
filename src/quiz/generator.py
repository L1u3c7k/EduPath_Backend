import json

from src.ai_model.llm.client import client, is_client_available
from src.ai_model.config import MODEL


QUIZ_PROMPT = """
You are generating study questions for an AI tutoring system.

The questions must be based ONLY on the provided chat history.

CHAT HISTORY:
{chat_history}

Generate exactly 5 study questions.

For each question, provide:
- question
- model_answer

The model_answer should be the correct answer that will later be used
by the system to evaluate the student's answer.

Requirements:
1. Questions must be directly based on the concepts discussed in the chat history.
2. Do not introduce concepts that were not discussed.
3. Questions should test understanding, not merely copy the wording of the chat.
4. Each question must have one clear expected answer.
5. Keep the questions appropriate for a student studying the given material.
6. Do not include explanations, hints, or feedback.
7. Return ONLY valid JSON.
8. Do not wrap the JSON in markdown code fences.

Return exactly this structure:

{
    "questions": [
        {
            "question": "Question 1",
            "model_answer": "Expected answer 1"
        },
        {
            "question": "Question 2",
            "model_answer": "Expected answer 2"
        },
        {
            "question": "Question 3",
            "model_answer": "Expected answer 3"
        },
        {
            "question": "Question 4",
            "model_answer": "Expected answer 4"
        },
        {
            "question": "Question 5",
            "model_answer": "Expected answer 5"
        }
    ]
}
"""


def generate_quiz_questions(
    chat_history: str,
) -> list[dict]:

    if not is_client_available():
        return []

    prompt = QUIZ_PROMPT.format(
        chat_history=chat_history
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    if not response.choices:
        print(response)
        return []

    content = response.choices[0].message.content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("⚠️ Quiz generator returned invalid JSON:")
        print(content)
        return []

    questions = data.get("questions")

    if not isinstance(questions, list):
        return []

    if len(questions) != 5:
        print(
            f"⚠️ Expected 5 questions, got {len(questions)}"
        )
        return []

    for item in questions:

        if not isinstance(item, dict):
            return []

        if not item.get("question"):
            return []

        if not item.get("model_answer"):
            return []

    return questions