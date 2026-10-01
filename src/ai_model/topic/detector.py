from src.ai_model.topic.subject import get_subject


def detect_topic(
    docs: list[dict],
) -> dict | None:

    if not docs:
        return None

    subject_counts = {}

    # Count subjects among retrieved documents
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

        subject = subject.strip()

        if not subject:
            continue

        subject_counts[subject] = (
            subject_counts.get(subject, 0) + 1
        )

    if not subject_counts:
        return None

    # Select the most common subject
    subject = max(
        subject_counts,
        key=subject_counts.get
    )

    # Find the highest-ranked document
    # belonging to the detected subject
    for doc in docs:

        metadata = doc.get(
            "metadata",
            {}
        )

        doc_subject = get_subject(
            metadata
        )

        if not doc_subject:
            continue

        if doc_subject.strip().lower() != subject.lower():
            continue

        return {
            "subject": subject,
            "chapter": metadata.get("chapter"),
            "topic": metadata.get("topic"),
            "subtopic": metadata.get("subtopic"),
        }

    return {
        "subject": subject,
        "chapter": None,
        "topic": None,
        "subtopic": None,
    }