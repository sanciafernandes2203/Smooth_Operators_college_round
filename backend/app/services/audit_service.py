"""
Audit Service

Business logic for audit creation and management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import AuditRepository, SourceDocumentRepository
from app.db.models import Audit
from app.schemas.audit import AuditCreateResponse


class AuditService:
    """Service layer for audit operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditRepository(session)
        self.doc_repo = SourceDocumentRepository(session)

    async def create_audit(
        self,
        *,
        answer: str,
        source_text: Optional[str] = None,
        title: Optional[str] = None,
    ) -> AuditCreateResponse:
        """
        Create a new audit with initial data.

        For Stage 3, we only persist the audit and source text metadata.
        The actual processing (claim extraction, verification) happens in later stages.
        """
        # Create the audit record
        audit = await self.audit_repo.create(
            original_answer=answer,
            title=title,
            status="PROCESSING",
        )

        # Create a source document record for pasted text if provided
        if source_text and source_text.strip():
            await self.doc_repo.create(
                audit_id=audit.id,
                file_name="pasted-source.txt",
                mime_type="text/plain",
                storage_path=None,
                processing_status="PROCESSED",
                page_count=1,
            )

        # Commit the transaction
        await self.session.commit()
        await self.session.refresh(audit)

        return AuditCreateResponse(
            audit_id=audit.id,
            status=audit.status,
            created_at=audit.created_at,
        )

    async def get_audit(self, audit_id: UUID) -> Optional[Audit]:
        """Get an audit by ID with all relationships."""
        return await self.audit_repo.get_by_id(audit_id)

    async def get_audit_simple(self, audit_id: UUID) -> Optional[Audit]:
        """Get an audit by ID without relationships."""
        return await self.audit_repo.get_by_id_simple(audit_id)

    async def list_audits(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Audit]:
        """List audits with pagination."""
        return await self.audit_repo.list_audits(limit=limit, offset=offset)

    async def update_audit_status(
        self,
        audit_id: UUID,
        status: str,
    ) -> Optional[Audit]:
        """Update audit status."""
        completed_at = datetime.utcnow() if status in ("COMPLETED", "FAILED") else None
        return await self.audit_repo.update_status(audit_id, status, completed_at)