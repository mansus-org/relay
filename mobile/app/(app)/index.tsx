import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useRef } from 'react'
import { ActivityIndicator, FlatList, Linking, Platform, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'

import { FEED_RADIUS_KM } from '../../src/domain'
import { useAuth } from '../../src/presentation/auth'
import { Alert } from '../../src/presentation/components/Alert'
import { Avatar } from '../../src/presentation/components/Avatar'
import { Fab } from '../../src/presentation/components/Fab'
import { FeedPostCard } from '../../src/presentation/components/FeedPostCard'
import { GeoRing, GeoSun, GeoWedge } from '../../src/presentation/components/Geo'
import { LocationOff } from '../../src/presentation/components/LocationOff'
import { MonoLabel } from '../../src/presentation/components/MonoLabel'
import { NewPostsBanner } from '../../src/presentation/components/NewPostsBanner'
import { Ochre, PosterHeader } from '../../src/presentation/components/PosterHeader'
import { PostalCodePrompt } from '../../src/presentation/components/PostalCodePrompt'
import { colors, fonts } from '../../src/presentation/theme'
import { useFeed, usesPostalCode } from '../../src/presentation/use-feed'

export default function Feed() {
  const router = useRouter()
  const { user, logout } = useAuth()
  const { state, enableLocation, setPostalCode, changePlace, backToFeed, refresh, loadMore, showPending } = useFeed()
  const list = useRef<FlatList>(null)

  // Coming back from compose: a post made without location never arrives on the stream.
  const focused = useRef(false)
  useFocusEffect(
    useCallback(() => {
      if (focused.current && state.phase === 'ready') void refresh()
      focused.current = true
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  )

  const denied = state.phase === 'denied'
  const asking = state.phase === 'ask'
  // Neither state has a place to put in the header yet.
  const bare = denied || asking
  const place = state.placeName ?? 'Near you'
  const now = new Date()

  const header = (
    <PosterHeader
      accessibleTitle={bare ? undefined : `${place}, ${FEED_RADIUS_KM} kilometres`}
      title={
        bare ? undefined : (
          <>
            {place}
            {'\n'}
            <Ochre>{`${FEED_RADIUS_KM} km`}</Ochre>
          </>
        )
      }
      meta={bare ? undefined : 'Near you · relay.mansus.org'}
      decoration={
        bare ? undefined : (
          <>
            <GeoSun size={150} right={-36} top={46} />
            <GeoRing size={190} right={-56} top={26} />
            <GeoWedge size={200} right={-30} top={108} />
          </>
        )
      }
      trailing={
        <View style={styles.trailing}>
          {usesPostalCode() && !bare ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Change place" onPress={changePlace} hitSlop={8} style={styles.navLink}>
              <MonoLabel size={12} tracking={0.12} color={colors.paper}>
                Change
              </MonoLabel>
            </Pressable>
          ) : null}
          <Pressable accessibilityRole="button" accessibilityLabel="Communities" onPress={() => router.push('/communities')} hitSlop={8} style={styles.navLink}>
            <MonoLabel size={12} tracking={0.12} color={colors.paper}>
              Communities
            </MonoLabel>
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Sign out" onPress={() => void logout()} hitSlop={8}>
            <Avatar name={user?.name ?? '?'} seed={user?.id} size={30} />
          </Pressable>
        </View>
      }
    />
  )

  if (asking) {
    return (
      <View style={styles.screen}>
        {header}
        <PostalCodePrompt onSubmit={setPostalCode} error={state.placeError} busy={state.checking} onCancel={state.cell ? backToFeed : undefined} />
      </View>
    )
  }

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

  return (
    <View style={styles.screen}>
      {header}
      <View style={styles.body}>
        <FlatList
          ref={list}
          data={state.posts}
          keyExtractor={(post) => post.id}
          renderItem={({ item }) => <FeedPostCard post={item} now={now} />}
          contentContainerStyle={[styles.feed, state.pending.length > 0 && { paddingTop: 66 }]}
          ItemSeparatorComponent={() => <View style={{ height: 16 }} />}
          refreshControl={<RefreshControl refreshing={state.refreshing} onRefresh={() => void refresh()} tintColor={colors.red} colors={[colors.red]} />}
          onEndReached={() => void loadMore()}
          onEndReachedThreshold={0.5}
          ListEmptyComponent={
            state.phase === 'locating' || (!state.failed && state.posts.length === 0 && !state.cell) ? (
              <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel={usesPostalCode() ? 'Loading your place' : 'Finding your location'} />
            ) : state.failed ? (
              <Alert message="Could not load the feed. Pull down to try again." />
            ) : (
              <Text style={styles.empty}>Nothing nearby yet. Be the first to post.</Text>
            )
          }
          ListFooterComponent={state.loadingMore ? <ActivityIndicator color={colors.red} style={styles.status} /> : undefined}
        />
        {state.pending.length > 0 ? (
          <NewPostsBanner
            count={state.pending.length}
            onPress={() => {
              showPending()
              list.current?.scrollToOffset({ offset: 0, animated: true })
            }}
          />
        ) : null}
        <Fab label="New post" onPress={() => router.push('/compose')} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  body: { flex: 1 },
  trailing: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  navLink: { minHeight: 44, justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: colors.red },
  feed: { padding: 16, paddingBottom: 110, flexGrow: 1 },
  status: { marginTop: 32 },
  empty: { marginTop: 32, textAlign: 'center', fontFamily: fonts.body, fontSize: 17, color: colors.ink2 },
})
