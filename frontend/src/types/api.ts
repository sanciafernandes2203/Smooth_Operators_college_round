/**
 * API error shape from PROJECT_BIBLE.md section 12.7.
 */
export interface ApiError {
  code: string
  message: string
}

export interface ApiErrorResponse {
  error: ApiError
}
