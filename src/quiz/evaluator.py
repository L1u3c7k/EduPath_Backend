import json

from src.ai_model.llm.client import client, is_client_available
from src.ai_model.config import MODEL


EVALUATION_PROMPT = """
You are evaluating a student's answer to a study question.

QUESTION:
{question}

EXPECTED ANSWER:
{model_answer}

STUDENT ANSWER:
{user_answer}

Determine whether the student's answer is correct.

Rules:
1. Judge the meaning of the student's answer, not exact wording.
2. Accept answers that are correct even if they use different wording.
3. Do not accept an answer that contains a fundamentally incorrect concept.
4. If the answer is partially correct but misses an essential part,
   mark it as incorrect.
5. Give a concise explanation of the evaluation.
6. If the answer is incorrect, provide a useful hint without directly
   giving the expected answer.
7. Return ONLY valid JSON.
8. Do not use markdown code fences.

Return exactly:

{
    "is_correct": true,
    "feedback": "Explanation of why the answer is correct or incorrect.",
    "hint": "A useful hint for the student."
}

If the answer is correct, "hint" should be null.
"""


def evaluate_answer(
    question: str,
    model_answer: str,
    user_answer: str,
) -> dict | None:

    if not is_client_available():
        return None

    prompt = EVALUATION_PROMPT.format(
        question=question,
        model_answer=model_answer,
        user_answer=user_answer,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
    )

    if not response.choices:
        print(response)
        return None

    content = (
        response.choices[0]
        .message
        .content
        .strip()
    )

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        print(
            "⚠️ Quiz evaluator returned invalid JSON:"
        )
        print(content)
        return None

    if not isinstance(result, dict):
        return None

    if "is_correct" not in result:
        return None

    if not isinstance(
        result["is_correct"],
        bool,
    ):
        return None

    feedback = result.get("feedback")

    if not isinstance(feedback, str):
        return None

    hint = result.get("hint")

    if hint is not None and not isinstance(
        hint,
        str,
    ):
        return None

    return {
        "is_correct": result["is_correct"],
        "feedback": feedback,
        "hint": hint,
    }