import type { Verdict } from '../types/claim'

export interface VerdictStyle {
  /** Human-readable label, always shown (never colour alone). */
  label: string
  /** Plain-language description used in tooltips and summaries. */
  description: string
  /** Tailwind classes for the badge container. */
  badge: string
  /** Tailwind classes for the badge icon. */
  icon: string
  /** Tailwind classes for the summary dot. */
  dot: string
  /** Tailwind classes for the claim card left accent border. */
  accentBorder: string
}

/**
 * Visual conventions from PROJECT_BIBLE.md section 17.3:
 * supported = green, contradicted = red, unsupported = amber,
 * ambiguous = blue, potentially unsafe = distinct warning,
 * unable to assess = grey/neutral.
 */
export const VERDICT_STYLES: Record<Verdict, VerdictStyle> = {
  SUPPORTED: {
    label: 'Supported',
    description: 'The supplied evidence supports this claim.',
    badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    icon: 'text-emerald-600',
    dot: 'bg-emerald-500',
    accentBorder: 'border-l-emerald-500',
  },
  CONTRADICTED: {
    label: 'Contradicted',
    description: 'The supplied evidence conflicts with this claim.',
    badge: 'bg-red-50 text-red-700 ring-red-600/20',
    icon: 'text-red-600',
    dot: 'bg-red-500',
    accentBorder: 'border-l-red-500',
  },
  UNSUPPORTED: {
    label: 'Unsupported',
    description:
      'The supplied material does not establish this claim. Unsupported does not mean false.',
    badge: 'bg-amber-50 text-amber-700 ring-amber-600/20',
    icon: 'text-amber-600',
    dot: 'bg-amber-500',
    accentBorder: 'border-l-amber-500',
  },
  AMBIGUOUS: {
    label: 'Ambiguous',
    description: 'The claim or evidence allows multiple interpretations.',
    badge: 'bg-sky-50 text-sky-700 ring-sky-600/20',
    icon: 'text-sky-600',
    dot: 'bg-sky-500',
    accentBorder: 'border-l-sky-500',
  },
  POTENTIALLY_UNSAFE: {
    label: 'Potentially unsafe',
    description:
      'This claim could lead to harm and requires caution. Not a clinical or legal verdict.',
    badge: 'bg-orange-50 text-orange-700 ring-orange-600/20',
    icon: 'text-orange-600',
    dot: 'bg-orange-500',
    accentBorder: 'border-l-orange-500',
  },
  UNABLE_TO_ASSESS: {
    label: 'Unable to assess',
    description: 'This claim cannot be assessed reliably from the supplied material.',
    badge: 'bg-slate-100 text-slate-600 ring-slate-500/20',
    icon: 'text-slate-500',
    dot: 'bg-slate-400',
    accentBorder: 'border-l-slate-400',
  },
}
