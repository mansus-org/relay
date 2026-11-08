import * as Location from 'expo-location'

import type { LocationProvider, PlaceNamer } from '../../domain'

const toStatus = ({ granted, canAskAgain }: Location.LocationPermissionResponse) => ({ granted, canAskAgain })

export const makeExpoLocationProvider = (): LocationProvider => ({
  status: async () => toStatus(await Location.getForegroundPermissionsAsync()),
  request: async () => toStatus(await Location.requestForegroundPermissionsAsync()),
  currentPosition: async () => {
    try {
      const { coords } = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      return { lat: coords.latitude, lng: coords.longitude }
    } catch {
      return null
    }
  },
})

/** "Pinheiros, São Paulo" from the device geocoder. Not available on web, where it returns null. */
export const makeExpoPlaceNamer = (): PlaceNamer => ({
  async nameOf({ lat, lng }) {
    try {
      const [place] = await Location.reverseGeocodeAsync({ latitude: lat, longitude: lng })
      if (!place) return null
      const area = place.district ?? place.subregion ?? place.name
      const city = place.city ?? place.region
      const parts = [area, city].filter((part, i, all): part is string => !!part && all.indexOf(part) === i)
      return parts.length ? parts.join(', ') : null
    } catch {
      return null
    }
  },
})
