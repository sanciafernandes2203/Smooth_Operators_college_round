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

---

## Partially Implemented / Known Gaps ⚠️

| Feature | Status | Notes |
|---------|--------|-------|
| Evidence persistence to DB | 🔄 Partial | Schema ready, retrieval in-memory only |
| Full document passages for retrieval | 🔄 Partial | Only pasted source_text passages available; file passages need re-processing |
| Real LLM integration | 🔄 Config needed | Requires `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` in `.env` |
| Tesseract OCR on Windows | 🔄 Setup needed | Requires `TESSERACT_CMD` in `.env` |
| Supabase connection | 🔄 Config needed | Requires valid `DATABASE_URL` in `.env` |

---

## Deferred to Future Stages 🚫

| Feature | Stage | Dependencies |
|---------|-------|--------------|
| Claim Verification / Verdict Generation | 8 | Stage 6 & 7 complete |
| Evidence Validation (quote verification) | 8 | Stage 7 complete |
| Evidence Persistence to `evidence` table | 7.5 | Stage 7 complete |
| Embedding-based Semantic Retrieval | 8+ | Optional enhancement |
| Report Export (Markdown/JSON) | 8+ | Optional |
| Authentication & User-specific History | 9+ | Not started |
| PDF Page Preview | 8+ | Optional |

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
| **Total** | **88** | **87** | **1** | **0** |

**All tests pass** (1 skipped: OCR service init requires Tesseract executable).

**No live LLM calls** - all use mocked responses.
**No database required** - tests use FastAPI ASGITransport with mocked services.

---

## Integration Tests Deferred (Credentials Missing)

| Test | Reason |
|------|--------|
| Real claim extraction with live LLM | Needs `LLM_API_KEY` |
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

3. **Implement Stage 8**: Claim Verification
   - Create `ClaimVerifier` service
   - Add verification prompt with verdict taxonomy
   - Integrate into `AuditService.process_audit_claims()`
   - Persist evidence to `evidence` table with `relationship_type`

4. **Wire evidence persistence** in retrieval service

5. **Add API endpoint** for triggering full audit processing (claim extraction + retrieval + verification)