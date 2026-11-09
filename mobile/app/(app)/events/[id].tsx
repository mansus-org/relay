import { useLocalSearchParams, useRouter } from 'expo-router'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'

import { formatDistance, formatEventDate, formatEventTime } from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { Avatar } from '../../../src/presentation/components/Avatar'
import { Button } from '../../../src/presentation/components/Button'
import { GeoRing, GeoSun, GeoWedge } from '../../../src/presentation/components/Geo'
import { HardShadow } from '../../../src/presentation/components/HardShadow'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../src/presentation/components/NavBar'
import { colors, fonts, line } from '../../../src/presentation/theme'
import { useEventDetail } from '../../../src/presentation/use-events'

/** A fact about the event: a rule, a label, and the answer in the poster's own type. */
function Fact({ label, value, big = false }: { label: string; value: string; big?: boolean }) {
  return (
    <View style={styles.fact} accessibilityLabel={`${label}: ${value}`}>
      <View style={styles.labelRow}>
        <View style={styles.rule} />
        <MonoLabel size={11} tracking={0.16}>
          {label}
        </MonoLabel>
      </View>
      <Text style={[styles.factValue, big && styles.factBig]}>{value}</Text>
    </View>
  )
}

export default function EventDetail() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const router = useRouter()
  const { state, toggle } = useEventDetail(id)

  if (!state.loaded) {
    return (
      <View style={styles.screen}>
        <NavBar title="Event" cancelLabel="‹ Back" onCancel={() => router.back()} />
        <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading event" />
      </View>
    )
  }

  const event = state.event
  if (!event) {
    return (
      <View style={styles.screen}>
        <NavBar title="Event" cancelLabel="‹ Back" onCancel={() => router.back()} />
        <View style={styles.pad}>
          <Alert message={state.error ?? 'That event is gone.'} />
        </View>
      </View>
    )
  }

  const range = event.endsAt ? `${formatEventTime(event.startsAt)} – ${formatEventTime(event.endsAt)}` : formatEventTime(event.startsAt)
  const away = formatDistance(event.distanceKm)
  const going = `${state.count} ${state.count === 1 ? 'person' : 'people'} going`
  const filed = event.communityName ?? 'A community'

  return (
    <View style={styles.screen}>
      <NavBar title="Event" cancelLabel="‹ Back" onCancel={() => router.back()} decoration={<GeoSun size={110} right={-26} top={30} />} />
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.hero}>
          <View pointerEvents="none" style={styles.heroDecoration} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <GeoSun size={130} right={-30} top={30} />
            <GeoRing size={170} right={-50} top={10} />
            <GeoWedge size={180} right={-20} top={92} />
          </View>
          <MonoLabel size={11} tracking={0.16} color={colors.ochre}>
            {formatEventDate(event.startsAt)}
          </MonoLabel>
          <Text accessibilityRole="header" style={styles.title}>
            {event.title.toUpperCase()}
          </Text>
          <View style={styles.byline}>
            <Avatar name={event.hostName} seed={event.hostId} size={30} />
            <MonoLabel size={11} tracking={0.1} color={colors.ink2}>
              {`Hosted by ${event.hostName}`}
            </MonoLabel>
          </View>
        </View>

        <View style={styles.pad}>
          <HardShadow>
            <View style={styles.card}>
              <Fact label="When" value={`${range}`} big />
              <Fact label="Where" value={event.venueName ?? (away ? 'No venue named' : 'No place given')} />
              {away ? <Fact label="Distance" value={away} /> : null}
              {event.communityId ? (
                <Pressable
                  style={styles.fact}
                  accessibilityRole="button"
                  accessibilityLabel={`Filed under ${filed}. Open the community.`}
                  onPress={() => router.push(`/communities/${event.communityId}`)}
                >
                  <View style={styles.labelRow}>
                    <View style={styles.rule} />
                    <MonoLabel size={11} tracking={0.16}>
                      Filed under
                    </MonoLabel>
                  </View>
                  <View style={styles.factRow}>
                    <Text style={styles.factValue}>{filed}</Text>
                    <MonoLabel size={11} tracking={0.1} color={colors.redText}>
                      Open ›
                    </MonoLabel>
                  </View>
                </Pressable>
              ) : null}
              <Fact label="Going" value={going} />
            </View>
          </HardShadow>

          {event.details ? (
            <HardShadow>
              <Text style={styles.details}>{event.details}</Text>
            </HardShadow>
          ) : null}

          <View style={styles.rsvp}>
            <View style={styles.rsvpButton}>
              <Button
                label={state.busy ? '…' : state.going ? "You're going — tap to undo" : "I'm going"}
                busy={state.busy}
                onPress={() => void toggle()}
              />
            </View>
            <Text style={styles.rsvpNote}>
              {state.going ? 'Tap again if you cannot make it after all.' : 'Only the host can change an event.'}
            </Text>
          </View>
          {state.error ? <Alert message={state.error} /> : null}
        </View>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  pad: { padding: 16, gap: 18 },
  scroll: { paddingBottom: 40 },
  status: { marginTop: 32 },
  hero: { padding: 16, gap: 10, marginBottom: 4, overflow: 'hidden', borderBottomWidth: line.strong, borderBottomColor: colors.ink, backgroundColor: colors.paper },
  heroDecoration: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  title: { fontFamily: fonts.display, fontSize: 44, lineHeight: 42, color: colors.ink },
  byline: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  card: { backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink },
  fact: { minHeight: 62, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: line.regular, borderBottomColor: colors.ink },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rule: { width: 14, height: 3, backgroundColor: colors.red },
  factValue: { marginTop: 3, fontFamily: fonts.bodyMedium, fontSize: 19, color: colors.ink },
  factRow: { marginTop: 3, flexDirection: 'row', alignItems: 'baseline', gap: 10 },
  factBig: { fontFamily: fonts.display, fontSize: 34, lineHeight: 36, color: colors.ink },
  details: { padding: 16, fontFamily: fonts.body, fontSize: 18, lineHeight: 26, color: colors.ink, backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink },
  rsvp: { marginTop: 4 },
  rsvpButton: { alignSelf: 'stretch' },
  rsvpNote: { marginTop: 10, fontFamily: fonts.body, fontSize: 15, color: colors.ink2 },
})
