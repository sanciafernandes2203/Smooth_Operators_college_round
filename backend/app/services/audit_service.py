"""
Audit Service

Business logic for audit creation and management.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.db.repositories import AuditRepository, SourceDocumentRepository
from app.db.models import Audit, Claim, Evidence, SourceDocument
from app.schemas.audit import AuditCreateResponse
from app.schemas.claim import ClaimCreate, ExtractedClaim
from app.services.documents import DocumentService, DocumentProcessingResult
from app.services.llm import ClaimExtractor
from app.services.retrieval import EvidenceRetriever, create_retriever
from app.services.verification import ClaimVerifier, EvidenceValidator, create_evidence_validator, EvidenceValidationResult, ClaimValidationResult
from app.services.reports import ReportService, create_report_service


class AuditService:
    """Service layer for audit operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditRepository(session)
        self.doc_repo = SourceDocumentRepository(session)
        self.document_service = DocumentService()
        self.claim_extractor = ClaimExtractor()
        self.evidence_retriever = create_retriever()
        self.claim_verifier = ClaimVerifier()
        self.evidence_validator = create_evidence_validator()
        self.report_service = create_report_service()

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
    ) -> tuple[List[ExtractedClaim], List[dict]]:
        """
        Full pipeline: extract claims, retrieve evidence, verify claims, validate evidence.

        This is the Stage 6 + 7 + 8 + 9 pipeline:
        1. Extract claims from the answer (Stage 6)
        2. Retrieve evidence for each claim (Stage 7)
        3. Verify each claim against evidence (Stage 8)
        4. Validate evidence quotations and references (Stage 9)
        5. Store claims and evidence in database with verdicts

        Args:
            audit_id: The audit to process

        Returns:
            Tuple of (extracted_claims, verification_results)

        Raises:
            ValueError: If audit not found
        """
        # Get the audit with source documents and passages
        audit = await self._get_audit_with_passages(audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found")

        # Collect all passages from source documents
        all_passages = self._collect_all_passages(audit)

        # Stage 6: Extract claims from the answer
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

        # Stage 7: Retrieve evidence for each claim
        passages_by_claim = {}
        for claim in claims:
            result = self.evidence_retriever.retrieve(claim.claim_text, all_passages)
            passages_by_claim[claim.claim_text] = result.passages

        # Stage 8: Verify each claim against evidence
        verification_results = await self.claim_verifier.verify_claims_batch(claims, passages_by_claim)

        # Store claims and evidence in database
        stored_claims = []
        for i, (extracted_claim, verification) in enumerate(zip(claims, verification_results)):
            claim = Claim(
                audit_id=audit_id,
                claim_text=extracted_claim.claim_text,
                verdict=verification.verdict,
                explanation=verification.explanation,
                evidence_strength=verification.evidence_strength,
                requires_review=verification.requires_review or not extracted_claim.is_checkable,
            )
            self.session.add(claim)
            await self.session.flush()  # Get the claim ID

            # Store evidence
            for ev in verification.evidence:
                evidence = Evidence(
                    claim_id=claim.id,
                    document_id=ev.get("document_id"),
                    passage_text=ev.get("quote", ""),
                    page_number=ev.get("page_number"),
                    relationship_type=ev.get("relationship", "context"),
                    validated=False,  # Will be validated in Stage 9
                )
                self.session.add(evidence)

            stored_claims.append((claim, extracted_claim, verification))

        await self.session.flush()

        # Stage 9: Validate evidence quotations and references
        # Collect all source passages for validation
        all_passages = self._collect_all_passages(audit)
        source_documents = {doc.id: doc for doc in audit.source_documents}

        # Get claims with evidence for validation
        # Reload audit with claims and evidence
        audit_with_claims = await self.audit_repo.get_by_id(audit_id)

        validation_results = self.evidence_validator.validate_audit_evidence(
            audit=audit_with_claims,
            claims=audit_with_claims.claims,
            source_passages=all_passages,
        )

        # Update evidence validation status in database
        for claim_validation in validation_results:
            claim_obj = await self.session.get(Claim, claim_validation.claim_id)
            if claim_obj:
                for i, ev_validation in enumerate(claim_validation.evidence_validations):
                    if i < len(claim_obj.evidence):
                        claim_obj.evidence[i].validated = ev_validation.validated

        # Update audit with claim count
        await self.audit_repo.update_total_claims(audit_id, len(claims))

        # Determine final audit status
        has_errors = any(r.has_errors for r in validation_results)
        if has_errors:
            await self.audit_repo.update_status(audit_id, "FAILED")
        else:
            await self.audit_repo.update_status(audit_id, "COMPLETED")

        await self.session.commit()

        # Return extracted claims and verification results for response
        results = []
        for claim, extracted_claim, verification in stored_claims:
            results.append({
                "claim": extracted_claim,
                "verification": verification,
            })

        return claims, results

    def _collect_all_passages(self, audit: Audit) -> List:
        """Collect all text passages from an audit's source documents."""
        all_passages = []
        for doc in audit.source_documents:
            # Re-process document to get passages
            # In a full implementation, passages would be stored in the database
            # For now, re-process from stored text
            if doc.processing_status == "PROCESSED":
                # For pasted text, we need to re-chunk
                if doc.file_name == "pasted-source.txt":
                    from uuid import uuid4
                    from app.services.documents.text_chunker import TextChunker
                    chunker = TextChunker()
                    # We don't have the original text stored, so we'd need to store it
                    # For now, this is a limitation
                    pass
        return []

    async def _get_audit_with_passages(self, audit_id: UUID) -> Optional[Audit]:
        """Get audit with source documents and their extracted text for passage reconstruction."""
        # Get audit with source documents
        stmt = (
            select(Audit)
            .where(Audit.id == audit_id)
            .options(
                selectinload(Audit.source_documents),
            )
        )
        result = await self.session.execute(stmt)
        audit = result.unique().scalar_one_or_none()
        return audit

    async def get_claims_for_audit(self, audit_id: UUID) -> List[Claim]:
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

    async def process_full_audit(self, audit_id: UUID) -> dict:
        """
        Process a complete audit from claim extraction through evidence validation.

        This is the main entry point for the full pipeline.

        Returns:
            Dict with processing results
        """
        try:
            claims, results = await self.process_audit_claims(audit_id)
            return {
                "success": True,
                "claims_processed": len(claims),
                "claims": results,
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            await self.audit_repo.update_status(audit_id, "FAILED")
            await self.session.commit()
            return {
                "success": False,
                "error": f"Unexpected error: {e}",
            }

    def generate_report(self, audit: Audit, format: str = "markdown") -> str:
        """
        Generate a report for the given audit.

        Args:
            audit: The audit with all relationships loaded
            format: Output format ("markdown" or "json")

        Returns:
            Formatted report string
        """
        return self.report_service.generate_report(audit, format)