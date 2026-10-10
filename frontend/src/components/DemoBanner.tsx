/**
 * Persistent, prominent banner marking every result on screen as
 * synthetic demo data. It must never be removed while mock data is shown.
 */
export function DemoBanner() {
  return (
    <div className="sticky top-2 z-40 mb-6">
      <div className="flex items-center justify-center gap-2.5 rounded-full border border-amber-300/60 bg-amber-300 px-4 py-2 shadow-lg shadow-amber-500/10">
        <svg
          className="h-4 w-4 shrink-0 text-amber-950"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
        <p className="text-center text-xs font-bold tracking-wide text-amber-950">
          DEMO — MOCK DATA · Sample results only · No real audit has run
        </p>
      </div>
    </div>
  )
}
