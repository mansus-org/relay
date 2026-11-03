import { useState } from 'react'
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native'

import { colors, line } from '../theme'

type Props = {
  value: number
  min: number
  max: number
  onChange: (value: number) => void
  accessibilityLabel: string
  /** Spoken value, e.g. "5 kilometres". */
  valueText?: string
}

const KNOB = 28

/** Whole-number slider: drag or tap the track; screen readers adjust it by one step. */
export function Slider({ value, min, max, onChange, accessibilityLabel, valueText }: Props) {
  const [width, setWidth] = useState(0)
  const set = (x: number) => {
    if (width > 0) onChange(Math.round(min + (Math.min(width, Math.max(0, x)) / width) * (max - min)))
  }

  const ratio = (value - min) / (max - min)
  const step = (delta: number) => onChange(Math.min(max, Math.max(min, value + delta)))
  return (
    <View
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={accessibilityLabel}
      accessibilityValue={{ min, max, now: value, text: valueText }}
      accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
      onAccessibilityAction={(e) => step(e.nativeEvent.actionName === 'increment' ? 1 : -1)}
      onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
      style={styles.slider}
      onStartShouldSetResponder={() => true}
      onMoveShouldSetResponder={() => true}
      onResponderGrant={(e) => set(e.nativeEvent.locationX)}
      onResponderMove={(e) => set(e.nativeEvent.locationX)}
    >
      <View style={styles.track} pointerEvents="none" />
      <View style={[styles.fill, { width: `${ratio * 100}%` }]} pointerEvents="none" />
      <View style={[styles.knob, { left: ratio * width - KNOB / 2 }]} pointerEvents="none" />
    </View>
  )
}

const styles = StyleSheet.create({
  slider: { height: 44, justifyContent: 'center' },
  track: { position: 'absolute', left: 0, right: 0, top: 17, height: 10, backgroundColor: colors.paper2, borderWidth: line.regular, borderColor: colors.ink },
  fill: { position: 'absolute', left: 0, top: 17, height: 10, backgroundColor: colors.red, borderWidth: line.regular, borderColor: colors.ink },
  knob: { position: 'absolute', top: 8, width: KNOB, height: KNOB, backgroundColor: colors.ink, borderWidth: line.strong, borderColor: colors.ink },
})
