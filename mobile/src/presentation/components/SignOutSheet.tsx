import { StyleSheet, Text, View } from 'react-native'

import { colors, fonts, minTap } from '../theme'
import { Button } from './Button'
import { Sheet } from './Sheet'

type Props = {
  visible: boolean
  /** The node the key being thrown away was minted by. */
  host: string
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Signing out, said before it happens: the key leaves this phone, the account stays where it is,
 * and coming back means signing in again on the same node.
 */
export function SignOutSheet({ visible, host, busy, onConfirm, onCancel }: Props) {
  return (
    <Sheet
      visible={visible}
      onCancel={onCancel}
      title={
        <>
          SIGN <Text style={{ color: colors.red }}>OUT</Text>
        </>
      }
    >
      <Text style={styles.body}>
        This phone keeps a key for <Text style={{ fontFamily: fonts.bodyMedium }}>{host}</Text>. Signing out throws it away. Your
        account stays on the server, and you sign back in with the same handle and password.
      </Text>
      <View style={styles.actions}>
        <Button label={busy ? 'Signing out…' : 'Sign out'} onPress={onConfirm} disabled={busy} />
        <Button variant="ghost" label="Stay signed in" onPress={onCancel} disabled={busy} />
      </View>
    </Sheet>
  )
}

const styles = StyleSheet.create({
  body: { marginTop: 18, fontFamily: fonts.body, fontSize: 16, lineHeight: 23, color: colors.ink },
  actions: { flexDirection: 'row', gap: 12, marginTop: 20, minHeight: minTap },
})
