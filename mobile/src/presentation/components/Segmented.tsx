import { Pressable, StyleSheet, View } from 'react-native'

import { colors, line, minTap } from '../theme'
import { MonoLabel } from './MonoLabel'

export type SegmentOption<T extends string> = { readonly value: T; readonly label: string }

type Props<T extends string> = {
  options: readonly SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  /** Names the group for screen readers: "View events as". */
  label: string
}

/** The segmented control: one black band, one box per view, ochre under the one you are in. */
export function Segmented<T extends string>({ options, value, onChange, label }: Props<T>) {
  return (
    <View style={styles.row} accessibilityRole="tablist" accessibilityLabel={label}>
      {options.map((option, index) => {
        const on = option.value === value
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityLabel={option.label}
            accessibilityState={{ selected: on }}
            onPress={() => onChange(option.value)}
            style={[styles.segment, on && styles.segmentOn, index > 0 && styles.divider]}
          >
            <View style={styles.inner}>
              <View style={[styles.dot, on ? styles.dotOn : styles.dotOff]} />
              <View style={[styles.bar, on ? styles.dotOn : styles.dotOff]} />
            </View>
            <MonoLabel size={14} tracking={0.12} color={on ? colors.ink : colors.paper}>
              {option.label}
            </MonoLabel>
          </Pressable>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', borderWidth: line.strong, borderColor: colors.ink, backgroundColor: colors.ink },
  segment: {
    flex: 1,
    minHeight: minTap + 6,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
    paddingHorizontal: 10,
    paddingVertical: 11,
  },
  segmentOn: { backgroundColor: colors.ochre },
  divider: { borderLeftWidth: 2, borderLeftColor: colors.paper },
  inner: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  dot: { width: 5, height: 5, transform: [{ rotate: '45deg' }] },
  dotOn: { backgroundColor: colors.ink },
  dotOff: { backgroundColor: colors.paper },
  bar: { width: 11, height: 3 },
})
