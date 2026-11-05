import { effectScope, ref } from 'vue'
import { expect, it } from 'vitest'
import { useDraftGuard } from '../src/composables/draft'
import { boundary } from '../src/api/client'

it('rejects results after close/reopen, a newer preview, disposal or access loss', () => {
  const scope = effectScope()
  const shown = ref(true)
  const draft = scope.run(() => useDraftGuard([shown]))!
  const old = draft.current()
  shown.value = false
  shown.value = true
  expect(old()).toBe(false)
  const first = draft.start(),
    second = draft.start()
  expect(first()).toBe(false)
  expect(second()).toBe(true)
  boundary.invalidate()
  expect(second()).toBe(false)
  const last = draft.current()
  scope.stop()
  expect(last()).toBe(false)
})
