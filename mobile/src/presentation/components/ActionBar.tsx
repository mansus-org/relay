import { Pressable, StyleSheet, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, line, minTap } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

type Props = {
  /** One decision at a time: both buttons go quiet while the node is answering. */
  busy: boolean
  onApprove: () => void
  onRemove: () => void
}

/**
 * The two things an admin can do to a post, pinned where the thumb already is.
 *
 * Approve is the ochre one and remove is the red one, in that order, on every post, so the hand
 * learns it. Neither one is final on its own: removing asks first, because that is the one that
 * takes something away.
 */
export function ActionBar({ busy, onApprove, onRemove }: Props) {
  const { bottom } = useSafeAreaInsets()
  return (
    <View style={[styles.bar, { paddingBottom: bottom + 14 }]}>
      <View style={styles.actions}>
        <HardShadow offset={3} style={styles.half}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Approve this post"
            accessibilityState={{ busy }}
            disabled={busy}
            onPress={onApprove}
            style={({ pressed }) => [styles.button, styles.approve, (busy || pressed) && styles.quiet]}
          >
            <MonoLabel size={14} tracking={0.16} color={colors.ink}>
              APPROVE
            </MonoLabel>
          </Pressable>
        </HardShadow>
        <HardShadow offset={3} style={styles.half}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Remove this post"
            accessibilityState={{ busy }}
            disabled={busy}
            onPress={onRemove}
            style={({ pressed }) => [styles.button, styles.remove, (busy || pressed) && styles.quiet]}
          >
            <MonoLabel size={14} tracking={0.16} color={colors.onRed}>
              REMOVE
            </MonoLabel>
          </Pressable>
        </HardShadow>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.paper,
    borderTopWidth: line.strong,
    borderTopColor: colors.ink,
    paddingHorizontal: 16,
    paddingTop: 14,
  },
  actions: { flexDirection: 'row', gap: 12 },
  half: { flex: 1 },
  button: {
    height: 50,
    minHeight: minTap,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: line.strong,
    borderColor: colors.ink,
  },
  approve: { backgroundColor: colors.ochre },
  remove: { backgroundColor: colors.red },
  quiet: { backgroundColor: colors.paper2, borderColor: colors.ink2 },
})
