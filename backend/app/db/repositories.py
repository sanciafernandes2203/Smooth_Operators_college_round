"""
Database Repositories

Encapsulate database operations for audit-related entities.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Audit, Claim, Evidence, SourceDocument
from app.schemas.errors import ErrorCodes, create_error_response


class DatabaseError(Exception):
    """Raised when a database operation fails."""

    def __init__(self, message: str, code: str = ErrorCodes.DATABASE_ERROR):
        self.message = message
        self.code = code
        super().__init__(message)


class AuditRepository:
    """Repository for audit operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        original_answer: str,
        title: Optional[str] = None,
        status: str = "PROCESSING",
    ) -> Audit:
        """Create a new audit record."""
        audit = Audit(
            original_answer=original_answer,
            title=title,
            status=status,
            total_claims=0,
        )
        self.session.add(audit)
        await self.session.flush()
        await self.session.refresh(audit)
        return audit

    async def get_by_id(self, audit_id: UUID) -> Optional[Audit]:
        """Get an audit by ID with all relationships loaded."""
        stmt = (
            select(Audit)
            .where(Audit.id == audit_id)
            .options(
                selectinload(Audit.source_documents),
                selectinload(Audit.claims).selectinload(Claim.evidence),
            )
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_id_simple(self, audit_id: UUID) -> Optional[Audit]:
        """Get an audit by ID without loading relationships."""
        stmt = select(Audit).where(Audit.id == audit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        audit_id: UUID,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Audit]:
        """Update audit status."""
        audit = await self.get_by_id_simple(audit_id)
        if audit is None:
            return None
        audit.status = status
        if completed_at is not None:
            audit.completed_at = completed_at
        await self.session.flush()
        await self.session.refresh(audit)
        return audit

    async def update_total_claims(self, audit_id: UUID, total_claims: int) -> Optional[Audit]:
        """Update total claims count."""
        audit = await self.get_by_id_simple(audit_id)
        if audit is None:
            return None
        audit.total_claims = total_claims
        await self.session.flush()
        await self.session.refresh(audit)
        return audit

    async def list_audits(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Audit]:
        """List audits with pagination, newest first."""
        stmt = (
            select(Audit)
            .order_by(Audit.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class SourceDocumentRepository:
    """Repository for source document operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        audit_id: UUID,
        file_name: str,
        mime_type: Optional[str] = None,
        storage_path: Optional[str] = None,
        processing_status: str = "UPLOADED",
        page_count: Optional[int] = None,
    ) -> SourceDocument:
        """Create a new source document record."""
        doc = SourceDocument(
            audit_id=audit_id,
            file_name=file_name,
            mime_type=mime_type,
            storage_path=storage_path,
            processing_status=processing_status,
            page_count=page_count,
        )
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, document_id: UUID) -> Optional[SourceDocument]:
        """Get a source document by ID."""
        stmt = select(SourceDocument).where(SourceDocument.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_audit(self, audit_id: UUID) -> list[SourceDocument]:
        """List all source documents for an audit."""
        stmt = select(SourceDocument).where(SourceDocument.audit_id == audit_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_processing_status(
        self,
        document_id: UUID,
        status: str,
        page_count: Optional[int] = None,
    ) -> Optional[SourceDocument]:
        """Update document processing status."""
        doc = await self.get_by_id(document_id)
        if doc is None:
            return None
        doc.processing_status = status
        if page_count is not None:
            doc.page_count = page_count
        await self.session.flush()
        await self.session.refresh(doc)
        return doc