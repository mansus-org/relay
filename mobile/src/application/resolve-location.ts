import { err, ok, type CellEncoder, type LocationProvider, type PlaceNamer, type Result } from '../domain'

export type ResolvedLocation = { readonly cell: string; readonly placeName: string | null }

/** 'denied' means permission is missing; `canAskAgain` tells whether the OS prompt can still be shown. */
export type LocationError = { readonly kind: 'denied'; readonly canAskAgain: boolean } | { readonly kind: 'unavailable' }

type Deps = {
  readonly locationProvider: LocationProvider
  readonly cellEncoder: CellEncoder
  readonly placeNamer: PlaceNamer
}

/**
 * Turns the device position into an H3 cell and place name. With `prompt` it asks for permission
 * when needed; without it, missing permission is reported as is (compose never prompts).
 */
export const makeResolveLocation =
  ({ locationProvider, cellEncoder, placeNamer }: Deps) =>
  async ({ prompt }: { prompt: boolean }): Promise<Result<ResolvedLocation, LocationError>> => {
    let status = await locationProvider.status()
    if (!status.granted && prompt && status.canAskAgain) status = await locationProvider.request()
    if (!status.granted) return err({ kind: 'denied', canAskAgain: status.canAskAgain })
    const position = await locationProvider.currentPosition()
    if (!position) return err({ kind: 'unavailable' })
    const cell = cellEncoder.cellOf(position)
    return ok({ cell, placeName: await placeNamer.nameOf(cellEncoder.centerOf(cell)) })
  }

/** Place name of a cell (its centroid), remembered per factory instance so a feed does not repeat lookups. */
export const makeCellPlaceName = ({ cellEncoder, placeNamer }: Pick<Deps, 'cellEncoder' | 'placeNamer'>) => {
  const names = new Map<string, Promise<string | null>>()
  return (cell: string): Promise<string | null> => {
    let name = names.get(cell)
    if (!name) {
      name = placeNamer.nameOf(cellEncoder.centerOf(cell)).catch(() => null)
      names.set(cell, name)
    }
    return name
  }
}
