import { Link, useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, FlatList, Linking, Platform, RefreshControl, StyleSheet, Text, View } from 'react-native'

import {
  EVENTS_RADIUS_KM,
  clusterEvents,
  groupEvents,
  type EventGroup,
  type NearbyEvent,
} from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { EventMap } from '../../../src/presentation/components/EventMap'
import { EventRow } from '../../../src/presentation/components/EventRow'
import { EventSheet } from '../../../src/presentation/components/EventSheet'
import { Fab } from '../../../src/presentation/components/Fab'
import { GeoRing, GeoSun, GeoWedge } from '../../../src/presentation/components/Geo'
import { LocationOff } from '../../../src/presentation/components/LocationOff'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { Ochre, PosterHeader } from '../../../src/presentation/components/PosterHeader'
import { Segmented } from '../../../src/presentation/components/Segmented'
import { colors, fonts } from '../../../src/presentation/theme'
import { useEvents } from '../../../src/presentation/use-events'

type View_ = 'list' | 'map'
type Item = { kind: 'group'; key: string; group: EventGroup } | { kind: 'event'; key: string; event: NearbyEvent }

const asItems = (groups: readonly EventGroup[]): Item[] =>
  groups.flatMap((group) => [{ kind: 'group' as const, key: `g-${group.key}`, group }, ...group.events.map((event) => ({ kind: 'event' as const, key: event.id, event }))])

export default function Events() {
  const router = useRouter()
  const { state, enableLocation, refresh, loadMore } = useEvents()
  const [view, setView] = useState<View_>('list')
  const [selected, setSelected] = useState<string | null>(null)
  const now = new Date()
  const groups = groupEvents(state.events, now)
  const items = asItems(groups)
  const pins = clusterEvents(state.events)
  const chosen = state.events.find((event) => event.id === selected) ?? null

  // Coming back from an event, the head counts have to be the ones you just changed.
  const focused = useRef(false)
  useFocusEffect(
    useCallback(() => {
      if (focused.current && state.phase === 'ready') void refresh()
      focused.current = true
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  )

  const denied = state.phase === 'denied'
  const place = state.placeName ?? 'Near you'

  const header = (
    <PosterHeader
      accessibleTitle={denied ? undefined : `Events near ${place}, within ${EVENTS_RADIUS_KM} kilometres`}
      title={
        denied ? undefined : (
          <>
            EVENTS
            {'\n'}
            <Ochre>{`${EVENTS_RADIUS_KM} km`}</Ochre>
          </>
        )
      }
      meta={denied ? undefined : `Near ${place} · relay.mansus.org`}
      decoration={
        denied ? undefined : (
          <>
            <GeoSun size={150} right={-36} top={46} />
            <GeoRing size={190} right={-56} top={26} />
            <GeoWedge size={200} right={-30} top={108} />
          </>
        )
      }
      trailing={
        <View style={styles.trailing}>
          <Link href="/" accessibilityRole="link" style={styles.back}>
            ‹ FEED
          </Link>
        </View>
      }
    />
  )

  if (denied) {
    return (
      <View style={styles.screen}>
        {header}
        <LocationOff
          onEnable={() => (state.canAskAgain || Platform.OS === 'web' ? void enableLocation() : void Linking.openSettings())}
          onOpenSettings={Platform.OS === 'web' ? undefined : () => void Linking.openSettings()}
        />
      </View>
    )
  }

  const control = (
    <View style={styles.control}>
      <Segmented
        label="View events as"
        value={view}
        onChange={setView}
        options={[
          { value: 'list', label: 'List' },
          { value: 'map', label: 'Map' },
        ]}
      />
    </View>
  )

  const empty =
    state.phase === 'locating' ? (
      <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading events" />
    ) : state.failed ? (
      <Alert message={state.error ?? 'Could not load the events nearby. Pull down to try again.'} />
    ) : (
      <View style={styles.emptyBlock}>
        <Text style={styles.empty}>Nothing on within {EVENTS_RADIUS_KM} km from today.</Text>
        <MonoLabel size={11} tracking={0.14} color={colors.ink2}>
          Make one with the plus
        </MonoLabel>
      </View>
    )

  return (
    <View style={styles.screen}>
      {header}
      {control}
      <View style={styles.body}>
        {view === 'list' ? (
          <FlatList
            data={items}
            keyExtractor={(item) => item.key}
            renderItem={({ item }) =>
              item.kind === 'group' ? (
                <View style={styles.groupHead} accessibilityLabel={`${item.group.label}, ${item.group.dateLabel}`}>
                  <Text style={styles.groupLabel}>{item.group.label}</Text>
                  <Text style={styles.groupDate}>{item.group.dateLabel}</Text>
                </View>
              ) : (
                <EventRow event={item.event} now={now} onPress={() => router.push(`/events/${item.event.id}`)} />
              )
            }
            ItemSeparatorComponent={() => <View style={styles.gap} />}
            contentContainerStyle={styles.list}
            refreshControl={
              <RefreshControl refreshing={state.refreshing} onRefresh={() => void refresh()} tintColor={colors.red} colors={[colors.red]} />
            }
            onEndReached={() => void loadMore()}
            onEndReachedThreshold={0.4}
            ListEmptyComponent={empty}
            ListFooterComponent={state.loadingMore ? <ActivityIndicator color={colors.red} style={styles.status} /> : undefined}
          />
        ) : (
          <>
            {state.center ? (
              <EventMap
                center={state.center}
                pins={pins}
                radiusKm={EVENTS_RADIUS_KM}
                selectedId={selected}
                onSelect={(pin) => setSelected(pin.events[0]?.id ?? null)}
              />
            ) : (
              <View style={styles.mapEmpty}>{empty}</View>
            )}
            {state.center && pins.length > 0 ? (
              <View style={styles.tag} pointerEvents="none">
                <Text style={styles.tagCount}>{state.events.length}</Text>
                <MonoLabel size={9} tracking={0.14} color={colors.ink2}>
                  events nearby
                </MonoLabel>
              </View>
            ) : null}
            {chosen ? (
              <EventSheet
                event={chosen}
                now={now}
                onClose={() => setSelected(null)}
                onOpen={() => router.push(`/events/${chosen.id}`)}
              />
            ) : null}
          </>
        )}
        <Fab label="New event" onPress={() => router.push('/events/new')} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  body: { flex: 1 },
  trailing: { flexDirection: 'row', alignItems: 'center' },
  back: { fontFamily: fonts.monoBold, fontSize: 12, letterSpacing: 1.4, color: colors.paper, minHeight: 44, justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: colors.red },
  control: { paddingHorizontal: 14, paddingTop: 14 },
  list: { padding: 14, paddingBottom: 110, flexGrow: 1, gap: 12 },
  gap: { height: 12 },
  groupHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 10, marginTop: 6 },
  groupLabel: { fontFamily: fonts.display, fontSize: 26, lineHeight: 28, color: colors.ink },
  groupDate: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.1, color: colors.ink2 },
  status: { marginTop: 32 },
  emptyBlock: { marginTop: 32, alignItems: 'center', gap: 10 },
  empty: { textAlign: 'center', fontFamily: fonts.body, fontSize: 17, color: colors.ink2 },
  mapEmpty: { flex: 1 },
  tag: { position: 'absolute', left: 14, top: 14, minWidth: 74, alignItems: 'center', paddingVertical: 7, paddingHorizontal: 10, backgroundColor: colors.paper, borderWidth: 2, borderColor: colors.ink },
  tagCount: { fontFamily: fonts.display, fontSize: 26, lineHeight: 28, color: colors.ink },
})
