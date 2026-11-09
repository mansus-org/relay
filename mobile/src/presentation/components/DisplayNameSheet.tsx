import { useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import { displayNameError, MAX_DISPLAY_NAME_LENGTH } from '../../domain'
import { colors, minTap } from '../theme'
import { Button } from './Button'
import { MonoLabel } from './MonoLabel'
import { Sheet } from './Sheet'
import { TextField } from './TextField'

type Props = {
  visible: boolean
  /** The name on the node now: the field opens on it, so a small edit stays small. */
  currentName: string
  /** The handle is not editable, so the sheet says what does stay. */
  handle: string
  busy: boolean
  error: string | null
  onSave: (displayName: string) => void
  onCancel: () => void
}

/**
 * The name you go by, which is yours to change. The handle underneath it is not offered here: it
 * is what other people's posts lean on, and it does not move.
 */
export function DisplayNameSheet({ visible, currentName, handle, busy, error, onSave, onCancel }: Props) {
  const [name, setName] = useState(currentName)
  // Opening re-reads the name on the node. Adjusted while rendering rather than in an effect, so
  // the field never paints the previous value for a frame first.
  const [wasOpen, setWasOpen] = useState(visible)
  if (visible !== wasOpen) {
    setWasOpen(visible)
    if (visible) setName(currentName)
  }

  const nameError = displayNameError(name)
  const canSave = !nameError && name.trim() !== currentName && !busy

  return (
    <Sheet
      visible={visible}
      onCancel={onCancel}
      title={
        <>
          YOUR <Text style={{ color: colors.red }}>NAME</Text>
        </>
      }
    >
      <TextField
        label="Display name"
        value={name}
        onChangeText={setName}
        error={nameError}
        maxLength={MAX_DISPLAY_NAME_LENGTH}
        autoCapitalize="words"
        autoCorrect={false}
        returnKeyType="done"
        editable={!busy}
        onSubmitEditing={() => canSave && onSave(name.trim())}
      />
      <MonoLabel size={12} tracking={0.06} color={colors.ink2} style={styles.counter}>
        {`${name.trim().length} / ${MAX_DISPLAY_NAME_LENGTH}`}
      </MonoLabel>
      {error ? (
        <MonoLabel size={12} tracking={0.08} color={colors.redText} style={styles.error}>
          {error}
        </MonoLabel>
      ) : null}
      <View style={styles.actions}>
        <Button label={busy ? 'Saving…' : 'Save'} onPress={() => onSave(name.trim())} disabled={!canSave} />
        <Button variant="ghost" label="Cancel" onPress={onCancel} disabled={busy} />
      </View>
      <MonoLabel size={11} tracking={0.1} color={colors.ink2} style={styles.note}>
        {`Your handle stays @${handle}.`}
      </MonoLabel>
    </Sheet>
  )
}

const styles = StyleSheet.create({
  counter: { marginTop: 8, textAlign: 'right' },
  error: { marginTop: 14 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 20, minHeight: minTap },
  note: { marginTop: 14, textAlign: 'center' },
})
