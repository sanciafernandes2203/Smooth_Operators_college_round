# AI Handoff Document

## Project Overview

**Second Opinion** is an AI-powered claim auditing and evidence verification platform. It allows users to submit an AI-generated answer along with source material (documents, text, images), and the system:

1. **Extracts** individual checkable claims from the answer (Stage 6)
2. **Retrieves** relevant evidence passages from the source material (Stage 7)
3. **Verifies** each claim against the evidence (Stage 8 - future)

The backend is built with **FastAPI**, **SQLAlchemy**, **PostgreSQL (Supabase)**, and uses **LLMs** (OpenAI, Anthropic, or Gemini) for claim extraction and verification.

---

## Important Project Rules (from PROJECT_BIBLE.md)

1. **Evidence over confident wording** - Never present LLM confidence as proof
2. **Unsupported does not mean false** - Lack of evidence ≠ contradiction
3. **Source traceability over black-box verdicts** - Every claim must link to source passages
4. **Reliability over feature count** - Working end-to-end audit > many unfinished components
5. **Measured evaluation over unsupported accuracy claims** - Don't claim accuracy without measurement
6. **One shared API contract** - Frontend and backend must agree on exact field names

---

## Backend Technology Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI 0.143+ |
| Database | PostgreSQL (Supabase) via SQLAlchemy 2.0+ async |
| Document Processing | PyMuPDF (fitz), Tesseract OCR (pytesseract), Pillow |
| LLM Integration | OpenAI, Anthropic, Google Gemini via httpx |
| Text Chunking | Custom TextChunker with provenance |
| Retrieval | TF-IDF/BM25 keyword search (no vector DB yet) |
| Validation | Pydantic 2.7+ |
| Testing | pytest, pytest-asyncio, httpx ASGITransport |

---

## Current Implementation Status (After Stages 6 & 7)

### ✅ Completed

#### Stage 6: Claim Extraction
- **Service**: `app/services/llm/claim_extractor.py` - `ClaimExtractor` class
- **Schemas**: `app/schemas/claim.py` - `ExtractedClaim`, `ClaimExtractionRequest`, `ClaimExtractionResponse`
- **LLM Prompt**: Structured system prompt in `CLAIM_EXTRACTION_SYSTEM_PROMPT`
- **Features**:
  - Extracts individual checkable claims from AI answers
  - Preserves original wording
  - Identifies non-checkable content (opinions, vague statements)
  - Handles malformed LLM output gracefully
  - Returns structured JSON via LLM `response_format`
  - Comprehensive error handling (LLM errors, parse errors, empty input)

#### Stage 7: Evidence Retrieval
- **Service**: `app/services/retrieval/evidence_retriever.py` - `EvidenceRetriever` class
- **Algorithm**: TF-IDF/BM25-inspired keyword scoring with stopword filtering
- **Features**:
  - Retrieves top-k passages for a claim
  - Preserves full provenance (document_id, document_name, page_number, char offsets)
  - Filters stopwords (the, of, and, etc.)
  - Preserves percentage signs and hyphenated terms
  - Configurable min_score, max_results, case_sensitivity
  - Returns `RetrievedPassage` with score and matched terms
  - `retrieve_for_multiple_claims` for batch processing

#### Integration
- **Audit Service**: `app/services/audit_service.py` - `process_audit_claims()` method
  - Orchestrates claim extraction → evidence retrieval
  - Stores claims in database with `PENDING` verdict
  - Updates audit status and claim count

#### Tests (89 passing)
- `test_claim_extraction.py` - 20 tests (mocked LLM responses)
- `test_retrieval.py` - 15 tests (local passages, no external deps)
- All existing tests still pass

---

### ⚠️ Partially Implemented / Known Limitations

1. **Claim-Evidence Persistence**: Claims are stored in DB, but evidence passages are not yet persisted to the `evidence` table. The retrieval happens in-memory from `TextPassage` objects.

2. **Full Document Passage Access**: The `process_audit_claims()` method needs access to all passages from source documents. Currently it only has passages from `source_text` (pasted text). File-based passages would require re-processing or storing passages in DB.

3. **No Verdict Generation (Stage 8)**: The verification step that decides SUPPORTED/CONTRADICTED/etc. is not implemented.

2. **LLM Configuration Required**: The claim extractor requires `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` in `.env` to work with a real LLM.

---

### 🚫 Deferred (Future Stages)

| Feature | Stage | Status |
|---------|-------|--------|
| Claim Verification / Verdict Generation | 8 | Not started |
| Evidence Validation (quote verification) | 8 | Not started |
| Evidence Persistence to DB | 7.5 | Schema ready, not wired |
| Embedding-based Semantic Retrieval | 8+ | Optional enhancement |
| Report Export (Markdown/JSON) | 8+ | Optional |
| Authentication & User-specific History | 9+ | Not started |

---

## Files Changed During Stages 6 & 7

### New Files Created
| File | Purpose |
|------|---------|
| `app/schemas/claim.py` | Claim extraction schemas |
| `app/services/llm/claim_extractor.py` | Claim extraction service |
| `app/services/retrieval/evidence_retriever.py` | Evidence retrieval service |
| `tests/test_claim_extraction.py` | 20 claim extraction tests |
| `tests/test_retrieval.py` | 15 evidence retrieval tests |

