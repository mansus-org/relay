import { useRouter } from 'expo-router'
import { ScrollView, StyleSheet, Text, View } from 'react-native'

import { DAY_MS, HOUR_MS, MINUTE_MS, formatEventDate, formatEventTime } from '../../../src/domain'
import { Alert } from '../../../src/presentation/components/Alert'
import { Button } from '../../../src/presentation/components/Button'
import { Chip } from '../../../src/presentation/components/Chip'
import { GeoSun } from '../../../src/presentation/components/Geo'
import { MonoLabel } from '../../../src/presentation/components/MonoLabel'
import { NavBar } from '../../../src/presentation/components/NavBar'
import { TextField } from '../../../src/presentation/components/TextField'
import { colors, fonts, line } from '../../../src/presentation/theme'
import { useCreateEvent } from '../../../src/presentation/use-events'

/** A small block that moves the date by one honest step. No calendar widget to download. */
function Step({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Text accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={styles.step} suppressHighlighting>
      {label}
    </Text>
  )
}

function FieldLabel({ text, note }: { text: string; note?: string }) {
  return (
    <View style={styles.labelRow}>
      <View style={styles.rule} />
      <MonoLabel size={11} tracking={0.16}>
        {text}
      </MonoLabel>
      {note ? (
        <MonoLabel size={11} tracking={0.16} color={colors.ink2}>
          {note}
        </MonoLabel>
      ) : null}
    </View>
  )
}

export default function NewEvent() {
  const router = useRouter()
  const { state, set, shiftStart, toggleCommunity, submit } = useCreateEvent()
  const { draft, errors, communities } = state
  const when = draft.startsAt ? `${formatEventDate(draft.startsAt)} · ${formatEventTime(draft.startsAt)}` : 'Tomorrow evening'
  const until = draft.endsAt ? formatEventTime(draft.endsAt) : null
  const endsAt = (ms: number) => set({ endsAt: new Date((draft.startsAt ?? new Date()).getTime() + ms) })

  const post = async () => {
    const id = await submit()
    if (id) router.replace(`/events/${id}`)
  }

  return (
    <View style={styles.screen}>
      <NavBar
        title="New event"
        cancelLabel="‹ Cancel"
        onCancel={() => router.back()}
        action={
          <View style={styles.post}>
            <Button label="Post" size="sm" busy={state.busy} onPress={() => void post()} />
          </View>
        }
        decoration={<GeoSun size={110} right={-26} top={30} />}
      />
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.form}>
          <TextField
            label="Title"
            value={draft.title}
            onChangeText={(title) => set({ title })}
            placeholder="Sunday market"
            error={errors.title}
            maxLength={120}
          />

          <View style={styles.field}>
            <FieldLabel text="Starts" />
            <Text style={styles.when}>{when}</Text>
            <View style={styles.steps}>
              <Step label="−1 d" onPress={() => shiftStart(-DAY_MS)} />
              <Step label="+1 d" onPress={() => shiftStart(DAY_MS)} />
              <Step label="−1 h" onPress={() => shiftStart(-HOUR_MS)} />
              <Step label="+1 h" onPress={() => shiftStart(HOUR_MS)} />
              <Step label="+15 m" onPress={() => shiftStart(15 * MINUTE_MS)} />
            </View>
            {errors.startsAt ? <Text style={styles.error}>{errors.startsAt}</Text> : null}
          </View>

          <View style={styles.field}>
            <FieldLabel text="Ends" note="optional" />
            <Text style={styles.until}>{until ?? 'Open-ended'}</Text>
            <View style={styles.steps}>
              <Step label="+30 m" onPress={() => endsAt(30 * MINUTE_MS)} />
              <Step label="+1 h" onPress={() => endsAt(HOUR_MS)} />
              <Step label="+3 h" onPress={() => endsAt(3 * HOUR_MS)} />
              {draft.endsAt ? <Step label="Clear" onPress={() => set({ endsAt: null })} /> : null}
            </View>
            {errors.endsAt ? <Text style={styles.error}>{errors.endsAt}</Text> : null}
          </View>

          <TextField
            label="Where"
            value={draft.venueName}
            onChangeText={(venueName) => set({ venueName })}
            placeholder="The back room at the club"
            maxLength={120}
          />

          <View style={styles.field}>
            <FieldLabel text="Place" />
            <Text style={styles.place}>{state.placeName ?? 'Somewhere we cannot see yet'}</Text>
            <MonoLabel size={11} tracking={0.08} color={colors.ink2}>
              It goes on the map where you are standing now.
            </MonoLabel>
          </View>

          {communities.length > 0 ? (
            <View style={styles.field}>
              <FieldLabel text="Filed under" note="optional" />
              <View style={styles.chips}>
                {communities.map((community) => (
                  <Chip
                    key={community.id}
                    label={community.name}
                    tone={draft.communityId === community.id ? 'on' : 'plain'}
                    accessibilityLabel={`File under ${community.name}`}
                    accessibilityState={{ selected: draft.communityId === community.id }}
                    onPress={() => toggleCommunity(community.id)}
                  />
                ))}
              </View>
              <MonoLabel size={11} tracking={0.08} color={colors.ink2}>
                {draft.communityId
                  ? 'Everyone in that community sees it, wherever they are.'
                  : 'Pick one of yours and it is on that community’s list, wherever it is held.'}
              </MonoLabel>
            </View>
          ) : null}

          <TextField
            label="Details"
            value={draft.details}
            onChangeText={(details) => set({ details })}
            placeholder="Bring something to share."
            error={errors.details}
            multiline
            numberOfLines={5}
            maxLength={500}
          />

          {state.error ? <Alert message={state.error} /> : null}
          <View style={styles.submit}>
            <Button label={state.busy ? 'Posting…' : 'Post event'} busy={state.busy} onPress={() => void post()} />
          </View>
        </View>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  scroll: { paddingBottom: 40 },
  form: { padding: 16, gap: 10 },
  post: { marginLeft: 'auto' },
  field: { gap: 8, marginTop: 18 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rule: { width: 14, height: 3, backgroundColor: colors.red },
  when: { fontFamily: fonts.display, fontSize: 26, lineHeight: 30, color: colors.ink },
  until: { fontFamily: fonts.bodyMedium, fontSize: 18, color: colors.ink },
  place: { fontFamily: fonts.bodyMedium, fontSize: 18, color: colors.ink },
  steps: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  step: {
    minHeight: 44,
    minWidth: 56,
    paddingHorizontal: 12,
    justifyContent: 'center',
    textAlign: 'center',
    fontFamily: fonts.monoBold,
    fontSize: 13,
    letterSpacing: 0.6,
    color: colors.ink,
    backgroundColor: colors.paper,
    borderWidth: line.regular,
    borderColor: colors.ink,
  },
  error: { marginTop: 6, fontFamily: fonts.mono, fontSize: 12, letterSpacing: 0.6, color: colors.redText },
  submit: { alignSelf: 'stretch', marginTop: 16 },
})
