import { ScrollView, StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line } from '../theme'
import { Button } from './Button'
import { GeoBar, GeoRing, GeoSun, GeoWedge } from './Geo'
import { MonoLabel } from './MonoLabel'

type Props = {
  onEnable: () => void
  /** Shown when the OS no longer prompts and the user has to flip the switch in Settings. */
  onOpenSettings?: () => void
  busy?: boolean
}

/** Empty state for the feed when location permission is missing. */
export function LocationOff({ onEnable, onOpenSettings, busy = false }: Props) {
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.art} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <GeoRing size={176} left={40} top={28} color={colors.ink} />
        <GeoSun size={124} left={66} top={54} />
        <GeoWedge size={250} left={-28} top={132} />
        <GeoBar width={440} left={-60} top={210} />
        <View style={styles.stamp}>
          <MonoLabel size={11} tracking={0.14} color={colors.onRed}>
            Location off
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
        {"SEE WHAT'S\n"}
        <Text style={styles.hot}>NEAR YOU</Text>
      </Text>
      <Text style={styles.body}>Turn on location and Relay shows posts from people within 10 km of you.</Text>
      <View style={styles.actions}>
        <Button label="Enable location" onPress={onEnable} busy={busy} />
        {onOpenSettings ? (
          <Button label="Open Settings" onPress={onOpenSettings} variant="ghost" />
        ) : null}
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 40 },
  art: { height: 250, marginTop: 4, marginRight: 22, borderWidth: line.strong, borderColor: colors.ink, overflow: 'visible' },
  stamp: { position: 'absolute', left: -10, top: -14, height: 30, paddingHorizontal: 10, justifyContent: 'center', backgroundColor: colors.red, borderWidth: 2, borderColor: colors.ink, transform: [{ rotate: '-4deg' }] },
  kicker: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 34 },
  rule: { width: 30, height: 4, backgroundColor: colors.red },
  title: { marginTop: 12, fontFamily: fonts.display, fontSize: 56, lineHeight: 54, color: colors.ink },
  hot: { color: colors.red },
  body: { marginTop: 12, fontFamily: fonts.body, fontSize: 17, lineHeight: 24, color: colors.ink2 },
  actions: { marginTop: 20, gap: 2 },
})
