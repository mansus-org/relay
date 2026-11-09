import { useLocalSearchParams, useRouter } from 'expo-router'
import { useState } from 'react'
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'

import { formatDistance, type CommunityError, type NearbyCommunity } from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { Avatar } from '../../../src/presentation/components/Avatar'
import { Button } from '../../../src/presentation/components/Button'
import { EventRow } from '../../../src/presentation/components/EventRow'
import { FeedPostCard } from '../../../src/presentation/components/FeedPostCard'
import { GeoRing, GeoSun, GeoWedge } from '../../../src/presentation/components/Geo'
import { HardShadow } from '../../../src/presentation/components/HardShadow'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../src/presentation/components/NavBar'
import { PseudonymSheet } from '../../../src/presentation/components/PseudonymSheet'
import { colors, fonts, line, minTap } from '../../../src/presentation/theme'
import { useCommunity } from '../../../src/presentation/use-community'

type Tab = 'feed' | 'events' | 'about'

const TAB_LABELS: Record<Tab, string> = { feed: 'Feed', events: 'Events', about: 'About' }

const joinMessages: Partial<Record<CommunityError, string>> = {
  'out-of-range': 'You are outside this community’s area, so you cannot join it.',
  network: 'Could not reach the server. Check your connection and try again.',
}

function Stamp({ children, ochre = false }: { children: string; ochre?: boolean }) {
  return (
    <View style={[styles.stamp, ochre && { backgroundColor: colors.ochre }]}>
      <MonoLabel size={11} tracking={0.1}>
        {children}
      </MonoLabel>
    </View>
  )
}

function Tabs({ tab, onChange }: { tab: Tab; onChange: (tab: Tab) => void }) {
  return (
    <View style={styles.tabs} accessibilityRole="tablist">
      {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
        <Pressable
          key={t}
          accessibilityRole="tab"
          accessibilityLabel={TAB_LABELS[t]}
          accessibilityState={{ selected: tab === t }}
          onPress={() => onChange(t)}
          style={[styles.tab, tab === t && styles.tabOn]}
        >
          <MonoLabel size={14} tracking={0.18} color={tab === t ? colors.paper : colors.ink2}>
            {TAB_LABELS[t]}
          </MonoLabel>
        </Pressable>
      ))}
    </View>
  )
}

function AboutRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.aboutRow} accessible accessibilityLabel={`${label}: ${value}`}>
      <View style={styles.labelRow}>
        <View style={styles.rule} />
        <MonoLabel size={11} tracking={0.16}>
          {label}
        </MonoLabel>
      </View>
      <Text style={styles.aboutValue}>{value}</Text>
    </View>
  )
}

function About({ community }: { community: NearbyCommunity }) {
  const { createdBy, createdAt } = community
  const area =
    community.radiusKm === null ? 'Anywhere' : `${community.radiusKm} km around its centre`
  const made = [createdBy?.name, createdAt ? createdAt.slice(0, 10) : null].filter(Boolean).join(' · ')
  return (
    <View style={styles.about}>
      <HardShadow>
        <Text style={styles.aboutText}>{community.description || 'No description yet.'}</Text>
      </HardShadow>
      <HardShadow>
        <View style={styles.aboutList}>
          <AboutRow label="Area" value={area} />
          {made ? <AboutRow label="Created by" value={made} /> : null}
          <AboutRow label="Pseudonyms" value={community.allowPseudonyms ? 'Allowed' : 'Not allowed'} />
        </View>
      </HardShadow>
    </View>
  )
}

