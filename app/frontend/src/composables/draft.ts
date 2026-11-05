import { onScopeDispose, watch, type WatchSource } from 'vue'
import { boundary } from '../api/client'

// A response may refresh lists, but must never replace a newer or closed draft.
export function useDraftGuard(sources: WatchSource[] = []) {
  let revision = 0
  const clear = () => {
    revision++
  }
  const release = boundary.onClear(clear)
  watch(sources, clear, { flush: 'sync' })
  onScopeDispose(() => {
    clear()
    release()
  })
  function current() {
    const expected = revision
    return () => expected === revision
  }
  function start() {
    clear()
    return current()
  }
  return { current, start, clear }
}
