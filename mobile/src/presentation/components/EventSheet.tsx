import { Pressable, StyleSheet, Text, View } from 'react-native'

import { formatDistance, formatEventTime, eventDayLabel, type NearbyEvent } from '../../domain'
import { colors, fonts, line, minTap } from '../theme'
import { Button } from './Button'
import { MonoLabel } from './MonoLabel'

type Props = {
  event: NearbyEvent
  now: Date
  onOpen: () => void
  onClose: () => void
}

/** The bar the map puts under a pin you tapped: enough to decide, and one way to the whole event. */
export function EventSheet({ event, now, onOpen, onClose }: Props) {
  const away = formatDistance(event.distanceKm)
  const going = `${event.rsvpCount} ${event.rsvpCount === 1 ? 'person' : 'people'} going`
  return (
    <View style={styles.sheet} accessibilityViewIsModal={false}>
      <View style={styles.head}>
        <View style={styles.headText}>
          <MonoLabel size={11} tracking={0.16} color={colors.ochre}>
            {`${eventDayLabel(event.startsAt, now)} · ${formatEventTime(event.startsAt)}`}
          </MonoLabel>
          <Text style={styles.title} numberOfLines={2}>
            {event.title}
          </Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Close" onPress={onClose} hitSlop={10} style={styles.close}>
          <Text style={styles.cross}>✕</Text>
        </Pressable>
      </View>
      <View style={styles.facts}>
        <MonoLabel size={11} tracking={0.08} color={colors.ink2}>
          {event.venueName ?? 'No venue named'}
        </MonoLabel>
        <MonoLabel size={11} tracking={0.08} color={colors.ink2}>
          {[`${event.hostName} · ${going}`, away].filter(Boolean).join(' · ')}
        </MonoLabel>
      </View>
      <View style={styles.button}>
        <Button label="View event" onPress={onOpen} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    left: 14,
    right: 14,
    bottom: 14,
    padding: 16,
    backgroundColor: colors.paper,
    borderWidth: line.strong,
    borderColor: colors.ink,
    shadowColor: colors.ink,
    shadowOpacity: 1,
    shadowOffset: { width: 6, height: 6 },
    shadowRadius: 0,
    elevation: 6,
  },
  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  headText: { flex: 1, gap: 4 },
  title: { fontFamily: fonts.display, fontSize: 32, lineHeight: 32, color: colors.ink },
  close: { width: minTap, height: minTap, alignItems: 'center', justifyContent: 'center' },
  cross: { fontFamily: fonts.display, fontSize: 22, color: colors.ink },
  facts: { marginTop: 10, gap: 3 },
  button: { alignSelf: 'stretch', marginTop: 16 },
})
