from src.ai_model.topic.session import session
from src.ai_model.topic.detector import detect_topic
from src.ai_model.topic.relevance import check_relevance

from src.ai_model.rag.embedding import embed
from src.ai_model.rag.retrieval import retrieve
from src.ai_model.rag.context import build_context
from src.ai_model.rag.generation import generate_answer



def ai_chat(question):


    # New conversation

    if session.topic is None:


        q_embedding = embed(question)

        docs = retrieve(
            q_embedding
        )


        context = build_context(
            docs
        )


        session.topic = detect_topic(
            question,
            docs
        )


    else:


        if not check_relevance(
            session.topic,
            question
        ):

            return (
                f"This chat is about "
                f"{session.topic}. "
                "Please start a new chat."
            )


        docs = retrieve(
            embed(question)
        )


    context = build_context(
        docs
    )


    answer = generate_answer(
        question,
        context
    )


    session.history.append(
        {
            "user":question,
            "assistant":answer
        }
    )


    return answer