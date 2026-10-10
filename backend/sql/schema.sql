-- =============================================================================
-- SECOND OPINION — DATABASE SCHEMA
-- Run this in Supabase SQL Editor or via psql
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TABLE: audits
-- =============================================================================
CREATE TABLE audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    original_answer TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PROCESSING', 'COMPLETED', 'FAILED')),
    total_claims INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Index for history queries
CREATE INDEX idx_audits_created_at ON audits(created_at DESC);

-- =============================================================================
-- TABLE: source_documents
-- =============================================================================
CREATE TABLE source_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    mime_type TEXT,
    storage_path TEXT,
    processing_status TEXT NOT NULL CHECK (processing_status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', 'FAILED')),
    page_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_source_documents_audit_id ON source_documents(audit_id);

-- =============================================================================
-- TABLE: claims
-- =============================================================================
CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN (
        'SUPPORTED',
        'CONTRADICTED',
        'UNSUPPORTED',
        'AMBIGUOUS',
        'POTENTIALLY_UNSAFE',
        'UNABLE_TO_ASSESS'
    )),
    explanation TEXT NOT NULL,
    evidence_strength TEXT CHECK (evidence_strength IN ('strong', 'moderate', 'weak')),
    requires_review BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_claims_audit_id ON claims(audit_id);

-- =============================================================================
-- TABLE: evidence
-- =============================================================================
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    document_id UUID REFERENCES source_documents(id) ON DELETE SET NULL,
    passage_text TEXT NOT NULL,
    page_number INTEGER,
    relationship TEXT NOT NULL CHECK (relationship IN ('supports', 'contradicts', 'context', 'insufficient')),
    validated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_claim_id ON evidence(claim_id);
CREATE INDEX idx_evidence_document_id ON evidence(document_id);

-- =============================================================================
-- Row Level Security (enable when authentication is added)
-- =============================================================================
-- ALTER TABLE audits ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;

-- Example policies (require auth context):
-- CREATE POLICY "Users can view own audits" ON audits FOR SELECT USING (auth.uid() = user_id);
-- CREATE POLICY "Users can insert own audits" ON audits FOR INSERT WITH CHECK (auth.uid() = user_id);