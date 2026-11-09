import { useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native'

import { FEED_RADIUS_KM, POSTAL_CODE_LENGTH } from '../../domain'
import { colors, fonts, line } from '../theme'
import { Button } from './Button'
import { GeoBar, GeoRing, GeoSun, GeoWedge } from './Geo'
import { MonoLabel } from './MonoLabel'
import { TextField } from './TextField'

type Props = {
  onSubmit: (code: string) => void
  /** The reason the last code was refused; the server's own words where it has any. */
  error?: string | null
  busy?: boolean
  /** Offered when there is already a place to go back to, so the prompt is never a dead end. */
  onCancel?: () => void
  /** Offered where the browser can be asked again; it is the reason this screen is usually here. */
  onUseLocation?: () => void
  /** The browser has not answered the retry yet. */
  askingLocation?: boolean
}

/** Empty state for the web feed: nothing knows where this person is, so they name the place to read. */
export function PostalCodePrompt({
  onSubmit,
  error = null,
  busy = false,
  onCancel,
  onUseLocation,
  askingLocation = false,
}: Props) {
  const [code, setCode] = useState('')
  const submit = () => onSubmit(code)
  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.art} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <GeoRing size={176} left={40} top={28} color={colors.ink} />
          <GeoSun size={124} left={66} top={54} />
          <GeoWedge size={250} left={-28} top={132} />
          <GeoBar width={440} left={-60} top={210} />
          <View style={styles.stamp}>
            <MonoLabel size={11} tracking={0.14} color={colors.onRed}>
              Find your place
            </MonoLabel>
          </View>
        </View>
        <View style={styles.kicker}>
          <View style={styles.rule} />
          <MonoLabel size={11.5} tracking={0.2}>
            Your neighbourhood, your feed
          </MonoLabel>
        </View>
        <Text accessibilityRole="header" style={styles.title}>
          {'PICK YOUR\n'}
          <Text style={styles.hot}>POSTAL CODE</Text>
        </Text>
        <Text style={styles.body}>
          Relay asks your browser where you are. When it will not say, a postal code opens the feed on posts from
          people within {FEED_RADIUS_KM} km of you.
        </Text>
        <TextField
          label="Postal code"
          value={code}
          onChangeText={(next) => setCode(next.replace(/\D/g, '').slice(0, POSTAL_CODE_LENGTH))}
          keyboardType="number-pad"
          inputMode="numeric"
          autoComplete="postal-code"
          textContentType="postalCode"
          maxLength={POSTAL_CODE_LENGTH}
          returnKeyType="search"
          onSubmitEditing={submit}
          error={error}
          invalid={!!error}
        />
        <View style={styles.actions}>
          <Button label="Show me nearby" onPress={submit} busy={busy} disabled={code.length !== POSTAL_CODE_LENGTH} />
          {onUseLocation ? (
            <Button label="Use my location" onPress={onUseLocation} variant="ghost" busy={askingLocation} />
          ) : null}
          {onCancel ? <Button label="Back to the feed" onPress={onCancel} variant="ghost" /> : null}
        </View>
        <MonoLabel size={11.5} tracking={0.14} color={colors.ink2} style={styles.note}>
          Relay is in Galicia for now.
        </MonoLabel>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  art: { height: 250, marginTop: 4, marginRight: 22, borderWidth: line.strong, borderColor: colors.ink, overflow: 'visible' },
  stamp: {
    position: 'absolute',
    left: -10,
    top: -14,
    height: 30,
    paddingHorizontal: 10,
    justifyContent: 'center',
    backgroundColor: colors.red,
    borderWidth: 2,
    borderColor: colors.ink,
    transform: [{ rotate: '-4deg' }],
  },
  kicker: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 34 },
  rule: { width: 30, height: 4, backgroundColor: colors.red },
  title: { marginTop: 12, fontFamily: fonts.display, fontSize: 56, lineHeight: 54, color: colors.ink },
  hot: { color: colors.red },
  body: { marginTop: 12, fontFamily: fonts.body, fontSize: 17, lineHeight: 24, color: colors.ink2 },
  actions: { marginTop: 20, gap: 2 },
  note: { marginTop: 22 },
})
