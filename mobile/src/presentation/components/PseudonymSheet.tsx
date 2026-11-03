import { useState } from 'react'
import { KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { MAX_PSEUDONYM_LENGTH } from '../../domain'
import { colors, fonts, minTap } from '../theme'
import { Alert } from './Alert'
import { Button } from './Button'
import { GeoSun, GeoWedge } from './Geo'
import { MonoLabel } from './MonoLabel'
import { TextField } from './TextField'

type Props = {
  visible: boolean
  communityName: string
  busy: boolean
  error: string | null
  /** Called with the typed pseudonym; `undefined` joins under the member's own name. */
  onJoin: (pseudonym?: string) => void
  onCancel: () => void
}

/** Bottom sheet asking for a pseudonym before joining a community that allows them. */
export function PseudonymSheet({ visible, communityName, busy, error, onJoin, onCancel }: Props) {
  const { bottom } = useSafeAreaInsets()
  const [pseudonym, setPseudonym] = useState('')
  const typed = pseudonym.trim()
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Pressable accessibilityLabel="Close" accessibilityRole="button" style={styles.scrim} onPress={onCancel} />
        <View style={[styles.sheet, { paddingBottom: bottom + 24 }]}>
          <View style={styles.head}>
            <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              <GeoSun size={110} right={-24} top={-30} />
              <GeoWedge size={130} right={10} top={60} />
            </View>
            <MonoLabel size={11} tracking={0.16} color={colors.paper} numberOfLines={1}>
              {`Join ${communityName}`}
            </MonoLabel>
            <Text accessibilityRole="header" style={styles.title}>
              PICK A <Text style={{ color: colors.ochre }}>PSEUDONYM</Text>
            </Text>
          </View>
          <View style={styles.body}>
            <Text style={styles.hint}>Members see this instead of your name.</Text>
            {error ? <Alert message={error} /> : null}
            <TextField
              label="Pseudonym"
              value={pseudonym}
              onChangeText={setPseudonym}
              maxLength={MAX_PSEUDONYM_LENGTH}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="join"
              onSubmitEditing={() => typed && onJoin(typed)}
            />
            <View style={styles.actions}>
              <Button label={busy ? 'Joining…' : 'Join'} onPress={() => onJoin(typed)} busy={busy} disabled={!typed} />
              <Button variant="ghost" label="Join with my own name" onPress={() => onJoin(undefined)} disabled={busy} />
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  scrim: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(20,18,16,.6)' },
  sheet: { backgroundColor: colors.surface, borderTopWidth: 6, borderTopColor: colors.red },
  head: { backgroundColor: colors.ink, paddingHorizontal: 20, paddingVertical: 16, overflow: 'hidden' },
  title: { marginTop: 8, fontFamily: fonts.display, fontSize: 34, lineHeight: 36, color: colors.paper },
  body: { paddingHorizontal: 20, paddingTop: 14 },
  hint: { fontFamily: fonts.body, fontSize: 18, color: colors.ink },
  actions: { marginTop: 22, gap: 6, minHeight: minTap },
})
