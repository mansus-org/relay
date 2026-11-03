import { useCallback, useEffect, useState } from 'react'

import { clampRadius, DEFAULT_RADIUS_KM, type CreateCommunityError } from '../domain'
import { useUseCases } from './use-cases'

/** State of the create-community sheet. The device position is read once, without prompting. */
export function useCreateCommunity() {
  const { resolveLocation, createCommunity } = useUseCases()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState<{ cell: string; placeName: string | null } | null>(null)
  const [useLocation, setUseLocation] = useState(true)
  const [locationBusy, setLocationBusy] = useState(true)
  const [radiusKm, setRadiusKm] = useState(DEFAULT_RADIUS_KM)
  const [allowPseudonyms, setAllowPseudonyms] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<CreateCommunityError | 'no-location' | null>(null)

  useEffect(() => {
    let cancelled = false
    void resolveLocation({ prompt: true }).then((result) => {
      if (cancelled) return
      if (result.ok) setLocation(result.value)
      setLocationBusy(false)
    })
    return () => {
      cancelled = true
    }
  }, [resolveLocation])

  const edit = <T,>(set: (value: T) => void) => (value: T) => {
    set(value)
    setError(null)
  }

  /** Whether "Use my current location" is effectively on: wanted and the position is known. */
  const locationOn = useLocation && location !== null

  const submit = useCallback(async (): Promise<boolean> => {
    if (busy) return false
    if (useLocation && !location) {
      setError('no-location')
      return false
    }
    setBusy(true)
    setError(null)
    const result = await createCommunity({
      name,
      description,
      locationCell: useLocation && location ? location.cell : undefined,
      radiusKm,
      allowPseudonyms,
    })
    setBusy(false)
    if (!result.ok) setError(result.error)
    return result.ok
  }, [busy, useLocation, location, createCommunity, name, description, radiusKm, allowPseudonyms])

  return {
    name,
    setName: edit(setName),
    description,
    setDescription: edit(setDescription),
    useLocation,
    setUseLocation: edit(setUseLocation),
    locationOn,
    locationBusy,
    placeName: location?.placeName ?? null,
    radiusKm,
    setRadiusKm: (km: number) => setRadiusKm(clampRadius(km)),
    allowPseudonyms,
    setAllowPseudonyms: edit(setAllowPseudonyms),
    busy,
    error,
    submit,
  }
}
