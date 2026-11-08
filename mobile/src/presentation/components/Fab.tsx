import { useState } from 'react'
import { Pressable, StyleSheet, Text } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { colors, fonts, line } from '../theme'
import { HardShadow } from './HardShadow'

/** Floating red "+" in the bottom-right corner of its (relative) parent. */
export function Fab({ label, onPress }: { label: string; onPress: () => void }) {
  const { bottom } = useSafeAreaInsets()
  const [pressed, setPressed] = useState(false)
  return (
    <HardShadow pressed={pressed} style={[styles.wrap, { bottom: 18 + bottom }]}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        onPress={onPress}
        onPressIn={() => setPressed(true)}
        onPressOut={() => setPressed(false)}
        style={styles.fab}
      >
        <Text style={styles.plus}>+</Text>
      </Pressable>
    </HardShadow>
  )
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', right: 13 },
  fab: { width: 62, height: 62, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.red, borderWidth: line.strong, borderColor: colors.ink },
  plus: { fontFamily: fonts.display, fontSize: 40, lineHeight: 46, color: colors.onRed },
})
