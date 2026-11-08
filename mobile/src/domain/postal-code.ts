export const POSTAL_CODE_LENGTH = 5

/** A Spanish postal code is five digits. Whether Relay serves it is the server's call, not ours. */
const FIVE_DIGITS = /^\d{5}$/

export type PostalArea = {
  readonly postalCode: string
  /** The place the code names, as the server spells it: "Vigo". */
  readonly placeName: string
  /** H3 cell to read the feed from. */
  readonly cell: string
}

/** 'invalid' is caught before any request; the rest are the server's answers. */
export type PostalCodeReason = 'invalid' | 'not-found' | 'unavailable' | 'network' | 'unexpected'

/**
 * `message` carries the server's own words when it has any, so what Relay covers stays the
 * server's to state instead of a second copy of the rule here.
 */
export type PostalCodeError = { readonly reason: PostalCodeReason; readonly message: string }

const FALLBACK: Record<PostalCodeReason, string> = {
  invalid: 'Postal codes are 5 digits.',
  'not-found': 'Relay could not find that postal code.',
  unavailable: "Relay's postal data could not be read. Try again in a moment.",
  network: 'Could not reach Relay. Check your connection and try again.',
  unexpected: 'Something went wrong looking up that postal code.',
}

export const isPostalCode = (raw: string): boolean => FIVE_DIGITS.test(raw.trim())

/** What to show under the field: the server's words when it sent any, our own when it did not. */
export const postalCodeMessage = (error: PostalCodeError): string => error.message || FALLBACK[error.reason]
