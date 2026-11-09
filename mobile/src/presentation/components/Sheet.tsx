import type { ReactNode } from 'react'
import { KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, fonts, line } from '../theme'
import { GeoRing, GeoSun } from './Geo'

type Props = {
  visible: boolean
  /** The heading, with its hot word already marked up by the caller. */
  title: ReactNode
  onCancel: () => void
  children: ReactNode
}

/**
 * The sheet every settings choice opens on: a red crown over a paper card, a grab bar, and a
 * title. It closes on the scrim and on Android's back, and nothing else.
 */
export function Sheet({ visible, title, onCancel, children }: Props) {
  const { bottom } = useSafeAreaInsets()
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Pressable accessibilityLabel="Close" accessibilityRole="button" style={styles.scrim} onPress={onCancel} />
        <View>
          <View style={styles.crown} />
          <View style={[styles.sheet, { paddingBottom: bottom + 24 }]}>
            <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              <GeoSun size={90} right={-24} top={-36} color={colors.ochre} />
              <GeoRing size={100} right={40} top={-50} color={colors.ink} />
            </View>
            <View style={styles.grab} />
            <Text accessibilityRole="header" style={styles.title}>
              {title}
            </Text>
            {children}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  scrim: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(20,18,16,.55)' },
  crown: { height: 8, backgroundColor: colors.red },
  sheet: { backgroundColor: colors.surface, borderTopWidth: line.strong, borderTopColor: colors.ink, paddingHorizontal: 20, paddingTop: 10, overflow: 'hidden' },
  grab: { width: 48, height: 6, backgroundColor: colors.ink, alignSelf: 'center', marginBottom: 16 },
  title: { fontFamily: fonts.display, fontSize: 40, lineHeight: 36, textTransform: 'uppercase', color: colors.ink },
})
