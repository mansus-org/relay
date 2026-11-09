import { Pressable, StyleSheet, Text, View } from 'react-native'

import { formatDistance, formatEventTime, eventDayLabel, type NearbyEvent } from '../../domain'
import { colors, fonts, line } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

type Props = {
  event: NearbyEvent
  now: Date
  onPress: () => void
}

/** One event in the list: its own time in a black block, then what, where, who and how many. */
export function EventRow({ event, now, onPress }: Props) {
  const today = eventDayLabel(event.startsAt, now) === 'Today'
  const when = `${formatEventTime(event.startsAt)} ${eventDayLabel(event.startsAt, now)}`
  const where = event.venueName ?? (event.distanceKm === null ? 'No place given' : 'No venue named')
  const away = formatDistance(event.distanceKm)
  const going = `${event.rsvpCount} ${event.rsvpCount === 1 ? 'person' : 'people'} going`

  return (
    <HardShadow>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${event.title}, ${when}, ${where}${away ? `, ${away}` : ''}, ${going}, hosted by ${event.hostName}`}
        onPress={onPress}
        style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      >
        <View style={[styles.time, today && styles.timeToday]}>
          <Text style={[styles.hour, today && { color: colors.onRed }]}>{formatEventTime(event.startsAt)}</Text>
          <MonoLabel size={9} tracking={0.1} color={today ? colors.onRed : colors.ochre}>
            {eventDayLabel(event.startsAt, now)}
          </MonoLabel>
        </View>
        <View style={styles.main}>
          <Text style={styles.title} numberOfLines={2}>
            {event.title}
          </Text>
          <View style={styles.meta}>
            <View style={styles.pin} />
            <MonoLabel size={10} tracking={0.08} color={colors.ink2} numberOfLines={1} style={styles.metaText}>
              {where}
            </MonoLabel>
            {away ? (
              <MonoLabel size={10} tracking={0.08} color={colors.ink2}>
                {away}
              </MonoLabel>
            ) : null}
          </View>
          <MonoLabel size={10} tracking={0.08} color={colors.ink2}>
            {`by ${event.hostName}`}
          </MonoLabel>
        </View>
        <View style={styles.going}>
          <Text style={styles.count}>{event.rsvpCount}</Text>
          <MonoLabel size={9} tracking={0.1} color={colors.ink2}>
            going
          </MonoLabel>
        </View>
      </Pressable>
    </HardShadow>
  )
}

const styles = StyleSheet.create({
  row: {
    minHeight: 78,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 10,
    backgroundColor: colors.surface,
    borderWidth: line.regular,
    borderColor: colors.ink,
  },
  pressed: { backgroundColor: colors.paper },
  time: { width: 58, height: 58, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.ink, gap: 1 },
  timeToday: { backgroundColor: colors.red },
  hour: { fontFamily: fonts.display, fontSize: 21, lineHeight: 22, color: colors.paper },
  main: { flex: 1, gap: 3 },
  title: { fontFamily: fonts.display, fontSize: 21, lineHeight: 23, color: colors.ink },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metaText: { flexShrink: 1 },
  pin: { width: 8, height: 8, borderRadius: 4, borderWidth: 2, borderColor: colors.red },
  going: { width: 46, alignItems: 'center' },
  count: { fontFamily: fonts.display, fontSize: 26, lineHeight: 28, color: colors.ink },
})