export default function CommunityScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const router = useRouter()
  const [tab, setTab] = useState<Tab>('feed')
  const { state, canJoin, promptOpen, joining, joinError, requestJoin, join, cancelPrompt, refresh, loadMore, loadMoreEvents, react } = useCommunity(id)
  const { community } = state
  const now = new Date()

  const close = () => (router.canGoBack() ? router.back() : router.replace('/communities'))
  const nav = (
    <NavBar
      title="Community"
      cancelLabel="‹ Back"
      onCancel={close}
      decoration={<GeoSun size={110} right={-26} top={30} />}
    />
  )

  if (!state.loaded) {
    return (
      <View style={styles.screen}>
        {nav}
        <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading community" />
      </View>
    )
  }
  if (!community) {
    return (
      <View style={styles.screen}>
        {nav}
        <View style={styles.pad}>
          <Alert message="Could not load this community. Go back and try again." />
        </View>
      </View>
    )
  }

  const words = community.name.trim().split(/\s+/)
  const last = words.length > 1 ? words.pop() : null
  const distance = formatDistance(community.distanceKm)
  const off = !community.isMember && !community.inRange

  const hero = (
    <View style={styles.hero}>
      <View pointerEvents="none" style={styles.heroDecoration} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <GeoSun size={120} right={-30} top={-24} />
        <GeoRing size={150} right={-44} top={-44} color={colors.ink} />
        <GeoWedge size={170} right={-24} top={50} />
      </View>
      <View style={styles.top}>
        <Avatar name={community.name} seed={community.id} size={72} />
        <Text accessibilityRole="header" style={styles.name}>
          {words.join(' ').toUpperCase()}
          {last ? <Text style={{ color: colors.red }}>{` ${last.toUpperCase()}`}</Text> : null}
        </Text>
      </View>
      {community.description ? (
        <Text style={styles.description} numberOfLines={3}>
          {community.description}
        </Text>
      ) : null}
      <View style={styles.stats}>
        <Stamp>{`${community.memberCount} members`}</Stamp>
        {distance ? <Stamp ochre>{distance}</Stamp> : null}
        {off ? <Stamp>Out of range</Stamp> : null}
      </View>
      {community.isMember ? (
        <Stamp ochre>Joined</Stamp>
      ) : (
        <View>
          <Button label={joining ? 'Joining…' : 'Join community'} onPress={() => void requestJoin()} busy={joining} disabled={!canJoin} />
          {off ? <Text style={styles.note}>You are outside this community’s area, so you cannot join it.</Text> : null}
          {state.noLocation ? <Text style={styles.note}>Turn on location to join a community.</Text> : null}
          {joinError && !promptOpen ? <Alert message={joinMessages[joinError] ?? 'Could not join. Try again.'} /> : null}
        </View>
      )}
      <Tabs tab={tab} onChange={setTab} />
    </View>
  )

  const pullToRefresh = (
    <RefreshControl refreshing={state.refreshing} onRefresh={() => void refresh()} tintColor={colors.red} colors={[colors.red]} />
  )

  return (
    <View style={styles.screen}>
      {nav}
      {tab === 'events' ? (
        <FlatList
          data={state.events}
          keyExtractor={(event) => event.id}
          renderItem={({ item }) => (
            <EventRow event={item} now={now} onPress={() => router.push(`/events/${item.id}`)} />
          )}
          ListHeaderComponent={hero}
          ItemSeparatorComponent={() => <View style={{ height: 16 }} />}
          contentContainerStyle={styles.list}
          refreshControl={pullToRefresh}
          onEndReached={() => void loadMoreEvents()}
          onEndReachedThreshold={0.5}
          ListEmptyComponent={
            !state.eventsLoaded ? (
              <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading events" />
            ) : state.eventsFailed ? (
              <Alert message="Could not load these events. Pull down to try again." />
            ) : (
              <Text style={styles.empty}>Nothing filed under {community.name} yet.</Text>
            )
          }
          ListFooterComponent={state.eventsLoadingMore ? <ActivityIndicator color={colors.red} style={styles.status} /> : undefined}
        />
      ) : (
      <FlatList
        key={tab}
        data={tab === 'feed' && community.isMember ? state.posts : []}
        keyExtractor={(post) => post.id}
        renderItem={({ item }) => (
          <FeedPostCard
            now={now}
            post={item}
            onPress={() => router.push(`/post/${item.id}`)}
            onToggleReaction={(emoji) => void react(item, emoji)}
          />
        )}
        ListHeaderComponent={hero}
        ItemSeparatorComponent={() => <View style={{ height: 16 }} />}
        contentContainerStyle={styles.list}
        refreshControl={pullToRefresh}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.5}
        ListEmptyComponent={
          tab === 'about' ? (
            <About community={community} />
          ) : !community.isMember ? (
            <Text style={styles.empty}>Join this community to see its posts.</Text>
          ) : !state.feedLoaded ? (
            <ActivityIndicator color={colors.red} style={styles.status} />
          ) : state.feedFailed ? (
            <Alert message="Could not load the feed. Pull down to try again." />
          ) : (
            <Text style={styles.empty}>No posts yet. Be the first to post here.</Text>
          )
        }
        ListFooterComponent={state.loadingMore ? <ActivityIndicator color={colors.red} style={styles.status} /> : undefined}
      />
      )}
      <PseudonymSheet
        visible={promptOpen}
        communityName={community.name}
        busy={joining}
        error={joinError ? (joinMessages[joinError] ?? 'Could not join. Try again.') : null}
        onJoin={(pseudonym) => void join(pseudonym)}
        onCancel={cancelPrompt}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  pad: { padding: 16 },
  list: { paddingBottom: 40, flexGrow: 1 },
  hero: { padding: 16, gap: 12, marginBottom: 20, overflow: 'hidden', borderBottomWidth: line.strong, borderBottomColor: colors.ink, backgroundColor: colors.paper },
  heroDecoration: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  top: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  name: { flex: 1, maxWidth: 230, fontFamily: fonts.display, fontSize: 36, lineHeight: 36, color: colors.ink },
  description: { fontFamily: fonts.body, fontSize: 18, lineHeight: 24, color: colors.ink },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  stamp: { height: 28, paddingHorizontal: 10, justifyContent: 'center', backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink, transform: [{ rotate: '-1.5deg' }], alignSelf: 'flex-start' },
  note: { marginTop: 10, fontFamily: fonts.bodyMedium, fontSize: 15, color: colors.ink2 },
  tabs: { flexDirection: 'row', borderWidth: line.strong, borderColor: colors.ink, backgroundColor: colors.surface },
  tab: { flex: 1, minHeight: minTap + 6, alignItems: 'center', justifyContent: 'center' },
  tabOn: { backgroundColor: colors.ink },
  status: { marginTop: 32 },
  empty: { marginTop: 12, paddingHorizontal: 16, textAlign: 'center', fontFamily: fonts.body, fontSize: 17, color: colors.ink2 },
  about: { paddingHorizontal: 16, gap: 18 },
  aboutText: { padding: 16, fontFamily: fonts.body, fontSize: 18, lineHeight: 25, color: colors.ink, backgroundColor: colors.surface, borderWidth: line.regular, borderColor: colors.ink },
  aboutList: { backgroundColor: colors.surface, borderWidth: line.regular, borderBottomWidth: 0, borderColor: colors.ink },
  aboutRow: { minHeight: 64, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: line.regular, borderBottomColor: colors.ink },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rule: { width: 14, height: 3, backgroundColor: colors.red },
  aboutValue: { marginTop: 3, fontFamily: fonts.bodyMedium, fontSize: 19, color: colors.ink },
})
