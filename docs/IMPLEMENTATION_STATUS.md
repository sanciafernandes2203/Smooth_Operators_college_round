# Implementation Status Checklist

## Stage 1: Repository & Backend Foundation ✅
- [x] Git repository initialized with `.gitignore`
- [x] FastAPI app with health endpoints (`/api/health`, `/api/health/ready`)
- [x] Pydantic Settings configuration (`.env.example`)
- [x] CORS middleware configured
- [x] Requirements.txt with all dependencies
- [x] Backend README with setup instructions

## Stage 2: Database Setup & Data Models ✅
- [x] SQLAlchemy async models: `Audit`, `SourceDocument`, `Claim`, `Evidence`
- [x] Supabase PostgreSQL schema (`sql/schema.sql`)
- [x] Repository pattern: `AuditRepository`, `SourceDocumentRepository`
- [x] Database connection manager with lifespan handling
- [x] Pydantic schemas for audit API (`AuditCreateRequest`, `AuditCreateResponse`, etc.)
- [x] Standardized error responses (`ErrorCodes`, `ErrorResponse`)

## Stage 3: Audit Submission API ✅
- [x] `POST /api/audits` - accepts answer, source_text, files
- [x] Input validation (required fields, size limits, file types)
- [x] File upload handling with validation
- [x] Audit creation with `PROCESSING` status
- [x] `GET /api/audits` - paginated history
- [x] `GET /api/audits/{audit_id}` - full audit detail

## Stage 4: Document Processing ✅
- [x] File validation (extension, MIME, size)
- [x] TXT extraction with encoding fallbacks
- [x] PDF text extraction (PyMuPDF, page-by-page)
- [x] Scanned page detection
- [x] OCR for images and scanned PDF pages (Tesseract)
- [x] Text chunking with provenance (TextChunker)
- [x] DocumentService orchestrating all processors
- [x] API integration for file uploads in audit creation

## Stage 5: LLM Client Integration ✅
- [x] Abstract `BaseLLMClient` with retry/timeout/error handling
- [x] OpenAI, Anthropic, Gemini implementations
- [x] Factory pattern for provider selection
- [x] Global client singleton with env config
- [x] JSON response format support (OpenAI, Gemini)
- [x] Comprehensive error handling (auth, rate limit, timeout, etc.)

## Stage 6: LLM Claim Extraction ✅
- [x] **Schemas**: `ExtractedClaim`, `ClaimExtractionRequest`, `ClaimExtractionResponse`
- [x] **Service**: `ClaimExtractor` class in `app/services/llm/claim_extractor.py`
- [x] **Prompt**: System prompt for claim extraction (JSON output)
- [x] **Features**:
  - [x] Extracts individual checkable claims
  - [x] Preserves original wording
  - [x] Splits independent claims
  - [x] Marks non-checkable content (opinion, vague, prediction)
  - [x] Handles malformed LLM JSON output
  - [x] Handles LLM errors (rate limit, auth, timeout, etc.)
- [x] **Tests**: 20 tests with mocked LLM responses
- [x] **Integration**: `AuditService.process_audit_claims()` stores claims in DB

## Stage 7: Evidence Retrieval ✅
- [x] **Schemas**: `RetrievedPassage`, `RetrievalResult` (dataclasses)
- [x] **Service**: `EvidenceRetriever` in `app/services/retrieval/evidence_retriever.py`
- [x] **Algorithm**: TF-IDF/BM25-inspired keyword scoring
- [x] **Features**:
  - [x] Keyword-based retrieval with stopword filtering
  - [x] TF-IDF scoring with IDF across passages
  - [x] Provenance preservation (doc_id, doc_name, page, char offsets)
  - [x] Percentage sign (%) preservation in tokenization
  - [x] Hyphenated word handling
  - [x] Configurable min_score, max_results, case_sensitivity
  - [x] Batch retrieval for multiple claims
- [x] **Tests**: 15 tests with local passages (no external deps)
- [x] **Integration**: `AuditService` uses `EvidenceRetriever` for claim evidence

## Stage 8: Claim Verification ✅
- [x] **Schemas**: `VerificationResult` (dataclass), reuses `EvidenceResponse` for evidence
- [x] **Service**: `ClaimVerifier` class in `app/services/verification/claim_verifier.py`
- [x] **Prompt**: `CLAIM_VERIFICATION_SYSTEM_PROMPT` with verdict taxonomy
- [x] **Verdict Taxonomy**: SUPPORTED, CONTRADICTED, UNSUPPORTED, AMBIGUOUS, POTENTIALLY_UNSAFE, UNABLE_TO_ASSESS
- [x] **Features**:
  - [x] Assesses claims ONLY against supplied evidence passages
  - [x] Distinguishes contradiction from lack of evidence
  - [x] Quotes only from supplied passages
  - [x] Explains verdict with evidence references
  - [x] Handles malformed LLM output gracefully
  - [x] Handles LLM errors (rate limit, auth, timeout, connection)
  - [x] Returns structured JSON via LLM `response_format`
  - [x] Non-checkable claims marked with `requires_review`
  - [x] Batch verification for multiple claims
