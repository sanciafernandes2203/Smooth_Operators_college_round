# AGENTS.md

## Instructions for Coding Assistants

This document provides mandatory instructions for any AI coding assistant working on the Second Opinion backend project.

---

### 1. Read the Project Bible First
Before making any changes, **read `PROJECT_BIBLE.md` completely**. It is the single source of truth for:
- Product scope and requirements
- Architecture and API contracts
- File structure and naming conventions
- Testing requirements
- Git workflow

Do not rely on memory or assumptions. The Bible overrides any conflicting instructions.

---

### 2. Respect Existing API Contracts
The API contract in `PROJECT_BIBLE.md` §12 and `docs/API_CONTRACT.md` is the integration agreement between frontend and backend.

**Rules**:
- Do not change field names, types, or response structures without updating the contract
- Frontend (Sancia) depends on exact field names
- Use Pydantic schemas in `app/schemas/` - they ARE the contract
- If you must change the contract, update the Bible and all related code together

---

### 3. Inspect Before Creating
**Always search the codebase first** before adding new files or functions.

```bash
# Search for existing implementations
grep -r "function_name" backend/app/
# Check existing patterns
ls backend/app/services/
```

**Do not**:
- Create duplicate services or utilities
- Reimplement existing functionality
- Overwrite working code without justification

---

### 4. Frontend Files Are Off-Limits
**Never modify files in `frontend/`** (if it exists). That is Sancia's responsibility.

Backend-only directories:
- `backend/app/`
- `backend/tests/`
- `backend/sql/`
- `docs/` (shared)

---

### 5. No Unrelated Refactoring
**Stay focused on the current task**. Do not:
- Reformat code that works
- Rename variables for "style"
- Restructure modules unless required
- Add "nice-to-have" features not in the current stage

---

### 6. Never Commit Secrets
**Absolute rule**: No API keys, passwords, connection strings, or tokens in tracked files.

**Checklist before commit**:
- [ ] No `.env` files staged
- [ ] No hardcoded API keys in code
- [ ] No database passwords in code
- [ ] No Supabase service role keys in code
- [ ] `.gitignore` covers `.env`, `.env.*`, `*.key`, `*.pem`

Use `.env.example` for documenting required variables.

---

### 7. Mock External Dependencies in Tests
**Never make live API calls in automated tests**.

**Rules**:
- Mock LLM clients (`AsyncMock` for `complete()`)
- Mock database sessions (FastAPI dependency override)
- Mock OCR, file I/O, external HTTP calls
- Use fixtures for test data
- Mark credential-dependent tests as skipped, not failed

**Test organization**:
- `test_health.py` - Health endpoints
- `test_audits.py` - Audit API endpoints
- `test_documents.py` - Document processing
- `test_llm_client.py` - LLM client behavior
- `test_claim_extraction.py` - Claim extraction (mocked LLM)
- `test_retrieval.py` - Evidence retrieval (local passages)

---

### 8. Distinguish Implemented vs. Tested vs. Untested
**Be precise in reporting**:

| Status | Meaning |
|--------|---------|
| ✅ Implemented & Tested | Code exists + automated tests pass |
| 🔄 Partially Implemented | Code exists but incomplete or not fully wired |
| ⚠️ Config Required | Works but needs credentials/env vars |
| 🚫 Not Implemented | Not started |
| ❌ Broken | Known issues |

**Never claim**:
- "Tests pass" unless you actually ran them
- "Integration works" without verifying
- "Stage X complete" if dependencies are missing

---

### 9. Update Documentation After Significant Work
After completing a stage or major feature, update:

1. **`docs/AI_HANDOFF.md`** - Current state, handoff info for next assistant
2. **`docs/IMPLEMENTATION_STATUS.md`** - Checklist of done/partial/deferred
3. **`docs/ARCHITECTURE_DECISIONS.md`** - Record new ADRs
4. **`README.md`** - Only if user-facing changes (setup, endpoints)

**Do not** regenerate from scratch. Make focused updates.

---

### 9. Git Workflow
**Branch**: Work on `backend-eleen` (your branch)
**Commits**: Small, focused, descriptive messages
```bash
git add backend/app/services/llm/claim_extractor.py
git commit -m "Stage 6: Add claim extraction service with LLM integration"
```

**Pull Requests**: Open PR to `main` for review before merge.

---

### 10. Stage-Specific Reminders

#### Stage 6 (Claim Extraction)
- Use existing `LLMClient` via `get_llm_client()`
- Structured JSON output via `response_format`
- Handle malformed LLM output gracefully
- Never fabricate claims on error

#### Stage 7 (Evidence Retrieval)
- Reuse `TextPassage` from document chunking
- Keyword/BM25 only - no embeddings
- Preserve ALL provenance (doc_id, page, char offsets)
- Stopword filtering required

#### Stage 8 (Next - Claim Verification)
- Input: Claim + retrieved passages
- Output: Verdict + explanation + evidence quotes
- Use same LLM client pattern
- Persist to `evidence` table with `relationship_type`

---

### Quick Reference: Key Files

| Purpose | File |
|---------|------|
| Project Bible | `PROJECT_BIBLE.md` |
| API Contract | `PROJECT_BIBLE.md` §12 |
| Database Schema | `backend/sql/schema.sql` |
| Config | `backend/app/config.py` |
| Main App | `backend/app/main.py` |
| LLM Client | `backend/app/services/llm/llm_client.py` |
| Claim Extractor | `backend/app/services/llm/claim_extractor.py` |
| Evidence Retriever | `backend/app/services/retrieval/evidence_retriever.py` |
| Audit Service | `backend/app/services/audit_service.py` |
| Audit API | `backend/app/api/routes/audits.py` |
| Schemas | `backend/app/schemas/` |
| Tests | `backend/tests/` |

---

### When in Doubt
1. Read `PROJECT_BIBLE.md`
2. Search existing code for patterns
3. Ask for clarification (don't guess)
4. Prefer smaller, verifiable changes