import { useMemo, useState } from 'react'
import { PanResponder, Pressable, StyleSheet, Text, View } from 'react-native'

import { inviteStateLabel, inviteSubline, tokenPreview, type Invite } from '../../domain'
import { colors, fonts, line } from '../theme'
import { Pill } from './Pill'

/** How far a row slides, and how wide the panel underneath it is. */
const REVEAL = 92

const TONES = { open: 'ochre', used: 'ink', revoked: 'spent' } as const

type Props = {
  invite: Invite
  /** Only an open invite can be taken back, and only one at a time is being taken back. */
  revoking: boolean
  /** The first row in the box wears no rule above itself. */
  first?: boolean
  onRevoke: () => void
}

/**
 * One invite, and the swipe that takes it back.
 *
 * Dragging left uncovers the red panel; letting go past halfway leaves it open, and tapping the
 * row again shuts it without revoking anything. A long press opens it too, for anybody who cannot
 * drag. Only an open invite answers a swipe at all: a used one is spent and a revoked one is
 * already back, and offering a button that the node would refuse is a lie about what is possible.
 */
export function InviteRow({ invite, revoking, first = false, onRevoke }: Props) {
  const open = invite.state === 'open'
  const [dx, setDx] = useState(0)
  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, g) => open && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy) * 1.5,
        onPanResponderMove: (_, g) => setDx(Math.max(-REVEAL, Math.min(0, g.dx))),
        onPanResponderRelease: (_, g) => setDx(g.dx < -REVEAL / 2 ? -REVEAL : 0),
        onPanResponderTerminate: () => setDx(0),
        onPanResponderTerminationRequest: () => false,
      }),
    [open],
  )
  const revealed = dx <= -REVEAL / 2
  return (
    <View style={[styles.swipe, first && styles.first]}>
      {open ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Revoke invite ${tokenPreview(invite.token)}`}
          accessibilityState={{ busy: revoking }}
          disabled={revoking}
          onPress={onRevoke}
          style={[styles.revoke, revoking && styles.revokeBusy]}
        >
          <Text style={styles.revokeText}>{revoking ? '...' : 'REVOKE'}</Text>
        </Pressable>
      ) : null}
      <Pressable
        {...pan.panHandlers}
        accessibilityRole={open ? 'button' : undefined}
        accessibilityLabel={`Invite ${tokenPreview(invite.token)}, ${inviteStateLabel(invite)}, ${inviteSubline(invite)}`}
        accessibilityHint={open && !revealed ? 'Swipe left to revoke, or press and hold' : undefined}
        onPress={() => setDx(revealed ? 0 : dx)}
        onLongPress={() => open && setDx(-REVEAL)}
        style={({ pressed }) => [styles.row, pressed && styles.pressed, { transform: [{ translateX: dx }] }]}
      >
        <View style={styles.main}>
          <Text style={styles.title}>{tokenPreview(invite.token)}</Text>
          <Text style={styles.sub}>{inviteSubline(invite)}</Text>
        </View>
        <Pill label={inviteStateLabel(invite)} tone={TONES[invite.state]} />
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  swipe: {
    position: 'relative',
    overflow: 'hidden',
    borderTopWidth: 1.5,
    borderTopColor: colors.ink,
  },
  first: { borderTopWidth: 0 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 58,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: colors.surface,
  },
  pressed: { backgroundColor: colors.paper2 },
  main: { flex: 1, gap: 2 },
  title: { fontFamily: fonts.mono, fontSize: 14, letterSpacing: 0.4, color: colors.ink },
  sub: { fontFamily: fonts.body, fontSize: 14, color: colors.ink2 },
  revoke: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    width: REVEAL,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.red,
    borderLeftWidth: line.regular,
    borderLeftColor: colors.ink,
  },
  revokeBusy: { backgroundColor: colors.redDeep },
  revokeText: { fontFamily: fonts.monoBold, fontSize: 12.5, letterSpacing: 1.2, color: colors.onRed },
})
