from src.ai_model.llm.client import client, is_client_available
from src.ai_model.config import MODEL


def detect_topic(question, context):
    if not is_client_available():
        return "General"


    prompt=f"""

Determine the learning topic.

Question:

{question}


Context:

{context}


Return only the topic name.

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