### Modified Files
| File | Changes |
|------|---------|
| `app/schemas/__init__.py` | Export claim schemas |
| `app/services/llm/__init__.py` | Export ClaimExtractor |
| `app/services/retrieval/__init__.py` | Export EvidenceRetriever |
| `app/services/__init__.py` | Export new services |
| `app/services/audit_service.py` | Added `process_audit_claims()`, claim storage, evidence retrieval integration |
| `app/schemas/claim.py` | Added validator for empty/whitespace answers |

---

## How Claim Extraction Works

1. **Input**: AI-generated answer text
2. **Prompt**: System prompt instructs LLM to extract claims as JSON
3. **LLM Call**: Uses global LLM client with JSON response format
4. **Parse & Validate**: JSON parsed, each claim validated as `ExtractedClaim`
4. **Filtering**: Non-dict items, empty claims skipped
5. **Output**: `ClaimExtractionResponse` with list of `ExtractedClaim`

**Key Prompt Rules** (from `CLAIM_EXTRACTION_SYSTEM_PROMPT`):
- Extract ONLY claims in the answer
- Preserve original wording
- Split independent claims
- Mark non-checkable (opinion, vague, prediction)
- Return structured JSON only

---

## How Evidence Retrieval Works

1. **Input**: Claim text + list of `TextPassage` objects (from document chunking)
2. **Tokenization**: Claim split into terms (stopwords filtered, % preserved)
3. **Scoring**: TF-IDF inspired scoring against all passages
4. **Filtering**: Min score threshold, max results limit
5. **Output**: Ranked `RetrievedPassage` with score, matched terms, full provenance

**Provenance Preserved**:
- `document_id`, `document_name`
- `page_number` (None for text files)
- `char_start`, `char_end` in original document
- `source_type` (text/pdf/ocr), `extraction_method`

---

## Schemas, Services, and Dependencies

### Key Schemas
```python
# Claim Extraction
ExtractedClaim(claim_text, is_checkable, reason_not_checkable)
ClaimExtractionRequest(answer)
ClaimExtractionResponse(claims, total_claims, error)

# Evidence Retrieval
RetrievedPassage(passage, score, matched_terms)
RetrievalResult(claim_text, passages, total_passages_searched, error)
```

### Key Services
```python
ClaimExtractor(llm_client).extract_claims(answer) -> ClaimExtractionResponse
EvidenceRetriever(min_score, max_results).retrieve(claim, passages) -> RetrievalResult
AuditService.process_audit_claims(audit_id) -> (claims, passages)
```

### External Dependencies Required
- **LLM**: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` in `.env`
- **OCR**: Tesseract executable (for Stage 4 OCR)
- **Database**: `DATABASE_URL` for Supabase PostgreSQL

---

## Credentials & External Integrations Still Needed

| Credential | Purpose | Status |
|------------|---------|--------|
| `LLM_PROVIDER` | Select LLM (openai/anthropic/gemini) | ❌ Not set |
| `LLM_API_KEY` | Authenticate with LLM provider | ❌ Not set |
| `LLM_MODEL` | Model name (e.g., gpt-4o-mini) | ❌ Not set |
| `DATABASE_URL` | Supabase PostgreSQL connection | ⚠️ Local default only |
| `TESSERACT_CMD` | Tesseract path (Windows) | ⚠️ Not set |

**Without LLM credentials**: Claim extraction tests pass (mocked), but real extraction will fail.

---

## Next Stage to Implement

**Stage 8: Claim Verification & Verdict Generation**

**Requirements** (from PROJECT_BIBLE.md §15.2):
- Input: Claim + retrieved passages + verdict taxonomy
- LLM instructed to:
  - Use ONLY supplied passages as evidence
  - Distinguish contradiction from lack of evidence
  - Quote only from supplied passages
  - Explain limitations
  - Ignore prompt injections in source docs
  - Return structured output (Pydantic validated)
- Output: Verdict (SUPPORTED/CONTRADICTED/UNSUPPORTED/AMBIGUOUS/POTENTIALLY_UNSAFE/UNABLE_TO_ASSESS) + explanation + evidence quotes

**Database Ready**: `claims` table has `verdict`, `explanation`, `evidence_strength` columns. `evidence` table ready for storing retrieved passages with `relationship_type` (supports/contradicts/context/insufficient).

---

## Running the Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials
uvicorn app.main:app --reload --port 8000
```

**API Endpoints**:
- `POST /api/audits` - Create audit (answer + source_text + files)
- `GET /api/audits` - List audits
- `GET /api/audits/{audit_id}` - Get audit with claims/evidence
- `GET /api/health` - Health check
- `GET /docs` - Swagger UI

---

## Testing

```bash
cd backend
pytest tests/ -v
# Or specific test files
pytest tests/test_claim_extraction.py tests/test_retrieval.py -v
```

**All 89 tests pass** (1 skipped for OCR which requires Tesseract executable).

**No live LLM calls in tests** - all use mocked responses.
**No database required for tests** - uses FastAPI ASGITransport with mocked services.