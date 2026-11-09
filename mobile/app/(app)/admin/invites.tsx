import { useFocusEffect, useRouter } from 'expo-router'
import { useCallback, useState } from 'react'
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'

import { canRevokeInvite, inviteLink } from '../../../src/domain'
import { AdminHeader } from '../../../src/presentation/components/AdminHeader'
import { Alert } from '../../../src/presentation/components/Alert'
import { Button } from '../../../src/presentation/components/Button'
import { FreshInvite } from '../../../src/presentation/components/FreshInvite'
import { GeoRing, GeoSun } from '../../../src/presentation/components/Geo'
import { HardShadow } from '../../../src/presentation/components/HardShadow'
import { InviteRow } from '../../../src/presentation/components/InviteRow'
import { TextField } from '../../../src/presentation/components/TextField'
import { colors, fonts, line, shadow } from '../../../src/presentation/theme'
import { useAdminInvites } from '../../../src/presentation/use-admin-invites'

/**
 * The links that let people into this node.
 *
 * Making one asks for a note and nothing else, because the note is the only record of why the
 * link exists. The token shows in full once, on the card at the top, and after that the list only
 * ever shows its first characters - which is the same deal the backend makes.
 */
export default function AdminInvites() {
  const router = useRouter()
  const { state, refresh, loadMore, issue, revoke } = useAdminInvites()
  const [note, setNote] = useState('')

  useFocusEffect(
    useCallback(() => {
      void refresh()
    }, [refresh]),
  )

  const back = () => (router.canGoBack() ? router.back() : router.replace('/settings'))
  const go = (tab: 'queue' | 'members' | 'invites') => {
    if (tab === 'queue') router.replace('/admin')
    if (tab === 'members') router.replace('/admin/members')
  }

  const open = state.invites.filter(canRevokeInvite).length
  const sub = state.loaded ? `Invites · ${open} open of ${state.invites.length}` : 'Invites'

  const make = async () => {
    if (await issue(note.trim())) setNote('')
  }

  return (
    <View style={styles.screen}>
      <AdminHeader
        sub={sub}
        tab="invites"
        onTab={go}
        onBack={back}
        decoration={
          <>
            <GeoSun size={86} right={-14} top={-22} />
            <GeoRing size={120} right={58} top={44} color={colors.ochre} />
          </>
        }
      />
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={false} tintColor={colors.ink} onRefresh={() => void refresh()} />}
      >
        <HardShadow offset={shadow.regular}>
          <View style={styles.composer}>
            <TextField
              label="Who is this for"
              value={note}
              onChangeText={setNote}
              onSubmitEditing={() => void make()}
              returnKeyType="go"
              accessibilityLabel="Who is this invite for"
            />
            <Button label="New invite" busy={state.issuing} onPress={() => void make()} />
          </View>
        </HardShadow>

        {state.problem ? <Alert message={state.problem} /> : null}
        {state.fresh ? (
          <FreshInvite link={inviteLink(state.fresh, state.serverUrl)} token={state.fresh.token} />
        ) : null}

        {state.loaded && state.invites.length === 0 ? (
          <Text style={styles.empty}>No invite has been made on this node yet.</Text>
        ) : (
          <HardShadow offset={shadow.regular}>
            <View style={styles.box}>
              {state.invites.map((invite, index) => (
                <InviteRow
                  key={invite.id}
                  invite={invite}
                  first={index === 0}
                  revoking={state.revoking === invite.id}
                  onRevoke={() => void revoke(invite.id)}
                />
              ))}
            </View>
          </HardShadow>
        )}
        {state.more ? (
          <View style={styles.more}>
            <Button label="More invites" variant="outline" size="sm" busy={state.loadingMore} onPress={() => void loadMore()} />
          </View>
        ) : null}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { padding: 20, gap: 16, paddingBottom: 40 },
  composer: { padding: 16, gap: 14 },
  empty: { fontFamily: fonts.body, fontSize: 16, lineHeight: 24, color: colors.ink2 },
  box: { borderWidth: line.strong, borderColor: colors.ink, backgroundColor: colors.surface },
  more: { alignSelf: 'flex-start' },
})
