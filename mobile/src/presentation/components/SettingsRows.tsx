import type { ReactNode } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'

import { colors, fonts, line, minTap } from '../theme'
import { MonoLabel } from './MonoLabel'
import { ChevronIcon } from './icons'

export type Row = {
  readonly key: string
  readonly title: string
  /** Whatever sits before the title: an ink box around an icon, an avatar. */
  readonly lead?: ReactNode
  /** What sits before the chevron: the host you are on, a `@handle`, a `soon` badge. */
  readonly end?: ReactNode
  /** Omit it for a row that only shows something: no chevron, no press. */
  readonly onPress?: () => void
  /** The one red block on the screen: it ends the session. */
  readonly danger?: boolean
  /** Here, but not working yet: grey, no chevron, no press. */
  readonly muted?: boolean
}

/** The small caps heading above a list, with the red rule in front of it. */
export function SectionLabel({ children }: { children: string }) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionRule} />
      <MonoLabel size={11} tracking={0.18}>
        {children}
      </MonoLabel>
    </View>
  )
}

/** The ink square a line icon sits in, so every row starts at the same width. */
export function IconBox({ children, muted = false }: { children: ReactNode; muted?: boolean }) {
  return <View style={[styles.iconBox, muted && styles.iconBoxMuted]}>{children}</View>
}

/** A boxed list of rows: ink border, a hair of ink between the rows, no gaps. */
export function RowList({ rows }: { rows: readonly Row[] }) {
  return (
    <View style={styles.list}>
      {rows.map(({ key, ...row }, index) => (
        <RowView key={key} {...row} first={index === 0} />
      ))}
    </View>
  )
}

function RowView({ title, lead, end, onPress, danger = false, muted = false, first = false }: Row & { first?: boolean }) {
  const body = (
    <View style={[styles.row, first && styles.firstRow, danger && styles.danger]}>
      {lead}
      <Text style={[styles.title, danger && styles.titleDanger, muted && styles.titleMuted]} numberOfLines={1}>
        {title}
      </Text>
      {end}
      {onPress && !muted ? <ChevronIcon size={16} color={danger ? colors.onRed : colors.ink} /> : null}
    </View>
  )
  if (!onPress || muted) return body
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress}>
      {body}
    </Pressable>
  )
}

/** The `soon` badge: a row that says the feature is coming, and does nothing. */
export function Soon() {
  return (
    <MonoLabel size={11} tracking={0.14} color={colors.ink} style={styles.soon}>
      soon
    </MonoLabel>
  )
}

/** The value on the right of a row: the host, the handle, the word Edit. */
export function Value({ children, strong = false }: { children: string; strong?: boolean }) {
  return (
    <MonoLabel size={12} tracking={0.06} color={strong ? colors.ink : colors.ink2} numberOfLines={1} style={styles.value}>
      {children}
    </MonoLabel>
  )
}

const styles = StyleSheet.create({
  section: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 20, paddingBottom: 10 },
  sectionRule: { width: 22, height: 3, backgroundColor: colors.red },
  list: { borderWidth: line.regular, borderColor: colors.ink, backgroundColor: colors.surface },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: Math.max(58, minTap),
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderTopWidth: 1.5,
    borderTopColor: colors.ink,
  },
  firstRow: { borderTopWidth: 0 },
  danger: { backgroundColor: colors.red, minHeight: Math.max(52, minTap) },
  iconBox: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.ink,
    flexShrink: 0,
  },
  iconBoxMuted: { backgroundColor: colors.ink2 },
  title: { flex: 1, flexShrink: 1, fontFamily: fonts.bodyMedium, fontSize: 17, lineHeight: 21, color: colors.ink },
  titleDanger: { fontFamily: fonts.monoBold, fontSize: 14, letterSpacing: 2.2, textTransform: 'uppercase', color: colors.onRed },
  titleMuted: { color: colors.ink2 },
  value: { flexShrink: 1 },
  soon: { height: 26, paddingHorizontal: 8, borderWidth: 2, borderColor: colors.ink, backgroundColor: colors.ochre, textAlign: 'center' },
})
