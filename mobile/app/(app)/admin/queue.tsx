import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback } from 'react'
import { ActivityIndicator, FlatList, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'

import { AdminHeader } from '../../../src/presentation/components/AdminHeader'
import { Alert } from '../../../src/presentation/components/Alert'
import { Button } from '../../../src/presentation/components/Button'
import { GeoRing, GeoSun } from '../../../src/presentation/components/Geo'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { QueueRow } from '../../../src/presentation/components/QueueRow'
import { colors, fonts } from '../../../src/presentation/theme'
import { useAdminQueue } from '../../../src/presentation/use-admin-queue'

/**
 * The queue: posts on this node that nobody has decided about yet.
 *
 * Reading the queue is the whole job, so the list is the screen - no counts to read first, no
 * filters to guess. A row opens the post on its own page, where the decision is actually made;
 * coming back re-reads the list, because a post decided elsewhere should not still be here.
 */
export default function AdminQueue() {
  const router = useRouter()
  const { state, refresh } = useAdminQueue()

  useFocusEffect(
    useCallback(() => {
      void refresh()
    }, [refresh]),
  )

  const back = () => (router.canGoBack() ? router.back() : router.replace('/settings'))
  const go = (tab: 'queue' | 'members' | 'invites') => {
    if (tab === 'members') router.replace('/admin/members')
    if (tab === 'invites') router.replace('/admin/invites')
  }

  const waiting = `${state.posts.length} ${state.posts.length === 1 ? 'post' : 'posts'}`
  const sub = state.loaded ? `Review queue · ${waiting}` : 'Review queue'

  const retry = () => void refresh()
  const pull = <RefreshControl refreshing={state.refreshing} tintColor={colors.ink} onRefresh={retry} />

  return (
    <View style={styles.screen}>
      <AdminHeader
        sub={sub}
        tab="queue"
        onTab={go}
        onBack={back}
        decoration={
          <>
            <GeoSun size={92} right={-16} top={-24} />
            <GeoRing size={130} right={54} top={40} color={colors.ochre} />
          </>
        }
      />
      {!state.loaded && state.posts.length === 0 ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : state.posts.length === 0 ? (
        <ScrollView contentContainerStyle={styles.empty} refreshControl={pull}>
          {state.problem ? (
            <>
              <MonoLabel size={12} tracking={0.16}>
                Could not read the queue
              </MonoLabel>
              <Alert message={state.problem} />
              <Text style={styles.emptyText}>
                Nothing here has been decided - the node would not say what is waiting. Pull, or try again, and the
                posts will come back.
              </Text>
              <Button label="Try again" busy={state.refreshing} onPress={retry} />
            </>
          ) : (
            <>
              <MonoLabel size={12} tracking={0.16}>
                Nothing waiting
              </MonoLabel>
              <Text style={styles.emptyText}>
                Every post on this node has been decided. New ones show up here as the model flags them, or as soon
                as anyone reports them.
              </Text>
            </>
          )}
        </ScrollView>
      ) : (
        <FlatList
          data={state.posts}
          keyExtractor={(post) => post.id}
          renderItem={({ item: post }) => (
            <QueueRow post={post} onPress={() => router.push(`/admin/post/${post.id}`)} />
          )}
          contentContainerStyle={styles.list}
          ListHeaderComponent={state.problem ? <Alert message={state.problem} /> : undefined}
          refreshControl={pull}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  list: { padding: 20, gap: 14, paddingBottom: 40 },
  empty: { padding: 24, gap: 14 },
  emptyText: { fontFamily: fonts.body, fontSize: 16, lineHeight: 24, color: colors.ink2 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
})
