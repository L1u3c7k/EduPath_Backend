import json

from src.ai_model.llm.client import (
    client,
    is_client_available,
)

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
7. If the answer is correct, the hint must be null.
8. The feedback must explain why the student's answer is correct or
   incorrect.
9. Return ONLY valid JSON.
10. Do not use markdown code fences.

Return exactly:

{{
    "is_correct": true,
    "feedback": "Explanation of why the answer is correct or incorrect.",
    "hint": "A useful hint for the student."
}}

If the answer is correct:

{{
    "is_correct": true,
    "feedback": "Explanation of why the answer is correct.",
    "hint": null
}}
"""


def evaluate_answer(
    question: str,
    model_answer: str,
    user_answer: str,
) -> dict | None:

    # --------------------------------------------------------
    # Check LLM availability.
    # --------------------------------------------------------

    if not is_client_available():

        return None

    # --------------------------------------------------------
    # Clean user answer.
    # --------------------------------------------------------

    user_answer = user_answer.strip()

    if not user_answer:

        return None

    # --------------------------------------------------------
    # Build evaluation prompt.
    # --------------------------------------------------------

    prompt = EVALUATION_PROMPT.format(
        question=question,
        model_answer=model_answer,
        user_answer=user_answer,
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
            temperature=0,
        )

        # ----------------------------------------------------
        # No provider choices.
        # ----------------------------------------------------

        if not response.choices:

            print(
                "⚠️ Quiz evaluator returned no choices."
            )

            print(response)

            return None

        # ----------------------------------------------------
        # Extract response.
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

            result = json.loads(
                content
            )

        except json.JSONDecodeError:

            print(
                "⚠️ Quiz evaluator returned invalid JSON:"
            )

            print(content)

            return None

        # ----------------------------------------------------
        # Validate top-level response.
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict,
        ):

            print(
                "⚠️ Quiz evaluator returned invalid data."
            )

            return None

        # ----------------------------------------------------
        # Validate is_correct.
        # ----------------------------------------------------

        if "is_correct" not in result:

            print(
                "⚠️ Quiz evaluator response is missing "
                "'is_correct'."
            )

            return None

        if not isinstance(
            result["is_correct"],
            bool,
        ):

            print(
                "⚠️ Quiz evaluator returned an invalid "
                "'is_correct' value."
            )

            return None

        # ----------------------------------------------------
        # Validate feedback.
        # ----------------------------------------------------

        feedback = result.get(
            "feedback"
        )

        if not isinstance(
            feedback,
            str,
        ):

            print(
                "⚠️ Quiz evaluator returned invalid feedback."
            )

            return None

        feedback = feedback.strip()

        if not feedback:

            print(
                "⚠️ Quiz evaluator returned empty feedback."
            )

            return None

        # ----------------------------------------------------
        # Validate hint.
        # ----------------------------------------------------

        hint = result.get(
            "hint"
        )

        if hint is not None:

            if not isinstance(
                hint,
                str,
            ):

                print(
                    "⚠️ Quiz evaluator returned invalid hint."
                )

                return None

            hint = hint.strip()

            if not hint:

                hint = None

        # ----------------------------------------------------
        # Correct answers should never have a hint.
        # ----------------------------------------------------

        if result["is_correct"]:

            hint = None

        # ----------------------------------------------------
        # Return normalized evaluation.
        # ----------------------------------------------------

        return {
            "is_correct": result[
                "is_correct"
            ],
            "feedback": feedback,
            "hint": hint,
        }

    except Exception as e:

        print(
            f"⚠️ Quiz evaluator exception: {e}"
        )

        return None