import type { AuditSummary as AuditSummaryData } from '../types/audit'
import type { Verdict } from '../types/claim'
import { VERDICT_STYLES } from '../utils/verdictStyles'

const VERDICT_ORDER: Verdict[] = [
  'SUPPORTED',
  'CONTRADICTED',
  'UNSUPPORTED',
  'AMBIGUOUS',
  'POTENTIALLY_UNSAFE',
  'UNABLE_TO_ASSESS',
]

const SUMMARY_KEYS: Record<
  Verdict,
  keyof Omit<AuditSummaryData, 'total_claims'>
> = {
  SUPPORTED: 'supported',
  CONTRADICTED: 'contradicted',
  UNSUPPORTED: 'unsupported',
  AMBIGUOUS: 'ambiguous',
  POTENTIALLY_UNSAFE: 'potentially_unsafe',
  UNABLE_TO_ASSESS: 'unable_to_assess',
}

interface AuditSummaryProps {
  summary: AuditSummaryData
}

/**
 * Summary cards for the audit: total claims plus the count for every
 * verdict category, so the counts visibly add up to the total.
 */
export function AuditSummary({ summary }: AuditSummaryProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
      <div className="rounded-xl border border-teal-200 bg-teal-50 p-4">
        <p className="text-3xl font-bold text-teal-700">
          {summary.total_claims}
        </p>
        <p className="mt-1 text-xs font-medium text-slate-500">Total claims</p>
      </div>

      {VERDICT_ORDER.map((verdict) => {
        const style = VERDICT_STYLES[verdict]
        return (
          <div
            key={verdict}
            className="rounded-xl border border-slate-200 bg-white p-4 motion-safe:transition motion-safe:hover:border-slate-300"
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${style.dot}`}
              aria-hidden="true"
            />
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {summary[SUMMARY_KEYS[verdict]]}
            </p>
            <p className="mt-1 text-xs font-medium text-slate-500">
              {style.label}
            </p>
          </div>
        )
      })}
    </div>
  )
}
