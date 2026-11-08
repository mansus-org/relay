import { cellToLatLng, latLngToCell } from 'h3-js'

import type { CellEncoder } from '../../domain'

export const H3_RESOLUTION = 8

export const makeH3CellEncoder = (): CellEncoder => ({
  cellOf: ({ lat, lng }) => latLngToCell(lat, lng, H3_RESOLUTION),
  centerOf: (cell) => {
    const [lat, lng] = cellToLatLng(cell)
    return { lat: lat!, lng: lng! }
  },
})
