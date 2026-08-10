from src.ai_model.llm.client import client, is_client_available
from src.ai_model.llm.prompt import ANSWER_PROMPT
from src.ai_model.config import MODEL


def generate_answer(question, context):
    if not is_client_available():
        return "I can’t answer yet because the LLM client is not configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY and a valid base URL if needed."


    prompt = ANSWER_PROMPT.format(
        question=question,
        context=context
    )


    response = client.chat.completions.create(

        model=MODEL,

        messages=[

            {
                "role":"user",
                "content":prompt
            }

        ],

        temperature=0.2

    )

    if not response.choices:
        print(response)
        return "General"

    return response.choices[0].message.content.strip()