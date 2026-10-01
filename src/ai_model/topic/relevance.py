from src.ai_model.topic.subject import get_subject


def check_relevance(
    current_subject: str,
    docs: list[dict],
) -> bool:

    if not current_subject:
        return False

    current_subject = current_subject.strip().lower()

    for doc in docs:

        metadata = doc.get(
            "metadata",
            {}
        )

        subject = get_subject(
            metadata
        )

        if not subject:
            continue

        if subject.strip().lower() == current_subject:
            return True

    return False