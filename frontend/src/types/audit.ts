import type { ClaimResult } from './claim'

export type AuditStatus = 'PROCESSING' | 'COMPLETED' | 'FAILED'

/**
 * Counts must include every verdict category the backend can return and
 * must add up to total_claims (PROJECT_BIBLE.md sections 12.4 and 17.2).
 */
export interface AuditSummary {
  total_claims: number
  supported: number
  contradicted: number
  unsupported: number
  ambiguous: number
  potentially_unsafe: number
  unable_to_assess: number
}

/**
 * Matches the API response contract in PROJECT_BIBLE.md section 12.4.
 */
export interface AuditResult {
  audit_id: string
  status: AuditStatus
  summary: AuditSummary
  claims: ClaimResult[]
  created_at: string
}
