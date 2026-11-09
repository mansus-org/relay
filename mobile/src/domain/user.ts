/** Your own account as the node sees it. The handle is how you sign in; the name is what you go by. */
export type Profile = {
  readonly handle: string
  readonly displayName: string
  /** Whether this node lets the account run moderation. The node decides; nothing here guesses. */
  readonly isAdmin: boolean
}

export type User = {
  readonly id: string
  readonly name: string
}

/** The backend keeps a name this long and no longer; the field says so before the call. */
export const MAX_DISPLAY_NAME_LENGTH = 60

/**
 * Why this name cannot be kept, in the words the field shows. Null when it can.
 * Mirrors the rule the server applies, so a name is refused here in the same breath there.
 */
export const displayNameError = (name: string): string | null => {
  const value = name.trim()
  if (!value) return 'A name, even a short one.'
  if (value.length > MAX_DISPLAY_NAME_LENGTH) return `At most 60 characters. This one is ${value.length}.`
  return null
}
