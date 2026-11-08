import { AxiosError, type AxiosInstance } from 'axios'

import { err, ok, type PostalCodeError, type PostalCodeResolver } from '../../domain'
import { toApiError, statusOf } from './api-error'
import { postalCodePath } from './endpoints'

type PostalAreaDto = { postal_code: string; place_name: string; cell: string }

/** FastAPI puts the reason in `detail`, and that sentence is the one worth showing. */
const detailOf = (error: unknown): string => {
  const detail = error instanceof AxiosError ? (error.response?.data as { detail?: unknown } | undefined)?.detail : undefined
  return typeof detail === 'string' ? detail : ''
}

const toPostalCodeError = (error: unknown): PostalCodeError => {
  const message = detailOf(error)
  switch (statusOf(error)) {
    case 400:
      return { reason: 'invalid', message }
    case 404:
      return { reason: 'not-found', message }
    case 503:
      return { reason: 'unavailable', message }
    default:
      return { reason: toApiError(error), message: '' }
  }
}

export const makeHttpPostalCodeResolver = ({ http }: { http: AxiosInstance }): PostalCodeResolver => ({
  async resolve(code) {
    try {
      const { data } = await http.get<PostalAreaDto>(postalCodePath(code))
      return ok({ postalCode: data.postal_code, placeName: data.place_name, cell: data.cell })
    } catch (error) {
      return err(toPostalCodeError(error))
    }
  },
})
