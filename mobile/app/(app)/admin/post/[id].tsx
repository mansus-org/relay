import { useLocalSearchParams, useRouter } from 'expo-router'
import { useState } from 'react'
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native'

import { aiReason, aiRest, authorLabel, dateTime } from '../../../../src/domain'
import { ActionBar } from '../../../../src/presentation/components/ActionBar'
import { AiBadge } from '../../../../src/presentation/components/AiBadge'
import { Alert } from '../../../../src/presentation/components/Alert'
import { Avatar } from '../../../../src/presentation/components/Avatar'
import { ConfirmAlert } from '../../../../src/presentation/components/ConfirmAlert'
import { HardShadow } from '../../../../src/presentation/components/HardShadow'
import { MonoLabel } from '../../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../../src/presentation/components/NavBar'
import { Stamp } from '../../../../src/presentation/components/Stamp'
import { colors, fonts, line, shadow } from '../../../../src/presentation/theme'
import { markDecided } from '../../../../src/presentation/use-admin-queue'
import { useAdminPost } from '../../../../src/presentation/use-admin-post'

/**
 * One post, everything the node knows about it, and the two buttons.
 *
 * This is where a decision is actually made, so it is the only place that asks why. Approving
 * needs no explanation from the admin and the node does not ask for one; removing does, and the
 * reason is kept in the trail with the post, which is why the red button will not go through
 * until something is written under it.
 */
export default function AdminPost() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const router = useRouter()
  const { state, decide } = useAdminPost(id)
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState('')

  const back = () => (router.canGoBack() ? router.back() : router.replace('/admin/queue'))
  const post = state.post

  const approve = async () => {
    if (await decide('approve')) {
      markDecided(id)
      back()
    }
  }
  const remove = async () => {
    if (await decide('remove', reason.trim())) {
      markDecided(id)
      setAsking(false)
      back()
    }
  }

  if (!state.loaded) {
    return (
      <View style={styles.screen}>
        <NavBar title="The post" cancelLabel="‹ Back" onCancel={back} />
        <ActivityIndicator color={colors.red} style={styles.status} accessibilityLabel="Loading post" />
      </View>
    )
  }

  if (!post) {
    return (
      <View style={styles.screen}>
        <NavBar title="The post" cancelLabel="‹ Back" onCancel={back} />
        <View style={styles.pad}>
          <Alert message={state.problem ?? 'That post is not on this node.'} />
        </View>
      </View>
    )
  }

  const waiting = post.status === 'pending'
  const why = aiReason(post.ai)
  const rest = aiRest(post.ai)

  return (
    <View style={styles.screen}>
      <NavBar
        title="The post"
        cancelLabel="‹ Back"
        onCancel={back}
        action={
          waiting ? (
            <Stamp label="Waiting" tone="ochre" />
          ) : (
            <Stamp label={post.status === 'approved' ? 'Approved' : 'Removed'} tone={post.status === 'approved' ? 'ink' : 'red'} />
          )
        }
      />
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.pad}>
          {state.problem ? <Alert message={state.problem} /> : null}

          <View style={styles.by}>
            <Avatar name={post.authorId} seed={post.authorId} size={34} />
            <View style={styles.byText}>
              <Text style={styles.name}>{authorLabel(post.authorId)}</Text>
              <Text style={styles.when}>{dateTime(post.createdAt).toUpperCase()}</Text>
            </View>
          </View>

          <HardShadow offset={shadow.regular}>
            <View style={styles.body}>
              <Text selectable style={styles.text}>
                {post.body}
              </Text>
            </View>
          </HardShadow>

          <View style={styles.section}>
            <MonoLabel size={12} tracking={0.16}>
              Why it is here
            </MonoLabel>
            <HardShadow offset={shadow.regular}>
              <View style={styles.ai}>
                {post.ai === null ? (
                  <Text style={styles.aiNone}>
                    No model has looked at this post. Somebody reported it, or it came in while the model was switched
                    off, and it is waiting for you.
                  </Text>
                ) : (
                  <>
                    <View style={styles.aiHead}>
                      <AiBadge ai={post.ai} large />
                      {why ? <Text style={styles.aiReason}>{why}</Text> : null}
                    </View>
                    {rest.map((row) => (
                      <View key={row.key} style={styles.aiRow}>
                        <Text style={styles.aiKey}>{row.key}</Text>
                        <Text style={styles.aiValue}>{row.value}</Text>
                      </View>
                    ))}
                  </>
                )}
              </View>
            </HardShadow>
          </View>

          {waiting ? null : (
            <Text style={styles.decided}>
              This one has already been decided. Another admin can put it back from the moderation log.
            </Text>
          )}
        </View>
      </ScrollView>

      {waiting ? <ActionBar busy={state.busy} onApprove={() => void approve()} onRemove={() => setAsking(true)} /> : null}

      <ConfirmAlert
        visible={asking}
        stamp="Not deletion"
        title={
          <>
            Remove this <Text style={styles.hot}>post</Text>?
          </>
        }
        message="It stops showing on this node and the author is told why. Nothing is erased: another admin can put it back."
        confirm="Remove post"
        reason={{ label: 'Why (the author sees this)', value: reason, onChange: setReason, required: true }}
        busy={state.busy}
        onConfirm={() => void remove()}
        onCancel={() => setAsking(false)}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  status: { marginTop: 40 },
  scroll: { paddingBottom: 24 },
  pad: { padding: 20, gap: 16 },
  by: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  byText: { flex: 1, gap: 2 },
  name: { fontFamily: fonts.bodyMedium, fontSize: 18, color: colors.ink },
  when: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 0.9, color: colors.ink2 },
  body: { backgroundColor: colors.surface, padding: 16 },
  text: { fontFamily: fonts.body, fontSize: 18, lineHeight: 27, color: colors.ink },
  section: { gap: 10 },
  ai: { backgroundColor: colors.surface, padding: 16, gap: 12 },
  aiNone: { fontFamily: fonts.body, fontSize: 16, lineHeight: 23, color: colors.ink2 },
  aiHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  aiReason: { flex: 1, fontFamily: fonts.body, fontSize: 16, lineHeight: 22, color: colors.ink },
  aiRow: { flexDirection: 'row', gap: 10, borderTopWidth: line.regular, borderTopColor: colors.paper2, paddingTop: 10 },
  aiKey: { width: 110, fontFamily: fonts.mono, fontSize: 11, letterSpacing: 0.9, color: colors.ink2 },
  aiValue: { flex: 1, fontFamily: fonts.mono, fontSize: 12, color: colors.ink },
  decided: { fontFamily: fonts.body, fontSize: 15, lineHeight: 22, color: colors.ink2 },
  hot: { color: colors.redText },
})