- [x] **Tests**: 12 tests with mocked LLM responses
- [x] **Integration**: `AuditService.process_audit_claims()` calls verification

## Stage 9: Evidence Validation ✅
- [x] **Schemas**: `EvidenceValidationResult`, `ClaimValidationResult`, `ValidationIssue` (dataclasses)
- [x] **Service**: `EvidenceValidator` in `app/services/verification/evidence_validator.py`
- [x] **Algorithm**: Exact/partial quote matching with whitespace normalization + stopword filtering
- [x] **Features**:
  - [x] Exact quote matching in source material
  - [x] Partial match detection with configurable threshold
  - [x] Document ID validation
  - [x] Page number validation (with range checking)
  - [x] Document name matching
  - [x] Stopword filtering for relevance
  - [x] Percentage sign (%) and hyphenated term preservation
  - [x] Whitespace normalization for robust matching
  - [x] Partial match detection with warnings
  - [x] Document name mismatch warnings
  - [x] Page number validation (out of range, unverifiable)
  - [x] Empty quote detection
  - [x] Missing source text detection
  - [x] Per-evidence validation with issues (error/warning/info)
  - [x] Per-claim validation summary with error/warning flags
  - [x] Per-audit validation
  - [x] Provenance preservation (doc_id, page, char offsets, source_type)
  - [x] Configurable match threshold, case sensitivity
- [x] **Tests**: 18 tests with local passages (no external deps)
- [x] **Integration**: `AuditService.process_audit_claims()` calls validation, updates `evidence.validated` flag

---

## Partially Implemented / Known Gaps ⚠️

| Feature | Status | Notes |
|---------|--------|-------|
| Full document passage storage | 🔄 Partial | Passages re-computed on demand; could store in DB for performance |
| Real LLM integration | 🔄 Config needed | Requires `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` in `.env` |
| Tesseract OCR on Windows | 🔄 Setup needed | Requires `TESSERACT_CMD` in `.env` |
| Supabase connection | 🔄 Config needed | Requires valid `DATABASE_URL` in `.env` |
| Evidence persistence in DB | ✅ Complete | Evidence stored with `validated` flag |

---

## Deferred to Future Stages 🚫

| Feature | Stage | Dependencies |
|---------|-------|--------------|
| Report Export (Markdown/JSON) | 10 | Stages 1-9 complete |
| Authentication & User-specific History | 11+ | Not started |
| Embedding-based Semantic Retrieval | 10+ | Optional enhancement |
| PDF Page Preview | 10+ | Optional |

---

## Tests Actually Run & Results

| Test File | Tests | Passed | Skipped | Failed |
|-----------|-------|--------|---------|--------|
| `test_health.py` | 3 | 3 | 0 | 0 |
| `test_audits.py` | 5 | 5 | 0 | 0 |
| `test_documents.py` | 22 | 21 | 1 | 0 |
| `test_llm_client.py` | 23 | 23 | 0 | 0 |
| `test_claim_extraction.py` | 20 | 20 | 0 | 0 |
| `test_retrieval.py` | 15 | 15 | 0 | 0 |
| `test_claim_verification.py` | 12 | 12 | 0 | 0 |
| `test_evidence_validation.py` | 18 | 18 | 0 | 0 |
| **Total** | **120** | **119** | **1** | **0** |

**All 119 tests pass** (1 skipped: OCR service init requires Tesseract executable).

**No live LLM calls** - all use mocked responses.
**No database required for tests** - uses FastAPI ASGITransport with mocked services.

---

## Integration Tests Deferred (Credentials Missing)

| Test | Reason |
|------|--------|
| Real claim extraction with live LLM | Needs `LLM_API_KEY` |
| Real claim verification with live LLM | Needs `LLM_API_KEY` |
| Real OCR with Tesseract | Needs Tesseract executable + `TESSERACT_CMD` |
| Database persistence with Supabase | Needs valid `DATABASE_URL` |
| End-to-end audit with files | Needs all above |

---

## Next Steps (Recommended)

1. **Configure credentials** in `.env`:
   ```bash
   LLM_PROVIDER=openai
   LLM_API_KEY=sk-...
   LLM_MODEL=gpt-4o-mini
   DATABASE_URL=postgresql://...
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

2. **Run Supabase schema** in SQL Editor (`backend/sql/schema.sql`)

3. **Implement Stage 10**: Report Generation
   - Create `ReportService` for Markdown/JSON export
   - Add audit orchestration endpoint
   - Generate final audit report with summary + claim details
   - Frontend integration for results display