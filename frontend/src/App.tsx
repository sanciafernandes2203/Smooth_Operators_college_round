import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  mockAnswerText,
  mockAuditResult,
  mockSources,
} from './data/mockAudit'
import { AuditSummary } from './components/AuditSummary'
import { BrandMark } from './components/BrandMark'
import { ClaimCard } from './components/ClaimCard'
import { DemoBanner } from './components/DemoBanner'
import { formatDate } from './utils/formatDate'
import { submitAudit } from './services/auditService'
import type { AuditResult } from './types/audit'

// The AI-generated answer is uploaded as a PDF, TXT, or image.
const ANSWER_EXTENSIONS = ['pdf', 'txt', 'png', 'jpg', 'jpeg']
const ANSWER_MIME_TYPES = [
  'application/pdf',
  'text/plain',
  'image/png',
  'image/jpeg',
]

// Source material is uploaded as a PDF or TXT document.
const SOURCE_EXTENSIONS = ['pdf', 'txt']
const SOURCE_MIME_TYPES = ['application/pdf', 'text/plain']

const MAX_FILE_SIZE_MB = 15
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const DEMO_EXTRACTION_DELAY_MS = 1500

/**
 * Extraction state machine. The backend extraction/OCR pipeline
 * (PROJECT_BIBLE.md F4/F5) is not connected yet, so the demo
 * flow only emulates these states until it is wired up.
 */
type ExtractionStatus = 'idle' | 'extracting' | 'success' | 'error'

/**
 * Simple visual explanation of the verification workflow,
 * shown in the hero so first-time visitors understand the
 * three-step loop at a glance.
 */
