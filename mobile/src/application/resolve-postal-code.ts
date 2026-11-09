import { err, isPostalCode, type PostalArea, type PostalCodeError, type PostalCodeReader, type PostalCodeResolver, type PostalCodeWriter, type Result } from '../domain'

/** A place nothing could locate, named by hand instead; a code that resolves is kept for the next visit. */
export const makeResolvePostalCode =
  ({ resolver, store }: { resolver: PostalCodeResolver; store: PostalCodeWriter }) =>
  async (raw: string): Promise<Result<PostalArea, PostalCodeError>> => {
    const code = raw.trim()
    if (!isPostalCode(code)) return err({ reason: 'invalid', message: '' })
    const area = await resolver.resolve(code)
    if (area.ok) await store.save(area.value.postalCode)
    return area
  }

/** The place to open the feed on, before anything is on screen. */
export const makeReadPostalCode =
  ({ store }: { store: PostalCodeReader }) =>
  (): Promise<string | null> => store.read()
