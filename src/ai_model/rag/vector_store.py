from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


EMBEDDING_DIMENSIONS = 1024


class EmbeddedDocument(Base):
    __tablename__ = "embedded_documents"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    document_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS),
        nullable=False
    )

    __table_args__ = (
        Index(
            "ix_embedded_documents_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={
                "embedding": "vector_cosine_ops"
            },
        ),
    )