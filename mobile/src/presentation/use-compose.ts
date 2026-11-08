import { useCallback, useEffect, useState } from 'react'

import type { Community, ComposeError } from '../domain'
import { useUseCases } from './use-cases'

/** State of the compose screen: text, optional location cell, optional community. */
export function useCompose() {
  const { resolveLocation, listJoinedCommunities, createPost } = useUseCases()
  const [body, setBody] = useState('')
  const [location, setLocation] = useState<{ cell: string; placeName: string | null } | null>(null)
  const [locationOn, setLocationOn] = useState(false)
  const [locationBusy, setLocationBusy] = useState(true)
  const [communities, setCommunities] = useState<readonly Community[]>([])
  const [communityId, setCommunityId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ComposeError | null>(null)

  // On by default when permission is already granted; never prompts on open.
  useEffect(() => {
    let cancelled = false
    void resolveLocation({ prompt: false }).then((result) => {
      if (cancelled) return
      if (result.ok) {
        setLocation(result.value)
        setLocationOn(true)
      }
      setLocationBusy(false)
    })
    void listJoinedCommunities().then((result) => {
      if (!cancelled && result.ok) setCommunities(result.value)
    })
    return () => {
      cancelled = true
    }
  }, [resolveLocation, listJoinedCommunities])

  const clearLocation = useCallback(() => setLocationOn(false), [])

  /** Turns location back on, asking for permission if it has not been resolved yet. */
  const addLocation = useCallback(async () => {
    if (location) return setLocationOn(true)
    setLocationBusy(true)
    const result = await resolveLocation({ prompt: true })
    if (result.ok) {
      setLocation(result.value)
      setLocationOn(true)
    }
    setLocationBusy(false)
  }, [location, resolveLocation])

  const toggleCommunity = useCallback((id: string) => setCommunityId((current) => (current === id ? null : id)), [])

  const submit = useCallback(async (): Promise<boolean> => {
    if (busy) return false
    setBusy(true)
    setError(null)
    const result = await createPost({
      body,
      locationCell: locationOn && location ? location.cell : undefined,
      communityId: communityId ?? undefined,
    })
    setBusy(false)
    if (!result.ok) setError(result.error)
    return result.ok
  }, [busy, body, createPost, location, locationOn, communityId])

  return {
    body,
    setBody: (next: string) => (setBody(next), setError(null)),
    location: locationOn ? location : null,
    locationBusy,
    addLocation,
    clearLocation,
    communities,
    communityId,
    toggleCommunity,
    busy,
    error,
    submit,
  }
}
