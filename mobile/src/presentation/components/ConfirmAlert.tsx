import type { ReactNode } from 'react'
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line, minTap } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'
import { Stamp } from './Stamp'
import { TextField } from './TextField'

type Props = {
  visible: boolean
  /** The red band's line: what the node will do, in three words. */
  stamp: string
  /** The question, with the hot word already marked up by the caller. */
  title: ReactNode
  message: string
  /** The verb on the button that does it. */
  confirm: string
  /**
   * Ask why, before it will let the button through. The node wants a reason for a removal and
   * keeps whatever it is given in the trail, so when the caller needs one it says so here and the
   * red button stays quiet until something is written.
   */
  reason?: { label: string; value: string; onChange: (text: string) => void; required?: boolean }
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * The last question before something is taken away.
 *
 * It closes on the scrim and on Android's back, both of which mean "no". The red button is the
 * only one that changes anything, and it goes quiet while the node is answering.
 */
export function ConfirmAlert({
  visible,
  stamp,
  title,
  message,
  confirm,
  reason,
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const waitingForReason = reason !== undefined && reason.required === true && reason.value.trim() === ''
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.root}>
        <Pressable accessibilityLabel="Cancel" accessibilityRole="button" style={styles.scrim} onPress={onCancel} />
        <HardShadow offset={8} color={colors.red}>
          <View style={styles.card}>
            <View style={styles.head}>
              <View style={styles.stamp} pointerEvents="none">
                <Stamp label={stamp} tone="red" />
              </View>
            </View>
            <View style={styles.body}>
              <Text style={styles.title}>{title}</Text>
              <Text style={styles.message}>{message}</Text>
              {reason ? (
                <TextField
                  label={reason.label}
                  value={reason.value}
                  onChangeText={reason.onChange}
                  multiline
                  accessibilityLabel={reason.label}
                />
              ) : null}
            </View>
            <View style={styles.actions}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={confirm}
                accessibilityState={{ busy }}
                disabled={busy || waitingForReason}
                onPress={onConfirm}
                style={({ pressed }) => [styles.action, styles.destructive, (busy || waitingForReason || pressed) && styles.busy]}
              >
                <MonoLabel size={13} tracking={0.16} color={colors.onRed}>
                  {confirm.toUpperCase()}
                </MonoLabel>
              </Pressable>
              <Pressable accessibilityRole="button" accessibilityLabel="Cancel" onPress={onCancel} style={({ pressed }) => [styles.action, styles.plain, pressed && styles.pressed]}>
                <MonoLabel size={13} tracking={0.16} color={colors.ink}>
                  CANCEL
                </MonoLabel>
              </Pressable>
            </View>
          </View>
        </HardShadow>
      </View>
    </Modal>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  scrim: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(20,18,16,.55)' },
  card: { width: 310, maxWidth: '100%', backgroundColor: colors.surface, borderWidth: line.strong, borderColor: colors.ink },
  head: { height: 46, backgroundColor: colors.red, borderBottomWidth: line.strong, borderColor: colors.ink },
  stamp: { position: 'absolute', left: 12, top: 8 },
  body: { padding: 18 },
  title: { fontFamily: fonts.display, fontSize: 38, lineHeight: 35, textTransform: 'uppercase', color: colors.ink },
  message: { fontFamily: fonts.body, fontSize: 16.5, lineHeight: 23, color: colors.ink2, marginTop: 10 },
  actions: { gap: 10, paddingHorizontal: 18, paddingBottom: 18 },
  action: {
    height: 48,
    minHeight: minTap,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: line.strong,
    paddingHorizontal: 10,
  },
  destructive: { backgroundColor: colors.red, borderColor: colors.ink },
  plain: { backgroundColor: colors.surface, borderColor: colors.ink },
  pressed: { backgroundColor: colors.paper2 },
  busy: { backgroundColor: colors.paper2, borderColor: colors.ink2 },
})
