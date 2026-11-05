import { expect, it } from 'vitest'
import { ReplayIdentity } from '../src/api/replay'

it('retries an unchanged request but isolates targets, actions, revisions and successes', () => {
  const replay = new ReplayIdentity()
  const first = replay.data('runs/a/retry', { expected_revision: 2 })
  expect(replay.data('runs/a/retry', { expected_revision: 2 })).toEqual(first)
  const target = replay.data('runs/b/retry', { expected_revision: 2 })
  expect(target.idempotency_key).not.toBe(first.idempotency_key)
  const action = replay.data('runs/b/reprocess', { expected_revision: 2 })
  expect(action.idempotency_key).not.toBe(target.idempotency_key)
  const revision = replay.data('runs/b/reprocess', { expected_revision: 3 })
  expect(revision.idempotency_key).not.toBe(action.idempotency_key)
  replay.clear()
  expect(
    replay.data('runs/b/reprocess', { expected_revision: 3 }).idempotency_key,
  ).not.toBe(revision.idempotency_key)
})
