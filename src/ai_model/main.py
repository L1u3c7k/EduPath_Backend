from src.ai_model.topic.session import session
from src.ai_model.chat.manager import ai_chat


while True:

    question = input("\nUser: ")

    if question == "exit":
        break

    answer = ai_chat(question)

    print("\nAI:", answer)