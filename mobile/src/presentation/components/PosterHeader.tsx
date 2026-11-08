import type { ReactNode } from 'react'
import { StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, fonts } from '../theme'
import { GridPaperDark } from './Geo'
import { MonoLabel } from './MonoLabel'

export function Logo() {
  return (
    <View style={styles.logo} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Text style={styles.logoLetter}>R</Text>
      <View style={styles.logoChip} />
    </View>
  )
}

export function Wordmark() {
  return <Text style={styles.wordmark}>RELAY</Text>
}

type Props = {
  /** Title lines; wrap the key word in <Hot> (red on black). */
  title?: ReactNode
  meta?: string
  /** Absolutely positioned geometric shapes (decoration, hidden from accessibility). */
  decoration?: ReactNode
  /** Plain-text title for screen readers. */
  accessibleTitle?: string
  /** Right end of the logo row, e.g. an avatar. */
  trailing?: ReactNode
}

export function Ochre({ children }: { children: string }) {
  return <Text style={styles.ochre}>{children}</Text>
}

export function Hot({ children }: { children: string }) {
  return <Text style={styles.hot}>{children}</Text>
}

/** Black header band with logo row, giant display title, ochre mono meta line and a 6px red stripe. */
export function PosterHeader({ title, meta, decoration, accessibleTitle, trailing }: Props) {
  const { top } = useSafeAreaInsets()
  return (
    <View style={[styles.band, { paddingTop: top + 8 }]}>
      <View pointerEvents="none" style={styles.decoration} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <GridPaperDark />
        {decoration}
      </View>
      <View style={styles.top}>
        <Logo />
        <Wordmark />
        {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
      </View>
      {title ? (
        <Text accessibilityRole="header" accessibilityLabel={accessibleTitle} style={styles.title}>
          {title}
        </Text>
      ) : null}
      {meta ? (
        <MonoLabel size={11} tracking={0.14} color={colors.ochre} style={styles.meta}>
          {meta}
        </MonoLabel>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  band: {
    backgroundColor: colors.ink,
    borderBottomWidth: 6,
    borderBottomColor: colors.red,
    paddingHorizontal: 18,
    paddingBottom: 18,
    overflow: 'hidden',
  },
  decoration: { top: 0, left: 0, right: 0, bottom: 0, position: 'absolute' },
  top: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  logo: {
    width: 32,
    height: 32,
    backgroundColor: colors.red,
    alignItems: 'center',
    justifyContent: 'center',
    transform: [{ rotate: '-6deg' }],
    borderRightWidth: 2,
    borderBottomWidth: 2,
    borderColor: colors.paper,
  },
  logoLetter: { fontFamily: fonts.display, fontSize: 22, lineHeight: 28, color: colors.onRed },
  logoChip: { position: 'absolute', right: -4, top: -4, width: 7, height: 7, backgroundColor: colors.ochre },
  wordmark: { fontFamily: fonts.display, fontSize: 26, letterSpacing: 0.5, color: colors.paper },
  title: { marginTop: 14, fontFamily: fonts.display, fontSize: 50, lineHeight: 44, color: colors.paper, textTransform: 'uppercase' },
  hot: { color: colors.red },
  ochre: { color: colors.ochre },
  trailing: { marginLeft: 'auto' },
  meta: { marginTop: 12 },
})

