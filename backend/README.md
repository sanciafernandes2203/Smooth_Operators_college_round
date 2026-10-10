# Second Opinion — Backend

FastAPI backend for the AI-powered claim auditing platform.

## Quick Start

### Prerequisites

- Python 3.11+
- Tesseract OCR (system installation required)
- Supabase PostgreSQL database (or local PostgreSQL)

### System Dependencies

#### Windows

1. **Tesseract OCR:**
   - Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
   - Install to default location (`C:\Program Files\Tesseract-OCR\`)
   - Add to PATH or set `TESSERACT_CMD` in `.env`

2. **Python:** Use official installer from python.org

#### macOS

```bash
brew install tesseract python@3.11
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr python3.11 python3.11-venv
```

### Installation

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux

# Edit .env with your values (at minimum: DATABASE_URL, LLM_API_KEY)
# notepad .env           # Windows
# nano .env              # macOS/Linux
```

### Database Setup

1. Create a Supabase project at https://supabase.com
2. Get the **direct PostgreSQL connection string** from Settings → Database
   - Format: `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`
3. Set `DATABASE_URL` in `.env`
4. Run the schema:
   ```bash
   # In Supabase SQL Editor, run the contents of sql/schema.sql
   ```

### Running the Server

```bash
# From backend/ directory with venv activated
uvicorn app.main:app --reload --port 8000
```

Server runs at: http://localhost:8000

API docs: http://localhost:8000/docs
Health check: http://localhost:8000/api/health

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Service health check |
| GET | `/api/health/ready` | Service readiness check |
| POST | `/api/audits` | Create a new audit submission |
| GET | `/api/audits` | List audit history (paginated) |
| GET | `/api/audits/{audit_id}` | Get audit details |

#### Create Audit (POST /api/audits)

**Content-Type:** `multipart/form-data`

**Fields:**
- `answer` (required): The AI-generated answer to audit
- `source_text` (optional): Pasted source text to audit against
- `files` (optional): Uploaded source files (PDF, TXT, JPG, JPEG, PNG)

**Response (201):**
```json
{
  "audit_id": "uuid",
  "status": "PROCESSING",
  "created_at": "2026-10-10T12:00:00Z"
}
```

**Error Responses:**
- 400: Missing or empty required fields
- 413: Input exceeds size limit
- 415: Unsupported file type
- 500: Database or internal error

### Document Processing (Stage 4)

The backend now supports processing of uploaded source documents:

**Supported file types:**
- **TXT** — Plain text files with automatic encoding detection (UTF-8, Latin-1, CP1252)
- **PDF** — Text-based PDFs using PyMuPDF (page-by-page extraction with provenance)
- **JPG/JPEG** — Images via Tesseract OCR
- **PNG** — Images via Tesseract OCR

**Features:**
- Page-level provenance for PDF documents
- Automatic detection of scanned/image-only PDF pages
- OCR processing for scanned pages and image files
- Configurable page limit (default: no limit)
- File size validation (default 15 MB, configurable via `MAX_UPLOAD_SIZE_MB`)
- Secure temporary file handling with automatic cleanup
- Structured extraction results with document ID, filename, page numbers, and extraction method

**PDF Processing Details:**
- Extracts text page by page preserving page numbers
- Detects pages with little/no extractable text (likely scanned)
- Flags potentially scanned pages for OCR processing
- Handles encrypted, corrupted, and empty PDFs gracefully
- Preserves extraction method metadata (pymupdf, tesseract)

**OCR Processing:**
- Uses Tesseract via pytesseract
- Supports multiple languages (default: English)
- Returns confidence scores for extracted text
- Processes both uploaded images and scanned PDF pages
- Requires Tesseract executable installed separately (see below)

### LLM Client Integration (Stage 5)

The backend includes a unified LLM client supporting multiple providers:

**Supported Providers:**
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — Claude 3 Haiku, Sonnet, Opus
- **Google Gemini** — Gemini 1.5 Flash, Pro

**Features:**
- Unified interface via `LLMClientFactory`
- Configurable via environment variables (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`)
- Automatic retries with exponential backoff (configurable)
- Timeout handling (default 60s)
- Structured output support where provider supports it (OpenAI JSON mode, Gemini JSON mode)
- Comprehensive error handling (auth, rate limits, timeouts, connection errors)
- Secure credential handling (never logged)
- Provider-specific details encapsulated in client classes

**Usage:**
```python
from app.services.llm import get_llm_client

client = get_llm_client()  # Creates client from environment config
response = await client.complete(
    user_prompt="Analyze this claim...",
    system_prompt="You are a fact-checker...",
    temperature=0.0,
    response_format={"type": "json_object"}  # Where supported
)
```

### Running Tests

```bash
# From backend/ directory
pytest -v
```

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── audits.py
│   │       └── history.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── audit.py
│   │   ├── claim.py
│   │   ├── evidence.py
│   │   └── errors.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audit_service.py
│   │   ├── documents/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── ocr_service.py
│   │   │   └── text_chunker.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── llm_client.py
│   │   ├── retrieval/
│   │   ├── verification/
│   │   └── reports/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repositories.py
│   └── utils/
│       ├── __init__.py
│       ├── file_validation.py
│       └── text_normalizer.py
├── tests/
│   ├── __init__.py
│   ├── test_health.py
│   ├── test_audits.py
│   ├── test_documents.py
│   └── test_llm_client.py
├── sql/
│   └── schema.sql
├── requirements.txt
├── .env.example
└── README.md
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `LLM_PROVIDER` | Yes* | `openai`, `anthropic`, or `gemini` |
| `LLM_API_KEY` | Yes* | Provider API key |
| `LLM_MODEL` | Yes* | Model name for chosen provider |
| `FRONTEND_ORIGIN` | No | CORS origin (default: `http://localhost:5173`) |
| `MAX_UPLOAD_SIZE_MB` | No | Max upload size (default: 15) |
| `BACKEND_HOST` | No | Bind host (default: `0.0.0.0`) |
| `BACKEND_PORT` | No | Bind port (default: 8000) |
| `LOG_LEVEL` | No | Log level (default: `INFO`) |
| `TESSERACT_CMD` | No* | Path to tesseract executable (Windows) |

*Required when the corresponding feature is used.

### LLM Provider Setup

Choose one provider and install its SDK:

```bash
# OpenAI
pip install openai>=1.30.0

# Anthropic
pip install anthropic>=0.25.0

# Google Gemini
pip install google-generativeai>=0.7.0
```

Then set `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` in `.env`.

### OCR Notes

- Tesseract must be installed **separately** from the Python package
- On Windows, set `TESSERACT_CMD` in `.env` if not in PATH
- Test with: `tesseract --version`

**Windows Tesseract Installation:**
1. Download installer from https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (`C:\Program Files\Tesseract-OCR\`)
3. Add to PATH or set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `.env`

### Troubleshooting

**"ModuleNotFoundError: No module named 'fitz'"**
→ Install PyMuPDF: `pip install pymupdf`

**"Tesseract not found"**
→ Install Tesseract system package and/or set `TESSERACT_CMD`

**"Connection refused" to database**
→ Check `DATABASE_URL`, network access, Supabase IP allowlist

**CORS errors from frontend**
→ Ensure `FRONTEND_ORIGIN` matches your frontend URL exactly

**"'coroutine' object is not subscriptable" in LLM client**
→ Ensure `await response.json()` is used (fixed in Stage 5)