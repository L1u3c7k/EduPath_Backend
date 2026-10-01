def get_subject(
    metadata: dict,
) -> str | None:

    subject = metadata.get(
        "subject"
    )

    if not subject:
        return None

    subject = subject.strip()

    return subject or None