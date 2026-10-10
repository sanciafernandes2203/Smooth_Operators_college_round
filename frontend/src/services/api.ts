import type { ApiErrorResponse } from '../types/api'

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  'http://localhost:8000'

/**
 * Extract a human-readable error message from an API response,
 * falling back to HTTP status text if not formatted as JSON.
 */
export async function parseApiError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as ApiErrorResponse
    if (data?.error?.message) {
      return data.error.message
    }
  } catch {
    // Response was not JSON
  }
  return `Server returned ${response.status} ${response.statusText}`.trim()
}
