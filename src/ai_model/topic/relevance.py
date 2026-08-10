from src.ai_model.llm.client import client, is_client_available
from src.ai_model.config import MODEL


def check_relevance(topic, question):
    if not is_client_available():
        return True


    prompt=f"""

Current conversation topic:

{topic}


New question:

{question}


Is this question related?

Answer ONLY YES or NO.

"""


    response=client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ],

        temperature=0

    )

    if not response.choices:
        print(response)
        return "General"

    return response.choices[0].message.content.strip()


    return (
        response
        .choices[0]
        .message
        .content
        .strip()
        .upper()
        ==
        "YES"
    )