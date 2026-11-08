import { isPostalCode, postalCodeMessage } from '../postal-code'

describe('postal codes', () => {
  it.each(['36201', '15003', '  27001 '])('accepts %s', (raw) => {
    expect(isPostalCode(raw)).toBe(true)
  })

  it.each(['', '3620', '362010', '3620A', '36 201', 'abc'])('rejects %s', (raw) => {
    expect(isPostalCode(raw)).toBe(false)
  })

  it('says what the server said when it said something', () => {
    expect(postalCodeMessage({ reason: 'not-found', message: '32999 is not in Relay\'s data yet.' })).toBe(
      "32999 is not in Relay's data yet.",
    )
  })

  it.each([
    ['invalid', 'Postal codes are 5 digits.'],
    ['not-found', 'Relay could not find that postal code.'],
    ['unavailable', "Relay's postal data could not be read. Try again in a moment."],
    ['network', 'Could not reach Relay. Check your connection and try again.'],
    ['unexpected', 'Something went wrong looking up that postal code.'],
  ] as const)('falls back for %s', (reason, expected) => {
    expect(postalCodeMessage({ reason, message: '' })).toBe(expected)
  })
})
