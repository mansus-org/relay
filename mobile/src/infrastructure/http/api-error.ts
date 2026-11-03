import { AxiosError } from 'axios'

import type { ApiError } from '../../domain'

export const toApiError = (error: unknown): ApiError =>
  error instanceof AxiosError && !error.response ? 'network' : 'unexpected'

export const statusOf = (error: unknown): number | undefined => (error instanceof AxiosError ? error.response?.status : undefined)
