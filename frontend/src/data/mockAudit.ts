import type { AuditResult } from '../types/audit'

/**
 * ============================================================================
 * SYNTHETIC DEMO DATA — NOT A REAL AUDIT
 * ============================================================================
 * Everything in this file is fictional sample data created for the hackathon
 * demonstration. The claims, quotations, sources, verdicts, and counts below
 * are invented. They must never be presented as verified real-world facts,
 * and no backend request is made with this data.
 *
 * The first three claims follow the controlled test fixture described in
 * PROJECT_BIBLE.md section 4.3. The remaining claims are additional fictional
 * examples included so the demo shows every verdict category from the
 * taxonomy in PROJECT_BIBLE.md section 5.
 * ============================================================================
 */

export const mockAnswerText = [
  'The survey included 500 students. 60% of surveyed students preferred',
  'online notes. A large majority of students preferred online notes. The',
  'survey proves that online notes improve examination scores. It is safe',
  'to stop taking prescribed medication as soon as you feel better. The',
  'scanned receipt shows a total of $42.10.',
].join(' ')

export const mockSources = [
  { name: 'survey-summary.txt', kind: 'TXT document · synthetic fixture' },
  { name: 'wellness-brief.txt', kind: 'TXT document · fictional sample' },
  { name: 'receipt-scan.pdf', kind: 'PDF scan · low quality, unreadable' },
]

export const mockAuditResult: AuditResult = {
  audit_id: 'demo-audit-7c1e4b2a-9f3d-4a8e-b6c2-5d1f0e9a8b7c',
  status: 'COMPLETED',
  created_at: '2026-10-10T09:30:00Z',
  summary: {
    total_claims: 6,
    supported: 1,
    contradicted: 1,
    unsupported: 1,
    ambiguous: 1,
    potentially_unsafe: 1,
    unable_to_assess: 1,
  },
  claims: [
    {
      claim_id: 'claim-demo-1',
      claim_text: 'The survey included 500 students.',
      verdict: 'CONTRADICTED',
      explanation:
        'The supplied source reports 200 students, which conflicts with the claim of 500 students.',
      evidence_strength: 'strong',
      evidence: [
        {
          document_id: 'doc-demo-1',
          document_name: 'survey-summary.txt',
          page_number: null,
          quote: 'The survey included 200 students.',
          relationship: 'contradicts',
          validated: true,
        },
      ],
      requires_review: false,
    },
    {
      claim_id: 'claim-demo-2',
      claim_text: '60% of surveyed students preferred online notes.',
      verdict: 'SUPPORTED',
      explanation:
        'The source states that 60% of surveyed students preferred online notes, matching this claim exactly.',
      evidence_strength: 'strong',
      evidence: [
        {
          document_id: 'doc-demo-1',
          document_name: 'survey-summary.txt',
          page_number: null,
          quote: '60% of surveyed students preferred online notes.',
          relationship: 'supports',
          validated: true,
        },
      ],
      requires_review: false,
    },
    {
      claim_id: 'claim-demo-3',
      claim_text: 'The survey proves that online notes improve examination scores.',
      verdict: 'UNSUPPORTED',
      explanation:
        'The source reports a preference for online notes but explicitly does not report examination scores, so it does not establish this claim.',
      evidence_strength: 'weak',
      evidence: [
        {
          document_id: 'doc-demo-1',
          document_name: 'survey-summary.txt',
          page_number: null,
          quote: 'The document does not report examination scores.',
          relationship: 'insufficient',
          validated: true,
        },
      ],
      requires_review: false,
    },
    {
      claim_id: 'claim-demo-4',
      claim_text: 'A large majority of students preferred online notes.',
      verdict: 'AMBIGUOUS',
      explanation:
        'The source reports 60%, but whether 60% counts as a "large majority" is open to interpretation, so no firm verdict can be reached.',
      evidence_strength: 'moderate',
      evidence: [
        {
          document_id: 'doc-demo-1',
          document_name: 'survey-summary.txt',
          page_number: null,
          quote: '60% of surveyed students preferred online notes.',
          relationship: 'context',
          validated: true,
        },
      ],
      requires_review: false,
    },
    {
      claim_id: 'claim-demo-5',
      claim_text:
        'It is safe to stop taking prescribed medication as soon as you feel better.',
      verdict: 'POTENTIALLY_UNSAFE',
      explanation:
        'The supplied brief advises consulting a healthcare provider before changing any medication, so this claim could lead to harm and requires caution. This is a product safety notice, not a clinical verdict.',
      evidence_strength: 'moderate',
      evidence: [
        {
          document_id: 'doc-demo-2',
          document_name: 'wellness-brief.txt',
          page_number: null,
          quote:
            'Participants were advised to consult a healthcare provider before changing any medication.',
          relationship: 'contradicts',
          validated: true,
        },
      ],
      requires_review: true,
    },
    {
      claim_id: 'claim-demo-6',
      claim_text: 'The scanned receipt shows a total of $42.10.',
      verdict: 'UNABLE_TO_ASSESS',
      explanation:
        'The supplied scan was too low-quality to read reliably, so this claim cannot be assessed from the provided material.',
      evidence_strength: 'none',
      evidence: [],
      requires_review: true,
    },
  ],
}
