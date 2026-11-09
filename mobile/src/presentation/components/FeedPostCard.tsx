import { useEffect, useState } from 'react'

import type { Post } from '../../domain'
import { useUseCases } from '../use-cases'
import { PostCard } from './PostCard'

type Props = {
  post: Post
  now: Date
  /** Opens the thread of this post. */
  onPress?: () => void
  /** Taps one of this post's reactions on, or takes the reader's own back off. */
  onToggleReaction: (emoji: string) => void
}

/** A post card that resolves the place name of the post's cell. */
export function FeedPostCard({ post, now, onPress, onToggleReaction }: Props) {
  const { placeNameOf } = useUseCases()
  const [placeName, setPlaceName] = useState<string | null>(null)
  const { locationCell } = post
  useEffect(() => {
    let cancelled = false
    if (locationCell) {
      void placeNameOf(locationCell).then((name) => {
        if (!cancelled) setPlaceName(name)
      })
    }
    return () => {
      cancelled = true
    }
  }, [locationCell, placeNameOf])
  return <PostCard post={post} placeName={placeName} now={now} onPress={onPress} onToggleReaction={onToggleReaction} />
}
