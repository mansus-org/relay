import { useState, type ReactNode } from 'react'
import { fetch as streamFetch } from 'expo/fetch'
import { Platform } from 'react-native'

import type { StreamFetch } from '../infrastructure/stream/fetch-post-stream'
import { makeAsyncStorage } from '../infrastructure/storage/async-storage'
import { makeSecureStoreStorage } from '../infrastructure/storage/secure-store'
import { AuthProvider } from '../presentation/auth'
import { UseCasesProvider } from '../presentation/use-cases'
import { wireUseCases } from './wire-use-cases'

/** Root of the app tree: wires the real adapters once and provides the use cases to the UI. */
export function AppProviders({ children }: { children: ReactNode }) {
  const [useCases] = useState(() =>
    wireUseCases({
      secureStorage: makeSecureStoreStorage(),
      preferenceStorage: makeAsyncStorage(),
      fixedApiBaseUrl: Platform.OS === 'web' ? '/api' : undefined,
      streamFetch: streamFetch as unknown as StreamFetch,
    }),
  )
  return (
    <UseCasesProvider useCases={useCases}>
      <AuthProvider>{children}</AuthProvider>
    </UseCasesProvider>
  )
}
