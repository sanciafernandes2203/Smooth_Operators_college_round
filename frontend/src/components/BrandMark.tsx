interface BrandMarkProps {
  className?: string
}

/**
 * Small Second Opinion brand mark: a teal-to-sky gradient
 * rounded square with a check mark, symbolising a verified
 * second look.
 */
export function BrandMark({ className = 'h-10 w-10' }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="Second Opinion brand mark"
    >
      <defs>
        <linearGradient id="second-opinion-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0d9488" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#second-opinion-mark)" />
      <path
        d="M9.5 16.5l4.25 4.25L22.75 12.5"
        fill="none"
        stroke="#ffffff"
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
