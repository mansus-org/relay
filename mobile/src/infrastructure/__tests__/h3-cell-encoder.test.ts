import { getResolution } from 'h3-js'
import { makeH3CellEncoder } from '../location/h3-cell-encoder'

describe('H3 cell encoder', () => {
  const encoder = makeH3CellEncoder()
  const position = { lat: -23.5614, lng: -46.6919 }

  it('encodes a position as a resolution 8 cell', () => {
    expect(getResolution(encoder.cellOf(position))).toBe(8)
  })

  it('gives a centroid inside the same cell', () => {
    const cell = encoder.cellOf(position)
    expect(encoder.cellOf(encoder.centerOf(cell))).toBe(cell)
  })
})
