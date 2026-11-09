import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useState } from 'react'
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'

import { AdminHeader } from '../../../src/presentation/components/AdminHeader'
import { Alert } from '../../../src/presentation/components/Alert'
import { Button } from '../../../src/presentation/components/Button'
import { ConfirmAlert } from '../../../src/presentation/components/ConfirmAlert'
import { GeoRing, GeoWedge } from '../../../src/presentation/components/Geo'
import { HardShadow } from '../../../src/presentation/components/HardShadow'
import { MemberRow } from '../../../src/presentation/components/MemberRow'
import { MemberSheet } from '../../../src/presentation/components/MemberSheet'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { colors, fonts, line, shadow } from '../../../src/presentation/theme'
import { useAdminMembers } from '../../../src/presentation/use-admin-members'

/**
 * The accounts on this node.
 *
 * One row each, and one thing to do to one: switch it off. Nothing is deleted here, so nothing on
 * the screen says deleted - a switched-off account keeps its row, its name in the trail, and its
 * posts until somebody puts it back.
 */
export default function AdminMembers() {
  const router = useRouter()
  const { state, refresh, loadMore, openMember, closeMember, remove } = useAdminMembers()
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState('')
  const [pulling, setPulling] = useState(false)

  useFocusEffect(
    useCallback(() => {
      void refresh()
    }, [refresh]),
  )

  const pull = async () => {
    setPulling(true)
    try {
      await refresh()
    } finally {
      setPulling(false)
    }
  }

  const back = () => (router.canGoBack() ? router.back() : router.replace('/settings'))
  const go = (tab: 'queue' | 'members' | 'invites') => {
    if (tab === 'queue') router.replace('/admin/queue')
    if (tab === 'invites') router.replace('/admin/invites')
  }

  const member = state.open?.member ?? null
  const accounts = `${state.members.length} ${state.members.length === 1 ? 'account' : 'accounts'}`
  const sub = state.loaded ? `Members · ${accounts}` : 'Members'

  const switchOff = async () => {
    if (member === null) return
    if (await remove(member.id, reason.trim())) {
      setAsking(false)
      setReason('')
    }
  }

  /** Backing out of the question, which also throws away what was written under it. */
  const dropAsking = () => {
    setAsking(false)
    setReason('')
  }

  return (
    <View style={styles.screen}>
      <AdminHeader
        sub={sub}
        tab="members"
        onTab={go}
        onBack={back}
        decoration={
          <>
            <GeoWedge size={140} flip right={-26} top={30} />
            <GeoRing size={90} right={70} top={-18} color={colors.ochre} />
          </>
        }
      />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={pulling} tintColor={colors.ink} onRefresh={() => void pull()} />}
      >
        {state.problem ? <Alert message={state.problem} /> : null}
        {state.notice ? (
          <MonoLabel size={12} tracking={0.14} color={colors.ink2} style={styles.notice}>
            {state.notice.toUpperCase()}
          </MonoLabel>
        ) : null}
        {state.loaded && state.members.length === 0 ? (
          <Text style={styles.empty}>No account has signed up on this node yet.</Text>
        ) : (
          <HardShadow offset={shadow.regular}>
            <View style={styles.box}>
              {state.members.map((entry, index) => (
                <MemberRow key={entry.id} member={entry} first={index === 0} onPress={() => void openMember(entry.id)} />
              ))}
            </View>
          </HardShadow>
        )}
        {state.more ? (
          <View style={styles.more}>
            <Button label="More accounts" variant="outline" size="sm" busy={state.loadingMore} onPress={() => void loadMore()} />
          </View>
        ) : null}
      </ScrollView>

      <MemberSheet
        detail={state.open}
        myHandle={state.myHandle ?? ''}
        removing={state.removing}
        onClose={closeMember}
        onRemove={() => setAsking(true)}
      />
      <ConfirmAlert
        visible={asking && member !== null}
        stamp="Not deletion"
        title={
          <>
            Switch off <Text style={styles.hot}>{member?.handle ?? ''}</Text>?
          </>
        }
        message="They cannot sign in any more, and the sessions they have running are thrown out. Nothing is erased: their posts stay up, and another admin can put them back."
        confirm="Switch off"
        reason={{ label: 'Why (it goes in the trail)', value: reason, onChange: setReason, required: true }}
        error={state.problem}
        busy={state.removing}
        onConfirm={() => void switchOff()}
        onCancel={dropAsking}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { padding: 20, gap: 14, paddingBottom: 40 },
  notice: { marginTop: 4 },
  empty: { fontFamily: fonts.body, fontSize: 16, lineHeight: 24, color: colors.ink2 },
  box: { borderWidth: line.strong, borderColor: colors.ink, backgroundColor: colors.surface },
  more: { alignSelf: 'flex-start' },
  hot: { color: colors.redText },
})
