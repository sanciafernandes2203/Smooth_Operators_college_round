import type { EvidenceItem, EvidenceRelationship } from '../types/evidence'

const RELATIONSHIP_LABELS: Record<EvidenceRelationship, string> = {
  supports: 'Supporting evidence',
  contradicts: 'Contradicting evidence',
  context: 'Context only',
  insufficient: 'Does not establish the claim',
}

const RELATIONSHIP_STYLES: Record<EvidenceRelationship, string> = {
  supports: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  contradicts: 'bg-red-50 text-red-700 ring-red-600/20',
  context: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  insufficient: 'bg-amber-50 text-amber-700 ring-amber-600/20',
}

interface EvidencePanelProps {
  evidence: EvidenceItem[]
}

/**
 * Shows the passages retrieved for a claim, with source identity,
 * page reference, evidence relationship, and validation status
 * (PROJECT_BIBLE.md F11 and F9).
 */
export function EvidencePanel({ evidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-center">
        <p className="text-sm font-medium text-slate-600">
          No evidence was retrieved for this claim.
        </p>
        <p className="mt-1 text-xs text-slate-400">
          The audit pipeline did not return any supporting passages.
        </p>
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {evidence.map((item, index) => (
        <li
          key={`${item.document_id}-${index}`}
          className="rounded-xl border border-slate-200 bg-slate-50 p-4"
        >
          <blockquote className="border-l-2 border-teal-400 pl-3">
            <p className="text-pretty text-sm leading-relaxed text-slate-700">
              “{item.quote}”
            </p>
          </blockquote>

          <dl className="mt-3 space-y-1.5 text-xs text-slate-500">
            <div className="flex flex-wrap items-center gap-2">
              <dt className="font-semibold uppercase tracking-wide">Source</dt>
              <dd className="inline-flex items-center gap-1.5 font-medium text-slate-700">
                <svg
                  className="h-3.5 w-3.5 shrink-0 text-teal-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                  />
                </svg>
                {item.document_name}
              </dd>
              {item.page_number !== null && (
                <>
                  <span aria-hidden="true">·</span>
                  <dd>page {item.page_number}</dd>
                </>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <dt className="font-semibold uppercase tracking-wide">Relationship</dt>
              <dd>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${RELATIONSHIP_STYLES[item.relationship]}`}
                >
                  {RELATIONSHIP_LABELS[item.relationship]}
                </span>
              </dd>
              <span aria-hidden="true">·</span>
              <dd>
                {item.validated ? (
                  <span className="font-semibold text-emerald-600">
                    Validated by retrieval
                  </span>
                ) : (
                  <span className="font-semibold text-amber-600">
                    Not validated by retrieval
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  )
}
