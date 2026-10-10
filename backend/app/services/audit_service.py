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
from app.services.documents import DocumentService, DocumentProcessingResult


class AuditService:
    """Service layer for audit operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditRepository(session)
        self.doc_repo = SourceDocumentRepository(session)
        self.document_service = DocumentService()

    async def create_audit(
        self,
        *,
        answer: str,
        source_text: Optional[str] = None,
        title: Optional[str] = None,
    ) -> AuditCreateResponse:
        """
        Create a new audit with initial data (no file processing).

        For backward compatibility with Stage 3 API.
        """
        return await self.create_audit_with_files(
            answer=answer,
            source_text=source_text,
            title=title,
            files=None,
        )

    async def create_audit_with_files(
        self,
        *,
        answer: str,
        source_text: Optional[str] = None,
        files: Optional[list[tuple[bytes, str, str]]] = None,  # (content, filename, mime_type)
        title: Optional[str] = None,
    ) -> AuditCreateResponse:
        """
        Create a new audit with file processing.

        Args:
            answer: The AI-generated answer to audit
            source_text: Optional pasted source text
            files: Optional list of (content, filename, mime_type) tuples
            title: Optional audit title

        Returns:
            AuditCreateResponse with audit_id and status
        """
        # Create the audit record
        audit = await self.audit_repo.create(
            original_answer=answer,
            title=title,
            status="PROCESSING",
        )

        # Process pasted source text
        if source_text and source_text.strip():
            await self.doc_repo.create(
                audit_id=audit.id,
                file_name="pasted-source.txt",
                mime_type="text/plain",
                storage_path=None,
                processing_status="PROCESSED",
                page_count=1,
            )

        # Process uploaded files
        if files:
            doc_results = self.document_service.process_multiple(files)
            for doc_result in doc_results:
                await self.doc_repo.create(
                    audit_id=audit.id,
                    file_name=doc_result.filename,
                    mime_type=doc_result.mime_type,
                    storage_path=None,
                    processing_status=doc_result.processing_status,
                    page_count=doc_result.page_count,
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