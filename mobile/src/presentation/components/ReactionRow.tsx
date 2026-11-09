import { useState } from 'react'
import { Dimensions, Modal, Pressable, StyleSheet, Text, View, type GestureResponderEvent, type StyleProp, type ViewStyle } from 'react-native'

import type { Reaction } from '../../domain'
import { colors, fonts, line, minTap } from '../theme'
import { HardShadow } from './HardShadow'
import { MonoLabel } from './MonoLabel'

/** The six emoji the picker offers, in the order the mockup shows them. */
export const REACTION_CHOICES = ['👍', '❤️', '😂', '😮', '😢', '🔥'] as const

/** What a screen reader says for each one, because an emoji read aloud says nothing. */
const NAMED: Record<string, string> = { '👍': 'Like', '❤️': 'Love', '😂': 'Funny', '😮': 'Wow', '😢': 'Sad', '🔥': 'Fire' }

/** Where the popover lands when nothing said where it was asked for: far enough up to be seen. */
const FALLBACK = 220

type Props = {
  reactions: readonly Reaction[]
  /** Taps one emoji on, or takes the reader's own back off. */
  onToggle: (emoji: string) => void
  style?: StyleProp<ViewStyle>
}

/**
 * The reaction row of a post: a chip per emoji anyone used, and a dashed one that opens the picker.
 * A chip taps on and off; long-pressing one opens the picker with that emoji already marked.
 */
export function ReactionRow({ reactions, onToggle, style }: Props) {
  // The distance from the bottom of the window the popover opens at, or null while it is shut.
  const [bottom, setBottom] = useState<number | null>(null)
  const shown = reactions.filter((r) => r.count > 0)
  const mine = reactions.filter((r) => r.mine).map((r) => r.emoji)
  const close = () => setBottom(null)
  const choose = (emoji: string) => {
    close()
    onToggle(emoji)
  }
  // The popover opens just above wherever the press happened, so it never covers what was pressed.
  const open = (event?: GestureResponderEvent) =>
    setBottom(event?.nativeEvent.pageY === undefined ? FALLBACK : Math.max(96, Dimensions.get('window').height - event.nativeEvent.pageY + 12))

  return (
    <View style={[styles.row, style]}>
      {shown.map((r) => (
        <Pressable
          accessibilityLabel={`${NAMED[r.emoji] ?? r.emoji}: ${r.count}. ${r.mine ? 'Take it back' : 'Add it'}`}
          accessibilityRole="button"
          hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
          key={r.emoji}
          onLongPress={open}
          onPress={() => onToggle(r.emoji)}
          style={[styles.chip, r.mine && styles.mine]}
        >
          <Text style={styles.emoji}>{r.emoji}</Text>
          <MonoLabel color={r.mine ? colors.onRed : colors.ink} size={13} tracking={0.02}>
            {r.count}
          </MonoLabel>
        </Pressable>
      ))}
      <Pressable
        accessibilityLabel="Add a reaction"
        accessibilityRole="button"
        hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
        onPress={open}
        style={styles.add}
      >
        <Text style={styles.plus}>+</Text>
      </Pressable>
      {bottom === null ? null : (
        <Modal animationType="none" onRequestClose={close} transparent visible>
          <Pressable accessibilityLabel="Close the reactions" accessibilityRole="button" onPress={close} style={styles.scrim} />
          <View pointerEvents="box-none" style={[styles.picker, { bottom }]}>
            <HardShadow offset={6} style={styles.popover}>
              <View style={styles.popoverIn}>
                {REACTION_CHOICES.map((emoji) => (
                  <Pressable
                    accessibilityLabel={NAMED[emoji] ?? emoji}
                    accessibilityRole="button"
                    accessibilityState={{ selected: mine.includes(emoji) }}
                    key={emoji}
                    onPress={() => choose(emoji)}
                    style={[styles.pick, mine.includes(emoji) && styles.pickOn]}
                  >
                    <Text style={styles.pickEmoji}>{emoji}</Text>
                  </Pressable>
                ))}
              </View>
            </HardShadow>
          </View>
        </Modal>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: minTap },
  chip: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderColor: colors.ink,
    borderWidth: line.regular,
    flexDirection: 'row',
    gap: 6,
    height: 34,
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  mine: { backgroundColor: colors.red, shadowColor: colors.ink, shadowOffset: { width: 3, height: 3 }, shadowOpacity: 1, shadowRadius: 0 },
  emoji: { fontFamily: fonts.body, fontSize: 15 },
  add: {
    alignItems: 'center',
    borderColor: colors.ink2,
    borderStyle: 'dashed',
    borderWidth: line.regular,
    height: 34,
    justifyContent: 'center',
    width: 34,
  },
  plus: { color: colors.ink2, fontFamily: fonts.monoBold, fontSize: 16, lineHeight: 20 },
  scrim: { backgroundColor: 'rgba(20,18,16,.55)', bottom: 0, left: 0, position: 'absolute', right: 0, top: 0 },
  picker: { alignItems: 'center', left: 0, position: 'absolute', right: 0 },
  popover: { backgroundColor: colors.paper, borderColor: colors.ink, borderWidth: line.strong },
  popoverIn: { flexDirection: 'row', gap: 4, padding: 5 },
  pick: {
    alignItems: 'center',
    borderColor: 'transparent',
    borderWidth: line.regular,
    height: 46,
    justifyContent: 'center',
    width: 46,
  },
  pickOn: { backgroundColor: colors.red, borderColor: colors.ink },
  pickEmoji: { fontSize: 25, lineHeight: 30 },
})
