import { API_BASE_URL, parseApiError } from './api'
import type { AuditResult } from '../types/audit'

export interface SubmitAuditParams {
  answer: string
  sourceText?: string
  files?: File[]
}

/**
 * Submit an AI-generated answer and source material to the backend
 * for claim extraction, evidence retrieval, and verification.
 * Follows PROJECT_BIBLE.md section 12.3.
 */
export async function submitAudit({
  answer,
  sourceText,
  files = [],
}: SubmitAuditParams): Promise<AuditResult> {
  const formData = new FormData()
  formData.append('answer', answer.trim())

  if (sourceText && sourceText.trim().length > 0) {
    formData.append('source_text', sourceText.trim())
  }

  for (const file of files) {
    formData.append('files', file)
  }

  // Let the browser set the multipart boundary automatically
  const response = await fetch(`${API_BASE_URL}/api/audits`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const errorMessage = await parseApiError(response)
    throw new Error(errorMessage)
  }

  const data = (await response.json()) as AuditResult
  return data
}

/**
 * Retrieve a previously saved audit by ID (PROJECT_BIBLE.md section 12.6).
 */
export async function getAuditById(auditId: string): Promise<AuditResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/audits/${encodeURIComponent(auditId)}`
  )
  if (!response.ok) {
    const errorMessage = await parseApiError(response)
    throw new Error(errorMessage)
  }
  const data = (await response.json()) as AuditResult
  return data
}
