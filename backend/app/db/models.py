"""
SQLAlchemy ORM Models

Models correspond to the database schema defined in sql/schema.sql.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Audit(Base):
    """Audit record - main entity for an auditing session."""

    __tablename__ = "audits"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PROCESSING",
    )
    total_claims: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Audit(id={self.id}, status={self.status})>"


class SourceDocument(Base):
    """Source document uploaded or pasted for an audit."""

    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="UPLOADED",
    )
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    audit: Mapped["Audit"] = relationship(back_populates="source_documents")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_source_documents_audit_id", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<SourceDocument(id={self.id}, file_name={self.file_name})>"


class Claim(Base):
    """Individual claim extracted from an AI-generated answer."""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_strength: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    requires_review: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    audit: Mapped["Audit"] = relationship(back_populates="claims")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_claims_audit_id", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<Claim(id={self.id}, verdict={self.verdict})>"


class Evidence(Base):
    """Evidence passage associated with a claim."""

    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    claim_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    passage_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    relationship_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    validated: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    claim: Mapped["Claim"] = relationship(back_populates="evidence")
    document: Mapped["SourceDocument | None"] = relationship(back_populates="evidence")

    # Indexes
    __table_args__ = (
        Index("idx_evidence_claim_id", "claim_id"),
        Index("idx_evidence_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, relationship={self.relationship_type})>"