const WORKFLOW_STEPS = [
  {
    number: '1',
    title: 'Upload the answer',
    description: 'Add the AI-generated answer as a PDF, TXT, PNG, JPG, or JPEG.',
    icon: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5',
  },
  {
    number: '2',
    title: 'Add source material',
    description: 'Paste reference text or upload PDF and TXT documents.',
    icon: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
  },
  {
    number: '3',
    title: 'Review the verdicts',
    description: 'See claim-by-claim verdicts with source-linked evidence.',
    icon: 'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
] as const

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isAcceptedAnswerFile(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  const mimeOk = ANSWER_MIME_TYPES.includes(file.type)
  const extensionOk = ANSWER_EXTENSIONS.includes(extension)
  return mimeOk || extensionOk
}

function isAcceptedSourceFile(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  const mimeOk = SOURCE_MIME_TYPES.includes(file.type)
  const extensionOk = SOURCE_EXTENSIONS.includes(extension)
  return mimeOk || extensionOk
}

type View = 'input' | 'results'

export function App() {
  const [view, setView] = useState<View>('input')

  // Input 1: the AI-generated answer to audit.
  const [answerFile, setAnswerFile] = useState<File | null>(null)
  const [answerFileError, setAnswerFileError] = useState('')
  const [extractionStatus, setExtractionStatus] =
    useState<ExtractionStatus>('idle')
  const [extractionError, setExtractionError] = useState('')
  const [extractedText, setExtractedText] = useState('')

  // Input 2: the source material used to verify the answer.
  // Kept entirely separate from the answer and its text.
  const [sourceText, setSourceText] = useState('')
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [sourceFileError, setSourceFileError] = useState('')

  // Live audit execution state
  const [isAuditing, setIsAuditing] = useState(false)
  const [auditError, setAuditError] = useState('')
  const [liveAuditResult, setLiveAuditResult] = useState<AuditResult | null>(null)
  const [isDemoResult, setIsDemoResult] = useState(true)

  // Move keyboard focus to the visible screen's heading when
  // switching views, so screen reader and keyboard users land
  // in the right place. Skipped on the first render.
  const resultsHeadingRef = useRef<HTMLHeadingElement>(null)
  const inputHeadingRef = useRef<HTMLHeadingElement>(null)
  const isFirstRender = useRef(true)
  const extractionTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    if (view === 'results') {
      resultsHeadingRef.current?.focus()
    } else {
      inputHeadingRef.current?.focus()
    }
  }, [view])

  // Cancel any pending demo extraction when the component unmounts.
  useEffect(() => {
    return () => {
      if (extractionTimeoutRef.current !== null) {
        window.clearTimeout(extractionTimeoutRef.current)
      }
    }
  }, [])

  const resetExtractionState = () => {
    if (extractionTimeoutRef.current !== null) {
      window.clearTimeout(extractionTimeoutRef.current)
      extractionTimeoutRef.current = null
    }
    setExtractionStatus('idle')
    setExtractionError('')
    setExtractedText('')
  }

  const handleAnswerFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null
    resetExtractionState()
    setAnswerFileError('')

    if (!selected) {
      setAnswerFile(null)
    } else if (!isAcceptedAnswerFile(selected)) {
      setAnswerFile(null)
      setAnswerFileError(
        'Unsupported file type. Please choose a PDF, TXT, PNG, JPG, or JPEG file.'
      )
    } else if (selected.size > MAX_FILE_SIZE_BYTES) {
      setAnswerFile(null)
      setAnswerFileError(
        `File is too large. The maximum upload size is ${MAX_FILE_SIZE_MB} MB.`
      )
    } else {
      setAnswerFile(selected)
    }

    // Reset the input so the same file can be re-selected after removal.
    event.target.value = ''
  }

  const handleRemoveAnswerFile = () => {
    resetExtractionState()
    setAnswerFile(null)
    setAnswerFileError('')
  }

  const handleSourceTextChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setSourceText(event.target.value)
  }

  const handleSourceFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null
    setSourceFileError('')

    if (!selected) {
      setSourceFile(null)
    } else if (!isAcceptedSourceFile(selected)) {
      setSourceFile(null)
      setSourceFileError('Unsupported file type. Please choose a PDF or TXT file.')
    } else if (selected.size > MAX_FILE_SIZE_BYTES) {
      setSourceFile(null)
      setSourceFileError(
        `File is too large. The maximum upload size is ${MAX_FILE_SIZE_MB} MB.`
      )
    } else {
      setSourceFile(selected)
    }

    // Reset the input so the same file can be re-selected after removal.
    event.target.value = ''
  }

  const handleRemoveSourceFile = () => {
    setSourceFile(null)
    setSourceFileError('')
  }

  const extractText = () => {
    if (!answerFile || extractionStatus === 'extracting') {
      return
    }
    setExtractionStatus('extracting')
    setExtractionError('')
    setExtractedText('')

    const extension = answerFile.name.split('.').pop()?.toLowerCase() ?? ''
    if (extension === 'txt' || answerFile.type === 'text/plain') {
      answerFile
        .text()
        .then((text) => {
          setExtractedText(text)
          setExtractionStatus('success')
        })
        .catch(() => {
          setExtractionStatus('error')
          setExtractionError('Failed to read text from the uploaded file.')
        })
      return
    }

    // Demo-only simulation for PDF and image uploads. Backend extraction
    // and OCR (PROJECT_BIBLE.md F4/F5) will process these on the server.
    extractionTimeoutRef.current = window.setTimeout(() => {
      extractionTimeoutRef.current = null
      setExtractionStatus('error')
      setExtractionError(
        'Demo mode: PDF and image OCR text extraction requires the backend pipeline (PROJECT_BIBLE.md F4/F5), which is not connected yet.'
      )
    }, DEMO_EXTRACTION_DELAY_MS)
  }

  // Validation rule from PROJECT_BIBLE.md section 12.3: the
  // answer is required, and at least one source must be
  // supplied through pasted source text or an uploaded file.
  // The extracted AI answer is the content to audit.
  const hasAnswer = extractedText.trim().length > 0
  const hasSource = sourceText.trim().length > 0 || sourceFile !== null
  const canAudit = hasAnswer && hasSource

  const handleAuditSubmit = async () => {
    if (!canAudit || isAuditing) {
      return
    }
    setIsAuditing(true)
    setAuditError('')

    try {
      const files = sourceFile ? [sourceFile] : []
      const result = await submitAudit({
        answer: extractedText,
        sourceText: sourceText.trim() || undefined,
        files,
      })
      setLiveAuditResult(result)
      setIsDemoResult(false)
      setView('results')
      window.scrollTo(0, 0)
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'An unexpected error occurred while communicating with the backend.'
      setAuditError(
        `Could not complete audit (${message}). If the backend server is not running on port 8000 yet, you can still click "View demo results" below to explore the results dashboard.`
      )
    } finally {
      setIsAuditing(false)
    }
  }

  const showDemoResults = () => {
    setIsDemoResult(true)
    setView('results')
    window.scrollTo(0, 0)
  }

  const showInput = () => {
    setView('input')
    window.scrollTo(0, 0)
  }

  const extractionStatusBadge: { label: string; className: string } = (() => {
    switch (extractionStatus) {
      case 'extracting':
        return {
          label: 'Extracting…',
          className:
            'border-sky-300 bg-sky-50 text-sky-700 ring-sky-500/20',
        }
      case 'success':
        return {
          label: 'Extracted',
          className:
            'border-emerald-300 bg-emerald-50 text-emerald-700 ring-emerald-500/20',
        }
      case 'error':
        return {
          label: 'Not extracted',
          className:
            'border-red-300 bg-red-50 text-red-700 ring-red-500/20',
        }
      default:
        return {
          label: answerFile ? 'Ready' : 'Waiting for file',
          className: 'border-slate-300 bg-white text-slate-500 ring-slate-400/20',
        }
    }
  })()

  const extractedTextPlaceholder =
    extractionStatus === 'extracting'
      ? 'Extracting text…'
      : extractionStatus === 'error'
        ? 'No text was extracted in demo mode. Paste or type the AI answer here instead.'
        : answerFile
          ? 'Choose Extract Text to pull the answer from this file, or paste it here.'
          : 'Paste or type the AI-generated answer here.'

  const activeResult: AuditResult =
    !isDemoResult && liveAuditResult ? liveAuditResult : mockAuditResult
  const activeAnswerText =
    !isDemoResult && liveAuditResult ? extractedText : mockAnswerText
  const activeSources =
    !isDemoResult && liveAuditResult
      ? [
          ...(sourceFile
            ? [{ name: sourceFile.name, kind: 'Uploaded document' }]
            : []),
          ...(sourceText.trim()
            ? [{ name: 'Pasted reference text', kind: 'Direct text input' }]
            : []),
        ]
      : mockSources

  return (
    <main
      id="main-content"
      className="relative min-h-screen bg-slate-50 bg-[radial-gradient(ellipse_at_top_right,rgba(167,139,250,0.12),transparent_55%),radial-gradient(ellipse_at_top,rgba(56,189,248,0.10),transparent_60%)] px-4 py-10 text-slate-900 sm:px-6"
    >
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:left-4 focus-visible:top-4 focus-visible:z-50 focus-visible:rounded-lg focus-visible:bg-teal-500 focus-visible:px-4 focus-visible:py-2 focus-visible:text-sm focus-visible:font-semibold focus-visible:text-white"
      >
        Skip to main content
      </a>

      <div
        className={`mx-auto ${view === 'results' ? 'max-w-6xl' : 'max-w-6xl'}`}
      >
        <header className="mb-10 flex flex-wrap items-center gap-4">
          <BrandMark className="h-11 w-11" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold tracking-tight text-slate-900">
              Second Opinion<span className="text-teal-500">.</span>
            </p>
            <p className="text-xs text-slate-500">AI claim verification</p>
          </div>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm">
            {view === 'results' ? 'Audit Results' : 'New audit'}
          </span>
        </header>

        {view === 'results' ? (
          <div>
            {isDemoResult && <DemoBanner />}

            <section
              aria-labelledby="results-title"
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2
                      id="results-title"
                      ref={resultsHeadingRef}
                      tabIndex={-1}
                      className="text-balance text-3xl font-bold tracking-tight text-slate-900 outline-none sm:text-4xl"
                    >
                      Audit Results
                    </h2>
                    {isDemoResult ? (
                      <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-bold tracking-wide text-amber-700">
                        DEMO — MOCK DATA
                      </span>
                    ) : (
                      <span className="rounded-full border border-teal-300 bg-teal-50 px-2.5 py-1 text-xs font-bold tracking-wide text-teal-700">
                        LIVE BACKEND AUDIT
                      </span>
                    )}
                  </div>
                  <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
                    <span className="break-all font-mono text-slate-600">
                      {activeResult.audit_id}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>{formatDate(activeResult.created_at)}</span>
                    <span aria-hidden="true">·</span>
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-500/20">
                      {activeResult.status}
                    </span>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={showInput}
                  className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 motion-safe:transition motion-safe:active:scale-[0.98] hover:border-teal-300 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
                    />
                  </svg>
                  Back to audit input
                </button>
              </div>

              <h3 className="mt-8 text-lg font-semibold text-slate-900">
                Summary
              </h3>
              <div className="mt-3">
                <AuditSummary summary={activeResult.summary} />
              </div>

              <h3 className="mt-8 text-lg font-semibold text-slate-900">
                {isDemoResult ? 'Demonstration answer' : 'Audited answer'}
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                {isDemoResult
                  ? 'The fictional answer below was checked against the fictional sources listed here. Both are synthetic demo content.'
                  : 'The answer evaluated by the backend against the supplied reference material.'}
              </p>
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-pretty text-sm leading-relaxed text-slate-700">
                  {activeAnswerText}
                </p>
              </div>
              <ul className="mt-3 space-y-1.5">
                {activeSources.map((source) => (
                  <li
                    key={source.name}
                    className="flex flex-wrap items-center gap-2 text-sm text-slate-500"
                  >
                    <svg
                      className="h-4 w-4 shrink-0 text-teal-500"
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
                    <span className="font-medium text-slate-700">
                      {source.name}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>{source.kind}</span>
                  </li>
                ))}
              </ul>

              <h3 className="mt-8 text-lg font-semibold text-slate-900">
                Claims{' '}
                <span className="text-sm font-normal text-slate-500">
                  ({activeResult.claims.length})
                </span>
              </h3>
              <div className="mt-3 space-y-4">
                {activeResult.claims.map((claim, index) => (
                  <ClaimCard key={claim.claim_id} claim={claim} index={index} />
                ))}
              </div>

              {isDemoResult && (
                <div className="mt-8 rounded-xl border border-amber-300/60 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                    Demo disclaimer
                  </p>
                  <p className="mt-1 text-pretty text-sm text-slate-600">
                    Every claim, quotation, source, and verdict on this
                    screen is synthetic sample data created for
                    demonstration. Nothing here is a real AI audit, and no
                    evidence shown is a verified real-world fact.
                  </p>
                </div>
              )}

              <div className="mt-6">
                <button
                  type="button"
                  onClick={showInput}
                  className="inline-flex items-center gap-2 rounded-xl bg-teal-500 px-5 py-3 font-semibold text-white motion-safe:transition motion-safe:active:scale-[0.98] hover:bg-teal-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
                    />
                  </svg>
                  Back to audit input
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div>
            {/* Hero — the product's promise and the three-step loop. */}
            <div className="mb-10">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-teal-700">
                AI trust &amp; verification
              </span>
              <h1
                ref={inputHeadingRef}
                tabIndex={-1}
                className="mt-4 text-balance text-4xl font-bold tracking-tight text-slate-900 outline-none sm:text-5xl"
              >
                Get a second opinion on{' '}
                <span className="text-teal-600">AI-generated answers</span>
              </h1>
              <p className="mt-4 max-w-2xl text-pretty text-base leading-relaxed text-slate-600">
                Upload an AI-generated answer, extract its text, and check
                its claims against the source material you provide.
              </p>

              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                {WORKFLOW_STEPS.map((step) => (
                  <div
                    key={step.number}
                    className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-sm motion-safe:transition motion-safe:hover:shadow-md"
                  >
                    <div className="flex items-center justify-between">
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={1.5}
                          stroke="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d={step.icon}
                          />
                        </svg>
                      </span>
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Step {step.number}
                      </span>
                    </div>
                    <h2 className="mt-3 text-sm font-semibold text-slate-900">
                      {step.title}
                    </h2>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500">
                      {step.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* The two inputs, side by side on large screens. */}
            <div className="grid items-start gap-6 lg:grid-cols-2">
              {/* Step 1 — the AI-generated answer to audit. */}
              <section
                aria-labelledby="answer-step-label"
                className="overflow-hidden rounded-2xl border border-teal-200 bg-white shadow-sm"
              >
                <div className="border-b border-teal-100 bg-teal-50/60 px-6 py-4 sm:px-8">
                  <p
                    id="answer-step-label"
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700"
                  >
                    Step 1 · AI-generated answer
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    The answer whose claims will be audited.
                  </p>
                </div>
                <div className="p-6 sm:p-8">
                  <label
                    htmlFor="answer-file"
                    className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-teal-300 bg-teal-50/60 px-4 py-8 text-center motion-safe:transition hover:border-teal-400 hover:bg-teal-50 peer-focus-visible:border-teal-400 peer-focus-visible:ring-2 peer-focus-visible:ring-teal-400/20"
                  >
                    <input
                      id="answer-file"
                      type="file"
                      accept=".pdf,.txt,.png,.jpg,.jpeg,application/pdf,text/plain,image/png,image/jpeg"
                      onChange={handleAnswerFileChange}
                      className="peer sr-only"
                    />
                    <svg
                      className="h-9 w-9 text-teal-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                      />
                    </svg>
                    <span className="text-base font-semibold text-slate-800">
                      {answerFile ? 'Replace file' : 'Upload the AI-generated answer'}
                    </span>
                    <span className="text-sm text-slate-500">
                      PDF, TXT, PNG, JPG, or JPEG
                    </span>
                    <span className="text-xs text-slate-400">
                      Maximum {MAX_FILE_SIZE_MB} MB
                    </span>
                  </label>

                  {answerFile && (
                    <div className="mt-3 space-y-3">
                      <div className="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50/40 px-4 py-3">
                        <svg
                          className="h-5 w-5 shrink-0 text-teal-500"
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
                        <div className="min-w-0 flex-1">
                          <p
                            className="truncate text-sm font-medium text-slate-800"
                            title={answerFile.name}
                          >
                            {answerFile.name}
                          </p>
                          <p className="text-xs text-slate-500">
                            {formatFileSize(answerFile.size)}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={handleRemoveAnswerFile}
                          aria-label={`Remove ${answerFile.name}`}
                          className="shrink-0 rounded-lg p-1.5 text-slate-400 motion-safe:transition hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                        </button>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={extractText}
                          disabled={extractionStatus === 'extracting'}
                          className="rounded-xl border border-teal-300 bg-white px-4 py-2.5 text-sm font-semibold text-teal-700 motion-safe:transition motion-safe:active:scale-[0.98] hover:border-teal-400 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {extractionStatus === 'extracting'
                            ? 'Extracting…'
                            : 'Extract Text'}
                        </button>
                        <span className="text-xs text-slate-500">
                          Demo only — no text is extracted until the backend
                          extraction API is connected.
                        </span>
                      </div>
                    </div>
                  )}

                  {answerFileError && (
                    <p
                      role="alert"
                      className="mt-2 flex items-start gap-1.5 text-xs text-red-600 sm:text-sm"
                    >
                      <svg
                        className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                        />
                      </svg>
                      <span>{answerFileError}</span>
                    </p>
                  )}

                  <div className="mt-6">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <label
                        htmlFor="extracted-text"
                        className="text-sm font-medium text-slate-800"
                      >
                        Extracted AI Answer
                      </label>
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${extractionStatusBadge.className}`}
                      >
                        {extractionStatusBadge.label}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {answerFile
                        ? `From ${answerFile.name} — edit the text below if it needs correcting.`
                        : 'Upload a file above, or paste the answer manually below.'}
                    </p>
                    <textarea
                      id="extracted-text"
                      value={extractedText}
                      onChange={(event) => setExtractedText(event.target.value)}
                      disabled={extractionStatus === 'extracting'}
                      placeholder={extractedTextPlaceholder}
                      className="mt-2 min-h-36 w-full resize-y rounded-xl border border-slate-300 bg-white p-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus-visible:border-teal-400 focus-visible:ring-2 focus-visible:ring-teal-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                    />

                    {extractionStatus === 'extracting' && (
                      <p
                        role="status"
                        className="mt-2 flex items-center gap-2 text-xs text-sky-600 sm:text-sm"
                      >
                        <svg
                          className="h-4 w-4 motion-safe:animate-spin"
                          viewBox="0 0 24 24"
                          fill="none"
                          aria-hidden="true"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-90"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                          />
                        </svg>
                        <span>
                          Extracting text from {answerFile?.name}…{' '}
                          <span className="text-slate-500">
                            (demo only — no real extraction is running)
                          </span>
                        </span>
                      </p>
                    )}

                    {extractionStatus === 'error' && (
                      <p
                        role="alert"
                        className="mt-2 flex items-start gap-1.5 text-xs text-red-600 sm:text-sm"
                      >
                        <svg
                          className="mt-0.5 h-3.5 w-3.5 shrink-0"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={1.5}
                          stroke="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                          />
                        </svg>
                        <span>{extractionError}</span>
                      </p>
                    )}

                    {extractionStatus === 'success' && (
                      <p
                        role="status"
                        className="mt-2 flex items-center gap-2 text-xs text-emerald-600 sm:text-sm"
                      >
                        <svg
                          className="h-3.5 w-3.5 shrink-0"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={1.5}
                          stroke="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        <span>
                          Text extracted successfully. Review and edit it above.
                        </span>
                      </p>
                    )}
                  </div>
                </div>
              </section>

              {/* Step 2 — the source material used to verify the answer. */}
              <section
                aria-labelledby="source-step-label"
                className="overflow-hidden rounded-2xl border border-violet-200 bg-white shadow-sm"
              >
                <div className="border-b border-violet-100 bg-violet-50/60 px-6 py-4 sm:px-8">
                  <p
                    id="source-step-label"
                    className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700"
                  >
                    Step 2 · Source material
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Reference material used to verify the answer's claims —
                    kept separate from the answer.
                  </p>
                </div>
                <div className="p-6 sm:p-8">
                  <label
                    htmlFor="source-text"
                    className="block text-sm font-medium text-slate-800"
                  >
                    Pasted source text
                  </label>
                  <textarea
                    id="source-text"
                    value={sourceText}
                    onChange={handleSourceTextChange}
                    placeholder="Paste source text, excerpts, or reference material..."
                    className="mt-2 min-h-32 w-full resize-y rounded-xl border border-slate-300 bg-white p-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus-visible:border-violet-400 focus-visible:ring-2 focus-visible:ring-violet-400/20"
                  />

                  <div className="mt-6 flex items-center gap-3" aria-hidden="true">
                    <span className="h-px flex-1 bg-slate-200" />
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
                      or upload a source document
                    </span>
                    <span className="h-px flex-1 bg-slate-200" />
                  </div>

                  <label
                    htmlFor="source-material-file"
                    className="mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-violet-300 bg-violet-50/60 px-4 py-6 text-center motion-safe:transition hover:border-violet-400 hover:bg-violet-50 peer-focus-visible:border-violet-400 peer-focus-visible:ring-2 peer-focus-visible:ring-violet-400/20"
                  >
                    <input
                      id="source-material-file"
                      type="file"
                      accept=".pdf,.txt,application/pdf,text/plain"
                      onChange={handleSourceFileChange}
                      className="peer sr-only"
                    />
                    <svg
                      className="h-8 w-8 text-violet-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                      />
                    </svg>
                    <span className="text-sm font-medium text-slate-800">
                      {sourceFile ? 'Replace source document' : 'Upload a source document'}
                    </span>
                    <span className="text-xs text-slate-500">
                      PDF or TXT · Maximum {MAX_FILE_SIZE_MB} MB
                    </span>
                  </label>

                  {sourceFile && (
                    <div className="mt-3 flex items-center gap-3 rounded-xl border border-violet-200 bg-violet-50/40 px-4 py-3">
                      <svg
                        className="h-5 w-5 shrink-0 text-violet-500"
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
                      <div className="min-w-0 flex-1">
                        <p
                          className="truncate text-sm font-medium text-slate-800"
                          title={sourceFile.name}
                        >
                          {sourceFile.name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatFileSize(sourceFile.size)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={handleRemoveSourceFile}
                        aria-label={`Remove ${sourceFile.name}`}
                        className="shrink-0 rounded-lg p-1.5 text-slate-400 motion-safe:transition hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                      >
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={1.5}
                          stroke="currentColor"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M6 18L18 6M6 6l12 12"
                          />
                        </svg>
                      </button>
                    </div>
                  )}

                  {sourceFileError && (
                    <p
                      role="alert"
                      className="mt-2 flex items-start gap-1.5 text-xs text-red-600 sm:text-sm"
                    >
                      <svg
                        className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                        />
                      </svg>
                      <span>{sourceFileError}</span>
                    </p>
                  )}
                </div>
              </section>
            </div>

            {/* Actions */}
            <section
              aria-label="Audit actions"
              className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={!canAudit || isAuditing}
                  onClick={handleAuditSubmit}
                  className="w-full rounded-xl bg-teal-500 px-5 py-3.5 font-semibold text-white motion-safe:transition motion-safe:active:scale-[0.98] hover:bg-teal-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
                >
                  {isAuditing ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg
                        className="h-4 w-4 motion-safe:animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                        aria-hidden="true"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-90"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      Auditing answer…
                    </span>
                  ) : (
                    'Audit Answer →'
                  )}
                </button>

                <button
                  type="button"
                  onClick={showDemoResults}
                  className="w-full rounded-xl border border-slate-300 bg-white px-5 py-3.5 font-semibold text-slate-700 motion-safe:transition motion-safe:active:scale-[0.98] hover:border-teal-300 hover:text-teal-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 sm:w-auto"
                >
                  View demo results
                </button>
              </div>

              {auditError && (
                <div
                  role="alert"
                  className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4"
                >
                  <div className="flex items-start gap-2.5">
                    <svg
                      className="mt-0.5 h-4 w-4 shrink-0 text-red-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                      />
                    </svg>
                    <div className="min-w-0 flex-1 text-xs text-red-700 sm:text-sm">
                      <p className="font-semibold text-red-800">
                        Backend connection notice
                      </p>
                      <p className="mt-0.5 leading-relaxed">{auditError}</p>
                    </div>
                  </div>
                </div>
              )}

              {!canAudit && (
                <p className="mt-2 text-xs text-slate-500">
                  Add an AI answer (extracted or pasted) and at least
                  one source (pasted text or a PDF/TXT file) to enable
                  this button.
                </p>
              )}

              <p className="mt-4 text-xs text-slate-400">
                Prototype mode · Results are not yet connected to the
                auditing backend.
              </p>
            </section>
          </div>
        )}

        <footer className="mt-8 text-center text-sm text-slate-400">
          Evidence over confidence. Transparency over blind trust.
        </footer>
      </div>
    </main>
  )
}

export default App
