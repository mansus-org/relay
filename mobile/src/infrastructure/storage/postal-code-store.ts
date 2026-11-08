import type { PostalCodeReader, PostalCodeWriter } from '../../domain'
import type { KeyValueStorage } from './key-value'

export const POSTAL_CODE_KEY = 'relay_postal_code'

export const makePostalCodeStore = ({ storage }: { storage: KeyValueStorage }): PostalCodeReader & PostalCodeWriter => ({
  read: async () => (await storage.get(POSTAL_CODE_KEY)) ?? null,
  save: (code) => storage.set(POSTAL_CODE_KEY, code),
})
