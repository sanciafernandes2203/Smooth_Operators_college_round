# Architecture Decisions Log

## ADR-001: FastAPI for API Framework
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need a modern, fast Python web framework with automatic OpenAPI docs, type safety, and async support.

**Decision**: Use FastAPI 0.143+ with Pydantic 2.7+ for validation.

**Consequences**:
- Automatic OpenAPI/Swagger docs at `/docs`
- Native async/await support for I/O-bound operations (LLM calls, DB)
- Type-safe request/response validation via Pydantic
- Easy dependency injection for services and DB sessions

---

## ADR-002: SQLAlchemy 2.0 Async with PostgreSQL
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need reliable, type-safe database access with async support for FastAPI.

**Decision**: Use SQLAlchemy 2.0+ with asyncpg driver, PostgreSQL (Supabase).

**Consequences**:
- Full async/await database operations
- Type-safe ORM models with Mapped annotations
- Repository pattern encapsulates DB logic
- Supabase provides managed PostgreSQL with auth/storage
- Migration path to other PostgreSQL providers

---

## ADR-003: Multi-Provider LLM Client Abstraction
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need to support multiple LLM providers (OpenAI, Anthropic, Gemini) without coupling business logic to specific APIs.

**Decision**: Abstract `BaseLLMClient` with provider-specific implementations and factory pattern.

**Consequences**:
- Single `get_llm_client()` function returns configured client
- Provider-specific logic encapsulated (auth, payload format, errors)
- Structured output support where provider allows (JSON mode)
- Unified error handling with retry logic
- Easy to add new providers

---

## ADR-004: Document Processing Pipeline (PyMuPDF + Tesseract)
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need to extract text from PDFs, images, and text files with page-level provenance.

**Decision**: 
- PyMuPDF (fitz) for PDF text extraction
- Tesseract OCR via pytesseract for scanned pages and images
- Custom TextChunker for provenance-preserving chunking

**Consequences**:
- PyMuPDF is fast and reliable for text-based PDFs
- Tesseract is open-source but requires separate system install
- Chunking preserves page numbers, char offsets, document IDs
- OCR only applied to detected scanned pages (hybrid approach)
- Temporary files cleaned up after processing

---

## ADR-005: Keyword-Based Retrieval (TF-IDF/BM25) over Vector Search
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need to retrieve relevant passages for claims. Vector search would require embeddings and vector DB.

**Decision**: Start with TF-IDF/BM25-inspired keyword retrieval using existing chunked passages.

**Consequences**:
- No external dependencies (no embedding model, no vector DB)
- Fast and deterministic
- Works well for exact/near-exact matches
- Stopword filtering improves relevance
- Can upgrade to embeddings later if needed
- Aligns with PROJECT_BIBLE.md §16.1 "MVP retrieval"

---

## ADR-006: Structured LLM Output via JSON Mode
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Claim extraction needs structured, parseable output from LLM.

**Decision**: Use provider JSON response format where available (OpenAI `response_format`, Gemini `responseMimeType`), fall back to prompt-based for Anthropic.

**Consequences**:
- Eliminates fragile regex parsing of LLM output
- Pydantic validates structure after parsing
- Handles malformed JSON gracefully (extraction attempt)
- Consistent interface across providers

---

## ADR-007: Repository Pattern for Database Access
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need clean separation between business logic and database operations.

**Decision**: Repository classes (`AuditRepository`, `SourceDocumentRepository`) encapsulate all DB queries.

**Consequences**:
- Business logic in services doesn't touch SQLAlchemy directly
- Easy to mock for testing
- Single place to modify queries
- Consistent error handling via `DatabaseError`

---

## ADR-008: Pydantic Schemas as API Contract
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Frontend and backend must agree on exact request/response formats.

**Decision**: All API request/response bodies defined as Pydantic models in `app/schemas/`.

**Consequences**:
- Automatic validation and serialization
- OpenAPI docs generated from schemas
- Frontend can generate TypeScript types from OpenAPI
- Single source of truth for field names and types
- Version-controlled in code

---

## ADR-009: In-Memory Evidence Retrieval (Not Persisted Yet)
**Date**: 2024-10-10
**Status**: Accepted (Temporary)

**Context**: Evidence retrieval needs passages from source documents. Full persistence would require storing all passages in DB.

**Decision**: For Stages 6-7, retrieval operates on in-memory `TextPassage` objects from document processing. Persistence deferred.

**Consequences**:
- Simpler implementation for Stages 6-7
- Retrieval only works for passages currently in memory
- File-based passages need re-processing or DB storage for full pipeline
- Will persist to `evidence` table in Stage 8

---

## ADR-010: Claim Status Flow in Database
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Need to track audit and claim processing state.

**Decision**: 
- Audit: `PROCESSING` → `COMPLETED` / `FAILED`
- Claim: `PENDING` → `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED` / `AMBIGUOUS` / `POTENTIALLY_UNSAFE` / `UNABLE_TO_ASSESS`

**Consequences**:
- Clear state machine for UI
- Easy to query audits by status
- `PENDING` allows showing partial results
- `COMPLETED` means all claims have verdicts

---

## ADR-011: Non-Checkable Claim Classification
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Not all statements in an AI answer are verifiable claims.

**Decision**: LLM marks claims as `is_checkable: false` with `reason_not_checkable` (opinion, vague, prediction, subjective).

**Consequences**:
- UI can filter or display differently
- Verification stage skips non-checkable claims
- Maintains "Unsupported ≠ False" principle
- Transparent about what was verified

---

## ADR-012: Stopword Filtering in Retrieval
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Common words ("the", "of", "and") match everything and drown out relevant terms.

**Decision**: Filter ~60 English stopwords during tokenization in `EvidenceRetriever`.

**Consequences**:
- Improves relevance scoring significantly
- Reduces false positives from common words
- Minimal impact on meaningful terms
- Stopword list extensible

---

## ADR-013: Percentage Sign Preservation
**Date**: 2024-10-10
**Status**: Accepted

**Context**: Percentages (e.g., "60%") are critical for numeric claims but often stripped by tokenizers.

**Decision**: Keep `%` in tokenization regex (`[a-zA-Z0-9%]+`).

**Consequences**:
- "60%" tokenized as single term "60%"
- Matches exact percentage in source text
- Improves numeric claim retrieval accuracy

---

## ADR-014: Error Handling Philosophy
**Date**: 2024-10-10
**Status**: Accepted

**Context**: External services (LLM, OCR, DB) can fail in various ways.

**Decision**: 
- Never fabricate successful results
- Return structured errors with codes
- Log full details server-side
- Client gets safe, actionable messages
- Retry only on transient errors (rate limit, timeout, 5xx)

**Consequences**:
- Predictable error responses for frontend
- No leaked credentials or stack traces
- Graceful degradation (e.g., claim extraction fails → audit marked FAILED)