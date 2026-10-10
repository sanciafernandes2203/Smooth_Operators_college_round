"""
Audit Service

Business logic for audit creation and management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import AuditRepository, SourceDocumentRepository
from app.db.models import Audit, Claim, SourceDocument
from app.schemas.audit import AuditCreateResponse
from app.schemas.claim import ClaimCreate, ExtractedClaim
from app.services.documents import DocumentService, DocumentProcessingResult
from app.services.llm import ClaimExtractor
from app.services.retrieval import EvidenceRetriever, create_retriever


class AuditService:
    """Service layer for audit operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditRepository(session)
        self.doc_repo = SourceDocumentRepository(session)
        self.document_service = DocumentService()
        self.claim_extractor = ClaimExtractor()
        self.evidence_retriever = create_retriever()

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
        all_passages = []
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
                # Collect passages for evidence retrieval
                all_passages.extend(doc_result.passages)

        # Also process pasted source text for passages
        if source_text and source_text.strip():
            # Create a temporary document result for the pasted text
            from uuid import uuid4
            from app.services.documents.text_chunker import TextChunker
            chunker = TextChunker()
            chunk_result = chunker.chunk_plain_text(
                text=source_text.strip(),
                document_id=uuid4(),
                document_name="pasted-source.txt",
            )
            all_passages.extend(chunk_result.passages)

        # Commit the transaction
        await self.session.commit()
        await self.session.refresh(audit)

        return AuditCreateResponse(
            audit_id=audit.id,
            status=audit.status,
            created_at=audit.created_at,
        )

    async def process_audit_claims(
        self,
        audit_id: UUID,
    ) -> tuple[list[ExtractedClaim], list[TextPassage]]:
        """
        Extract claims from the audit's answer and retrieve evidence.

        This is the Stage 6 + 7 pipeline:
        1. Extract claims from the answer (Stage 6)
        2. Retrieve evidence for each claim (Stage 7)
        3. Store claims and evidence in database

        Args:
            audit_id: The audit to process

        Returns:
            Tuple of (extracted_claims, all_passages)

        Raises:
            ValueError: If audit not found
        """
        # Get the audit with source documents
        audit = await self.audit_repo.get_by_id(audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found")

        # Collect all passages from source documents
        all_passages = []
        for doc in audit.source_documents:
            # We need to re-process the documents to get passages
            # For now, we'll note this limitation and process from source text
            pass

        # For the initial implementation, we extract claims from the answer
        # and retrieve evidence from the available passages
        extraction_result = await self.claim_extractor.extract_claims(audit.original_answer)

        if extraction_result.error:
            # Update audit status to FAILED
            await self.audit_repo.update_status(audit_id, "FAILED")
            await self.session.commit()
            raise ValueError(f"Claim extraction failed: {extraction_result.error}")

        claims = extraction_result.claims

        if not claims:
            # No claims extracted - update audit as completed with 0 claims
            await self.audit_repo.update_status(audit_id, "COMPLETED")
            await self.audit_repo.update_total_claims(audit_id, 0)
            await self.session.commit()
            return [], []

        # Store claims in database
        stored_claims = []
        for extracted_claim in claims:
            claim = Claim(
                audit_id=audit_id,
                claim_text=extracted_claim.claim_text,
                verdict="PENDING",
                explanation="",
                evidence_strength=None,
                requires_review=not extracted_claim.is_checkable,
            )
            self.session.add(claim)
            stored_claims.append((claim, extracted_claim))

        await self.session.flush()

        # Collect all passages from source documents for retrieval
        # In a full implementation, we'd have stored passages from document processing
        # For now, we'll extract from the answer's source_text if available
        # This is a limitation of the current implementation

        # Update audit with claim count
        await self.audit_repo.update_total_claims(audit_id, len(claims))

        # Mark audit as ready for verification (Stage 8)
        await self.audit_repo.update_status(audit_id, "COMPLETED")
        await self.session.commit()

        return claims, []

    async def get_claims_for_audit(self, audit_id: UUID) -> list[Claim]:
        """Get all claims for an audit."""
        audit = await self.audit_repo.get_by_id(audit_id)
        if audit is None:
            return []
        return audit.claims

    async def retrieve_evidence_for_claim(
        self,
        claim_id: UUID,
        passages: list,
    ) -> list:
        """
        Retrieve evidence passages for a specific claim.

        Args:
            claim_id: The claim to retrieve evidence for
            passages: List of available source passages

        Returns:
            List of retrieved passages with scores
        """
        claim = await self.session.get(Claim, claim_id)
        if claim is None:
            return []

        result = self.evidence_retriever.retrieve(claim.claim_text, passages)
        return result.passages

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