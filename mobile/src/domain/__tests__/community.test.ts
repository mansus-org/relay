import { makeCommunity } from '../../testing/fakes'
import {
  clampRadius,
  distanceKm,
  excerpt,
  formatDistance,
  placeCommunity,
  sortByDistance,
  validateNewCommunity,
  type NearbyCommunity,
} from '../community'

const centerOf = (cell: string) => {
  const [lat, lng] = cell.split(',').map(Number)
  return { lat: lat!, lng: lng! }
}
const here = { lat: 0, lng: 0 }

describe('distanceKm', () => {
  it('is zero for the same point and about 111 km per degree of latitude', () => {
    expect(distanceKm(here, here)).toBe(0)
    expect(distanceKm(here, { lat: 1, lng: 0 })).toBeCloseTo(111.19, 1)
  })
})

describe('placeCommunity', () => {
  it('is in range within the radius and out of range beyond it', () => {
    const near = placeCommunity(makeCommunity('a', { locationCell: '0.01,0', radiusKm: 5 }), here, centerOf)
    const far = placeCommunity(makeCommunity('b', { locationCell: '0.2,0', radiusKm: 5 }), here, centerOf)
    expect(near.inRange).toBe(true)
    expect(near.distanceKm).toBeCloseTo(1.11, 1)
    expect(far.inRange).toBe(false)
    expect(far.distanceKm).toBeCloseTo(22.2, 0)
  })

  it('treats a community without a location as joinable from anywhere', () => {
    expect(placeCommunity(makeCommunity('c'), here, centerOf)).toMatchObject({ distanceKm: null, inRange: true })
  })
})

describe('sortByDistance', () => {
  const at = (id: string, distance: number | null): NearbyCommunity => ({ ...makeCommunity(id), distanceKm: distance, inRange: true })

  it('puts the nearest first and communities without a location last, keeping ties stable', () => {
    const sorted = sortByDistance([at('far', 7), at('none', null), at('tie1', 2), at('near', 1), at('tie2', 2)])
    expect(sorted.map((c) => c.id)).toEqual(['near', 'tie1', 'tie2', 'far', 'none'])
  })
})

describe('formatDistance', () => {
  it('rounds to whole kilometres', () => {
    expect(formatDistance(2.2)).toBe('~2 km away')
    expect(formatDistance(0.4)).toBe('<1 km away')
    expect(formatDistance(null)).toBeNull()
  })
})

describe('excerpt', () => {
  it('keeps short text and cuts long text on a word with an ellipsis', () => {
    expect(excerpt('short  text')).toBe('short text')
    expect(excerpt('one two three four five', 14)).toBe('one two three…')
  })
})

describe('community input', () => {
  it('clamps the radius to 1–50 km', () => {
    expect([clampRadius(0), clampRadius(7.4), clampRadius(99)]).toEqual([1, 7, 50])
  })

  it('validates name and radius', () => {
    expect(validateNewCommunity({ name: '  ', radiusKm: 5 })).toBe('empty-name')
    expect(validateNewCommunity({ name: 'x'.repeat(81), radiusKm: 5 })).toBe('name-too-long')
    expect(validateNewCommunity({ name: 'ok', radiusKm: 51 })).toBe('bad-radius')
    expect(validateNewCommunity({ name: 'ok', radiusKm: 5 })).toBeNull()
  })
})
