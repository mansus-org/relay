import { useEffect, useState } from 'react'

import type { Post } from '../../domain'
import { useUseCases } from '../use-cases'
import { PostCard } from './PostCard'

/** A post card that resolves the place name of the post's cell. */
export function FeedPostCard({ post, now }: { post: Post; now: Date }) {
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
  return <PostCard post={post} placeName={placeName} now={now} />
}
