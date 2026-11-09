import { Redirect } from 'expo-router'

/**
 * `/admin` has no screen of its own. The queue is the whole job, so anything that lands here -
 * an old link, a typed-in path - goes straight to it rather than to a menu of three doors.
 */
export default function AdminIndex() {
  return <Redirect href="/admin/queue" />
}
