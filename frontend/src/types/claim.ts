import type { EvidenceItem } from './evidence'

/**
 * Verdict values must match the taxonomy in PROJECT_BIBLE.md section 5
 * and the backend contract exactly. Do not rename or extend without
 * updating the backend schemas and documentation together.
 */
export type Verdict =
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'UNSUPPORTED'
  | 'AMBIGUOUS'
  | 'POTENTIALLY_UNSAFE'
  | 'UNABLE_TO_ASSESS'

/**
 * A small, interpretable evidence-strength label (PROJECT_BIBLE.md F13).
 * This is an estimate, never proof.
 */
export type EvidenceStrength = 'strong' | 'moderate' | 'weak' | 'none'

export interface ClaimResult {
  claim_id: string
  claim_text: string
  verdict: Verdict
  explanation: string
  evidence_strength: EvidenceStrength
  evidence: EvidenceItem[]
  requires_review: boolean
}
