import Constants from 'expo-constants'
import { useRouter } from 'expo-router'
import { useState } from 'react'
import { ScrollView, StyleSheet, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { serverHost } from '../../src/domain'
import { useAuth } from '../../src/presentation/auth'
import { Avatar } from '../../src/presentation/components/Avatar'
import { DisplayNameSheet } from '../../src/presentation/components/DisplayNameSheet'
import { GeoSun, GeoWedge } from '../../src/presentation/components/Geo'
import { GlobeIcon, NodesIcon, ShieldIcon } from '../../src/presentation/components/icons'
import { MonoLabel } from '../../src/presentation/components/MonoLabel'
import { NavBar } from '../../src/presentation/components/NavBar'
import { NodeSheet } from '../../src/presentation/components/NodeSheet'
import { IconBox, RowList, SectionLabel, Soon, Value } from '../../src/presentation/components/SettingsRows'
import { SignOutSheet } from '../../src/presentation/components/SignOutSheet'
import { colors } from '../../src/presentation/theme'
import { useSettings } from '../../src/presentation/use-settings'

const version = Constants.expoConfig?.version ?? ''

/**
 * The screen where a person owns their own account: the name they go by, the node that keeps it,
 * and the way out. Two rows are here to say a thing is coming rather than to do it, because a
 * dead control reads worse than an honest one.
 *
 * The Moderation row is not one of those. It is only there when the node says this account runs
 * it, because every screen behind it answers 403 to anybody else.
 */
export default function Settings() {
  const router = useRouter()
  const { bottom } = useSafeAreaInsets()
  const { logout } = useAuth()
  const { state, test, move, rename } = useSettings()
  const [nodeOpen, setNodeOpen] = useState(false)
  const [nameOpen, setNameOpen] = useState(false)
  const [signOutOpen, setSignOutOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  const close = () => (router.canGoBack() ? router.back() : router.replace('/'))
  const profile = state.profile
  const host = state.serverUrl ? serverHost(state.serverUrl) : ''
  const who = profile ? `@${profile.handle}` : state.loaded ? 'not signed in' : 'reading…'

  async function signOut() {
    setSigningOut(true)
    // Dropping the session is the auth layer's call; this screen only asks for it, then gets out
    // of the way, because there is nothing left here to read.
    await logout()
    router.replace('/login')
  }

  return (
    <View style={styles.screen}>
      <NavBar
        title="Settings"
        subtitle={profile ? `${profile.handle} · ${host}` : who}
        cancelLabel="Back"
        onCancel={close}
        decoration={
          <>
            <GeoSun size={96} right={-18} top={-26} />
            <GeoWedge size={150} flip right={-30} top={48} />
          </>
        }
      />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: bottom + 32 }]}>
        <SectionLabel>Profile</SectionLabel>
        <RowList
          rows={[
            {
              key: 'name',
              title: !state.loaded ? 'Reading your account…' : (profile?.displayName ?? 'No name yet'),
              lead: <Avatar name={profile?.displayName ?? '?'} seed={profile?.handle} size={34} />,
              end: profile ? <Value strong>Edit</Value> : undefined,
              onPress: profile ? () => setNameOpen(true) : undefined,
            },
            { key: 'handle', title: 'Username', end: <Value>{profile ? `@${profile.handle}` : '—'}</Value> },
          ]}
        />

        <SectionLabel>Node</SectionLabel>
        <RowList
          rows={[
            {
              key: 'server',
              title: 'Server',
              lead: (
                <IconBox>
                  <GlobeIcon size={20} color={colors.paper} />
                </IconBox>
              ),
              end: <Value strong>{host}</Value>,
              onPress: () => setNodeOpen(true),
            },
            {
              key: 'browse',
              title: 'Browse nodes',
              lead: (
                <IconBox muted>
                  <NodesIcon size={20} color={colors.paper} />
                </IconBox>
              ),
              muted: true,
              end: <Soon />,
            },
          ]}
        />

        {profile?.isAdmin ? (
          <>
            <SectionLabel>Admin</SectionLabel>
            <RowList
              rows={[
                {
                  key: 'moderation',
                  title: 'Moderation',
                  lead: (
                    <IconBox>
                      <ShieldIcon size={20} color={colors.paper} />
                    </IconBox>
                  ),
                  end: <Value strong>Open</Value>,
                  onPress: () => router.push('/admin'),
                },
              ]}
            />
          </>
        ) : null}

        <SectionLabel>Account</SectionLabel>
        <RowList rows={[{ key: 'signout', title: 'Sign out', onPress: () => setSignOutOpen(true), danger: true }]} />

        {version ? (
          <MonoLabel size={11} tracking={0.14} color={colors.ink2} style={styles.footer}>
            {`Relay ${version}`}
          </MonoLabel>
        ) : null}
      </ScrollView>

      <NodeSheet
        visible={nodeOpen}
        currentUrl={state.serverUrl}
        testing={state.testing}
        saving={state.moving}
        error={state.nodeError}
        test={state.test}
        onTest={(url) => void test(url)}
        onSave={(url) => void move(url)}
        onCancel={() => setNodeOpen(false)}
      />
      <DisplayNameSheet
        visible={nameOpen && !!profile}
        currentName={profile?.displayName ?? ''}
        handle={profile?.handle ?? ''}
        busy={state.renaming}
        error={state.nameError}
        onSave={(name) => void rename(name)}
        onCancel={() => setNameOpen(false)}
      />
      <SignOutSheet
        visible={signOutOpen}
        host={host}
        busy={signingOut}
        onConfirm={() => void signOut()}
        onCancel={() => setSignOutOpen(false)}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: 20, paddingTop: 4 },
  footer: { marginTop: 22, textAlign: 'center' },
})
