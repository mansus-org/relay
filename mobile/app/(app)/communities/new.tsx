import { useRouter } from 'expo-router'
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { MAX_COMMUNITY_NAME_LENGTH, MAX_RADIUS_KM, MIN_RADIUS_KM } from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { Button } from '../../../src/presentation/components/Button'
import { GeoSun, GeoWedge } from '../../../src/presentation/components/Geo'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../src/presentation/components/NavBar'
import { Slider } from '../../../src/presentation/components/Slider'
import { TextField } from '../../../src/presentation/components/TextField'
import { colors, fonts, line, minTap } from '../../../src/presentation/theme'
import { useCreateCommunity } from '../../../src/presentation/use-create-community'

const messages: Record<string, string> = {
  'empty-name': 'Give the community a name.',
  'name-too-long': `Names are limited to ${MAX_COMMUNITY_NAME_LENGTH} characters.`,
  'bad-radius': `The radius must be ${MIN_RADIUS_KM}–${MAX_RADIUS_KM} km.`,
  'no-location': 'Your location is not available. Turn off “Use my current location” or allow location access.',
  network: 'Could not reach the server. Check your connection and try again.',
}

function SwitchRow({ label, sub, value, onChange }: { label: string; sub?: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <View style={styles.switchRow}>
      <View style={styles.rowMain}>
        <Text style={styles.rowTitle}>{label}</Text>
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
      <Switch
        accessibilityLabel={label}
        value={value}
        onValueChange={onChange}
        trackColor={{ true: colors.red, false: colors.paper2 }}
        thumbColor={colors.surface}
        ios_backgroundColor={colors.paper2}
      />
    </View>
  )
}

export default function NewCommunity() {
  const router = useRouter()
  const { bottom } = useSafeAreaInsets()
  const form = useCreateCommunity()

  const close = () => (router.canGoBack() ? router.back() : router.replace('/communities'))
  async function create() {
    const id = await form.submit()
    if (id) router.replace(`/communities/${id}`)
  }

  const where = form.locationBusy ? 'Finding your location…' : form.locationOn ? (form.placeName ?? 'Current location') : 'Location not available'

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <NavBar
        title="New community"
        subtitle="Start a group"
        onCancel={close}
        action={<Button size="sm" label={form.busy ? 'Creating…' : 'Create'} onPress={() => void create()} busy={form.busy} disabled={form.name.trim() === ''} />}
        decoration={
          <>
            <GeoSun size={120} right={-30} top={52} />
            <GeoWedge size={130} flip right={22} top={92} />
          </>
        }
      />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: bottom + 32 }]} keyboardShouldPersistTaps="handled">
        {form.error ? <Alert message={messages[form.error] ?? 'Could not create the community. Try again.'} /> : null}
        <TextField label="Name" value={form.name} onChangeText={form.setName} maxLength={MAX_COMMUNITY_NAME_LENGTH} autoCapitalize="words" />
        <TextField label="Description" value={form.description} onChangeText={form.setDescription} multiline textAlignVertical="top" />
        <View style={styles.group}>
          <SwitchRow label="Use my current location" sub={where} value={form.useLocation} onChange={form.setUseLocation} />
          <View style={styles.radiusHead}>
            <View style={styles.labelRow}>
              <View style={styles.rule} />
              <MonoLabel>Radius</MonoLabel>
            </View>
            <View style={styles.radiusTag}>
              <MonoLabel size={12} tracking={0.1} color={colors.onRed}>{`${form.radiusKm} km`}</MonoLabel>
            </View>
          </View>
          <Slider
            value={form.radiusKm}
            min={MIN_RADIUS_KM}
            max={MAX_RADIUS_KM}
            onChange={form.setRadiusKm}
            accessibilityLabel="Radius"
            valueText={`${form.radiusKm} kilometres`}
          />
          <View style={styles.ends}>
            <MonoLabel size={11} tracking={0.1} color={colors.ink2}>{`${MIN_RADIUS_KM} km`}</MonoLabel>
            <MonoLabel size={11} tracking={0.1} color={colors.ink2}>{`${MAX_RADIUS_KM} km`}</MonoLabel>
          </View>
        </View>
        <View style={styles.group}>
          <SwitchRow label="Allow pseudonyms" value={form.allowPseudonyms} onChange={form.setAllowPseudonyms} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: 20, paddingTop: 4 },
  group: { marginTop: 22, paddingTop: 6, borderTopWidth: 1.5, borderTopColor: colors.ink },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8 },
  rowMain: { flex: 1 },
  rowTitle: { fontFamily: fonts.bodyMedium, fontSize: 21, color: colors.ink },
  rowSub: { marginTop: 2, fontFamily: fonts.body, fontSize: 16, color: colors.ink2 },
  radiusHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10, minHeight: minTap },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rule: { width: 14, height: 3, backgroundColor: colors.red },
  radiusTag: { paddingHorizontal: 10, height: 30, justifyContent: 'center', backgroundColor: colors.red, borderWidth: line.regular, borderColor: colors.ink, transform: [{ rotate: '-2deg' }] },
  ends: { flexDirection: 'row', justifyContent: 'space-between' },
})
