import { err, ok, type PostalCodeError } from '../../domain'
import { makeFakePostalCodeResolver, makePostalArea } from '../../testing/fakes'
import { makeReadPostalCode, makeResolvePostalCode } from '../resolve-postal-code'

const vigo = makePostalArea('36201', 'Vigo', 'cell-vigo')

const makeStore = (initial: string | null = null) => {
  let saved = initial
  return {
    store: { read: async () => saved, save: async (code: string) => void (saved = code) },
    current: () => saved,
  }
}

describe('resolvePostalCode', () => {
  it('resolves a code and remembers it for the next visit', async () => {
    const { store, current } = makeStore()
    const resolver = makeFakePostalCodeResolver({ '36201': vigo })
    const result = await makeResolvePostalCode({ resolver, store })(' 36201 ')
    expect(result).toEqual(ok(vigo))
    expect(current()).toBe('36201')
  })

  it('asks nobody before the code is even shaped like one', async () => {
    const { store, current } = makeStore()
    const resolver = makeFakePostalCodeResolver({ '36201': vigo })
    const result = await makeResolvePostalCode({ resolver, store })('362')
    expect(result).toEqual(err({ reason: 'invalid', message: '' }))
    expect(resolver.calls).toEqual([])
    expect(current()).toBeNull()
  })

  it('does not remember a code Relay has no place for', async () => {
    const { store, current } = makeStore()
    const failure: PostalCodeError = { reason: 'not-found', message: 'Relay is in Galicia for now.' }
    const resolver = makeFakePostalCodeResolver({}, failure)
    const result = await makeResolvePostalCode({ resolver, store })('28001')
    expect(result).toEqual(err(failure))
    expect(current()).toBeNull()
  })

  it('keeps the last good code when a later one fails', async () => {
    const { store, current } = makeStore()
    const resolver = makeFakePostalCodeResolver({ '36201': vigo })
    const resolve = makeResolvePostalCode({ resolver, store })
    await resolve('36201')
    await resolve('99999')
    expect(current()).toBe('36201')
  })
})

describe('readPostalCode', () => {
  it('is empty until a place is chosen', async () => {
    expect(await makeReadPostalCode({ store: makeStore().store })()).toBeNull()
  })

  it('reads back what was saved', async () => {
    const { store } = makeStore()
    await makeResolvePostalCode({ resolver: makeFakePostalCodeResolver({ '36201': vigo }), store })('36201')
    expect(await makeReadPostalCode({ store })()).toBe('36201')
  })
})
