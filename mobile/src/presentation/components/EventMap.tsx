import { useMemo, useState } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'

import { formatEventTime, regionDeltaFor, type LatLng, type MapPin } from '../../domain'
import { colors, fonts, line } from '../theme'
import { GridPaperLight } from './Geo'
import { MonoLabel } from './MonoLabel'

type Size = { width: number; height: number }

/** Degrees of latitude and longitude are not the same distance; longitude is squeezed by the latitude. */
const squeeze = (lat: number) => Math.cos((lat * Math.PI) / 180) || 1

const KM_PER_DEGREE = 111

type Projection = {
  readonly to: (point: LatLng) => { x: number; y: number }
  readonly pxPerKm: number
}

/**
 * Fit the reader's reach and every pin into the box, keeping the ratio between the two, so the map
 * is honest about relative positions without a tile server. Nothing is clipped: a pin outside the
 * first reach simply widens the view instead of disappearing.
 */
const makeProjection = (center: LatLng, points: readonly LatLng[], radiusKm: number, size: Size): Projection => {
  const k = squeeze(center.lat)
  const delta = regionDeltaFor(radiusKm)
  let x0 = (center.lng - delta) * k
  let x1 = (center.lng + delta) * k
  let y0 = center.lat - delta
  let y1 = center.lat + delta
  for (const point of points) {
    const x = point.lng * k
    if (x < x0) x0 = x
    if (x > x1) x1 = x
    if (point.lat < y0) y0 = point.lat
    if (point.lat > y1) y1 = point.lat
  }
  const pad = 30
  const width = Math.max(x1 - x0, 1e-9)
  const height = Math.max(y1 - y0, 1e-9)
  const scale = Math.max(
    Math.min((size.width - pad * 2) / width, (size.height - pad * 2) / height),
    1e-9,
  )
  const left = (size.width - width * scale) / 2
  const top = (size.height - height * scale) / 2
  return {
    to: (point) => ({ x: left + (point.lng * k - x0) * scale, y: size.height - top - (point.lat - y0) * scale }),
    pxPerKm: scale / KM_PER_DEGREE,
  }
}

/** The scale bar picks a round distance that is worth drawing at this zoom. */
const scaleBarFor = (pxPerKm: number): { km: number; px: number } => {
  const km = [1, 2, 5, 10, 20].find((n) => n * pxPerKm > 54) ?? 20
  return { km, px: Math.round(km * pxPerKm) }
}

type Props = {
  center: LatLng
  pins: readonly MapPin[]
  radiusKm: number
  selectedId: string | null
  onSelect: (pin: MapPin) => void
}

/**
 * The map view: the reader's reach, a dot for where they are standing, and a square pin per event.
 * Pins are placed by their own coordinates, so the picture is the geography, not a decoration.
 */
export function EventMap({ center, pins, radiusKm, selectedId, onSelect }: Props) {
  const [size, setSize] = useState<Size | null>(null)
  const points = useMemo(() => pins.map((pin) => pin.at), [pins])
  const projection = size ? makeProjection(center, points, radiusKm, size) : null
  const here = projection ? projection.to(center) : null
  const bar = projection ? scaleBarFor(projection.pxPerKm) : null

  return (
    <View style={styles.map} onLayout={(event) => setSize({ width: event.nativeEvent.layout.width, height: event.nativeEvent.layout.height })}>
      <GridPaperLight />
      {size && projection && here ? (
        <>
          <View style={[styles.here, { left: here.x - 9, top: here.y - 9 }]} accessibilityLabel="You are here">
            <View style={styles.hereDot} />
          </View>
          {pins.map((pin) => {
            const at = projection.to(pin.at)
            const many = pin.events.length > 1
            const on = selectedId !== null && pin.events.some((event) => event.id === selectedId)
            const first = pin.events[0]
            return (
              <Pressable
                key={pin.id}
                accessibilityRole="button"
                accessibilityLabel={
                  many
                    ? `${pin.events.length} events here`
                    : `${first?.title ?? 'Event'}, ${first ? formatEventTime(first.startsAt) : ''}`
                }
                onPress={() => onSelect(pin)}
                style={({ pressed }) => [
                  styles.pin,
                  many && styles.pinMany,
                  on && styles.pinOn,
                  pressed && styles.pinPressed,
                  { left: at.x - (many ? 23 : 18), top: at.y - (many ? 23 : 18) },
                ]}
              >
                {many ? (
                  <Text style={styles.pinCount}>{pin.events.length}</Text>
                ) : (
                  <View style={styles.pinDot} />
                )}
              </Pressable>
            )
          })}
          {bar ? (
            <View style={styles.scale} accessibilityLabel={`Scale: ${bar.km} kilometres`}>
              <View style={[styles.scaleBar, { width: bar.px }]} />
              <MonoLabel size={9} tracking={0.1} color={colors.ink2}>
                {`${bar.km} km`}
              </MonoLabel>
            </View>
          ) : null}
        </>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  map: { flex: 1, backgroundColor: colors.paper2, overflow: 'hidden' },
  here: { position: 'absolute', width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
  hereDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.red, borderWidth: 3, borderColor: colors.ink },
  pin: {
    position: 'absolute',
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.red,
    borderWidth: line.strong,
    borderColor: colors.ink,
    borderRadius: 4,
    shadowColor: colors.ink,
    shadowOpacity: 1,
    shadowOffset: { width: 3, height: 3 },
    shadowRadius: 0,
    elevation: 3,
  },
  pinMany: { width: 46, height: 46, backgroundColor: colors.ink },
  pinOn: { backgroundColor: colors.ochre },
  pinPressed: { transform: [{ translateX: 2 }, { translateY: 2 }] },
  pinDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.onRed },
  pinCount: { fontFamily: fonts.display, fontSize: 24, lineHeight: 26, color: colors.ochre },
  scale: { position: 'absolute', left: 14, bottom: 14, gap: 3 },
  scaleBar: { height: 7, borderWidth: 2, borderColor: colors.ink, borderTopWidth: 2, borderBottomWidth: 0 },
})
