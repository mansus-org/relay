import { useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import { serverHost, serverUrlError, type NodeTest } from '../../domain'
import { colors, minTap } from '../theme'
import { Button } from './Button'
import { MonoLabel } from './MonoLabel'
import { NodeTestResult } from './NodeTestResult'
import { Sheet } from './Sheet'
import { TextField } from './TextField'

type Props = {
  visible: boolean
  /** The address on the row: the field opens on it, so it reads back what is stored. */
  currentUrl: string
  testing: boolean
  saving: boolean
  /** Why the move was refused, when it was. */
  error: string | null
  /** The last test, whatever URL it was run against; only its own host counts. */
  test: NodeTest | null
  onTest: (url: string) => void
  onSave: (url: string) => void
  onCancel: () => void
}

/**
 * The address of the node you live on, and the only way to move it. Nothing here changes the node
 * until Save: Test asks, and Save only becomes possible once the answer was yes.
 */
export function NodeSheet({ visible, currentUrl, testing, saving, error, test, onTest, onSave, onCancel }: Props) {
  const [url, setUrl] = useState(currentUrl)
  // Opening re-reads the stored address. Adjusted while rendering rather than in an effect, so
  // the field never paints the previous value for a frame first.
  const [wasOpen, setWasOpen] = useState(visible)
  if (visible !== wasOpen) {
    setWasOpen(visible)
    if (visible) setUrl(currentUrl)
  }

  const busy = testing || saving
  const urlError = serverUrlError(url)
  // A test only speaks for the address it was run against, so typing again retires the answer.
  const tested = test && !urlError && serverHost(url) === test.host ? test : null
  const canSave = !urlError && !!tested?.reachable && serverHost(url) !== serverHost(currentUrl) && !busy

  return (
    <Sheet
      visible={visible}
      onCancel={onCancel}
      title={
        <>
          CHANGE <Text style={{ color: colors.red }}>SERVER</Text>
        </>
      }
    >
      <TextField
        label="Server URL"
        value={url}
        onChangeText={setUrl}
        error={urlError}
        autoCapitalize="none"
        autoCorrect={false}
        spellCheck={false}
        keyboardType="url"
        returnKeyType="done"
        editable={!busy}
        onSubmitEditing={() => !urlError && !busy && onTest(url)}
      />
      {tested ? <NodeTestResult test={tested} /> : null}
      {error ? (
        <MonoLabel size={12} tracking={0.08} color={colors.redText} style={styles.error}>
          {error}
        </MonoLabel>
      ) : null}
      <View style={styles.actions}>
        <Button variant="outline" label={testing ? 'Testing…' : 'Test connection'} onPress={() => onTest(url)} disabled={!!urlError || busy} />
        <Button label={saving ? 'Moving…' : 'Save'} onPress={() => onSave(url)} disabled={!canSave} />
      </View>
      <MonoLabel size={11} tracking={0.1} color={colors.ink2} style={styles.note}>
        Switching servers signs you out.
      </MonoLabel>
    </Sheet>
  )
}

const styles = StyleSheet.create({
  error: { marginTop: 14 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 20, minHeight: minTap },
  note: { marginTop: 14, textAlign: 'center' },
})
