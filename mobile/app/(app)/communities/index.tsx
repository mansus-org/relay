import { useRouter } from 'expo-router'
import { ActivityIndicator, FlatList, Linking, Platform, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'

import { Alert } from '../../../src/presentation/components/Alert'
import { CommunityRow } from '../../../src/presentation/components/CommunityRow'
import { Fab } from '../../../src/presentation/components/Fab'
import { GeoRing, GeoSun, GeoWedge } from '../../../src/presentation/components/Geo'
import { LocationOff } from '../../../src/presentation/components/LocationOff'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { PosterHeader } from '../../../src/presentation/components/PosterHeader'
import { colors, fonts, minTap } from '../../../src/presentation/theme'
import { useNearbyCommunities } from '../../../src/presentation/use-nearby-communities'

export default function Communities() {
  const router = useRouter()
  const { state, enableLocation, refresh } = useNearbyCommunities()
  const denied = state.phase === 'denied'
  const inRange = state.communities.filter((c) => c.inRange).length

  const header = (
    <PosterHeader
      accessibleTitle={denied ? undefined : 'Communities'}
      title={denied ? undefined : <>COMMUNITIES</>}
      meta={denied ? undefined : state.placeName ? `Near ${state.placeName}` : 'Near you'}
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
        <Pressable accessibilityRole="button" accessibilityLabel="Back to the feed" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} style={styles.back}>
          <MonoLabel size={12} tracking={0.12} color={colors.paper}>
            ‹ Feed
          </MonoLabel>
        </Pressable>
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

  return (
    <View style={styles.screen}>
      {header}
      <View style={styles.body}>
        <FlatList
          data={state.communities}
          keyExtractor={(c) => c.id}
          renderItem={({ item }) => <CommunityRow community={item} onPress={() => router.push(`/communities/${item.id}`)} />}
          contentContainerStyle={styles.list}
          ItemSeparatorComponent={() => <View style={{ height: 18 }} />}
          refreshControl={<RefreshControl refreshing={state.refreshing} onRefresh={() => void refresh()} tintColor={colors.red} colors={[colors.red]} />}
          ListHeaderComponent={
            state.communities.length > 0 ? (
              <MonoLabel size={11} tracking={0.14} color={colors.ink2} style={styles.count}>
                {`${inRange} in range · ${state.communities.length} nearby`}
              </MonoLabel>
            ) : undefined
          }
          ListEmptyComponent={
            state.phase === 'locating' ? (
              <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Finding your location" />
            ) : state.failed ? (
              <Alert message="Could not load communities. Pull down to try again." />
            ) : (
              <Text style={styles.empty}>No communities nearby yet. Start one.</Text>
            )
          }
        />
        <Fab label="New community" onPress={() => router.push('/communities/new')} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  body: { flex: 1 },
  list: { padding: 16, paddingTop: 24, paddingBottom: 110, flexGrow: 1 },
  count: { marginBottom: 18 },
  back: { minHeight: minTap, justifyContent: 'center', paddingLeft: 8 },
  status: { marginTop: 32 },
  empty: { marginTop: 32, textAlign: 'center', fontFamily: fonts.body, fontSize: 17, color: colors.ink2 },
})
