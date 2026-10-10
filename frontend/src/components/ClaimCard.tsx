import { useState } from 'react'
import type { ClaimResult } from '../types/claim'
import { VERDICT_STYLES } from '../utils/verdictStyles'
import { VerdictBadge } from './VerdictBadge'
import { EvidencePanel } from './EvidencePanel'

const UNCERTAINTY_NOTES: Partial<Record<ClaimResult['verdict'], string>> = {
  UNSUPPORTED:
    'The supplied material does not establish this claim. Unsupported does not mean false — it means the evidence was insufficient.',
  AMBIGUOUS:
    'The wording or the evidence allows more than one interpretation, so no firm verdict could be reached.',
  POTENTIALLY_UNSAFE:
    'This claim may require caution. The safety flag is a product notice, not a clinical or legal verdict.',
  UNABLE_TO_ASSESS:
    'This claim could not be assessed reliably from the supplied material, so no verdict is offered.',
}

const STRENGTH_LABELS: Record<ClaimResult['evidence_strength'], string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  weak: 'Weak',
  none: 'None',
}

interface ClaimCardProps {
  claim: ClaimResult
  index: number
}

/**
 * One audited claim with its verdict badge, plain-language
 * explanation, evidence-strength estimate, and collapsible
 * evidence panel. Pure and props-driven.
 */
export function ClaimCard({ claim, index }: ClaimCardProps) {
  const style = VERDICT_STYLES[claim.verdict]
  const [expanded, setExpanded] = useState(false)
  const evidenceId = `claim-${claim.claim_id}-evidence`
  const uncertainty = UNCERTAINTY_NOTES[claim.verdict]

  return (
    <article
      className={`rounded-2xl border border-slate-200 border-l-4 ${style.accentBorder} bg-white p-5 shadow-sm motion-safe:transition-shadow hover:shadow-md sm:p-6`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
          Claim {index + 1}
        </p>
        <VerdictBadge verdict={claim.verdict} />
      </div>

      <p className="mt-3 text-base font-medium text-slate-900 sm:text-lg">
        {claim.claim_text}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">
        {claim.explanation}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500">
          Evidence strength (estimate):{' '}
          <span className="font-semibold text-slate-800">
            {STRENGTH_LABELS[claim.evidence_strength]}
          </span>
        </span>
        {claim.requires_review && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-orange-300 bg-orange-50 px-2.5 py-1 font-medium text-orange-700">
            Flagged for manual review
          </span>
        )}
      </div>

      {uncertainty && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Uncertainty
          </p>
          <p className="mt-1 text-sm text-slate-600">{uncertainty}</p>
        </div>
      )}

      <div className="mt-5">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          aria-controls={evidenceId}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-teal-700 motion-safe:transition hover:border-teal-300 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
        >
          <svg
            className={`h-4 w-4 motion-safe:transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 8.25l-7.5 7.5-7.5-7.5"
            />
          </svg>
          {expanded ? 'Hide evidence' : `Show evidence (${claim.evidence.length})`}
        </button>
        {expanded && (
          <div id={evidenceId} className="mt-3">
            <EvidencePanel evidence={claim.evidence} />
          </div>
        )}
      </div>
    </article>
  )
}
