import { useCallback, useEffect, useState } from 'react'
import { AppState } from 'react-native'

import type { NearbyCommunity } from '../domain'
import { useUseCases } from './use-cases'

export type NearbyPhase = 'locating' | 'denied' | 'ready'

export type NearbyState = {
  phase: NearbyPhase
  canAskAgain: boolean
  placeName: string | null
  communities: readonly NearbyCommunity[]
  refreshing: boolean
  /** True when the last load failed. */
  failed: boolean
}

const initial: NearbyState = { phase: 'locating', canAskAgain: true, placeName: null, communities: [], refreshing: false, failed: false }

/** Location → H3 cell → communities near it, nearest first. */
export function useNearbyCommunities() {
  const { resolveLocation, loadNearbyCommunities } = useUseCases()
  const [state, setState] = useState<NearbyState>(initial)

  const patch = useCallback((next: Partial<NearbyState>) => setState((s) => ({ ...s, ...next })), [])

  /** `prompt` allows the permission dialog. */
  const start = useCallback(
    async (prompt: boolean) => {
      const location = await resolveLocation({ prompt })
      if (!location.ok) {
        if (location.error.kind === 'denied') patch({ phase: 'denied', canAskAgain: location.error.canAskAgain, refreshing: false })
        else patch({ phase: 'ready', failed: true, refreshing: false })
        return
      }
      const result = await loadNearbyCommunities({ cell: location.value.cell })
      if (result.ok) patch({ phase: 'ready', placeName: location.value.placeName, communities: result.value, failed: false })
      else patch({ phase: 'ready', placeName: location.value.placeName, failed: true })
    },
    [resolveLocation, loadNearbyCommunities, patch],
  )

  useEffect(() => {
    // start() only sets state after the first await, so this is not a synchronous update.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start(true)
  }, [start])

  // Returning from the system settings screen after granting permission.
  const denied = state.phase === 'denied'
  useEffect(() => {
    if (!denied) return
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') void start(false)
    })
    return () => sub.remove()
  }, [denied, start])

  const refresh = useCallback(async () => {
    patch({ refreshing: true })
    await start(false)
    patch({ refreshing: false })
  }, [start, patch])

  return { state, enableLocation: () => start(true), refresh }
}
