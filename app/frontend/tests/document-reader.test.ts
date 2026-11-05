import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { boundary } from '../src/api/client'
import type { Token } from '../src/components/markdown'
vi.mock('vue-router', () => ({
  useRoute: () => ({ fullPath: '/wiki/current' }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('../src/stores/session', () => ({
  useSession: () => ({ space: { id: 'current-space' } }),
}))
import DocumentReader from '../src/components/DocumentReader.vue'
class Parser {
  static instances: Parser[] = []
  onmessage?: (event: { data: { tokens: Token[] } }) => Promise<void>
  onerror?: () => void
  terminate = vi.fn()
  postMessage = vi.fn()
  constructor() {
    Parser.instances.push(this)
  }
  send(content: string, count = 1) {
    return this.onmessage?.({
      data: {
        tokens: Array.from({ length: count }, () => ({
          type: 'text',
          content,
          tag: '',
          nesting: 0,
        })),
      },
    })
  }
}
beforeEach(() => {
  Parser.instances = []
  vi.stubGlobal('Worker', Parser)
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
it('ignores an already queued old parse without terminating its successor', async () => {
  const wrapper = mount(DocumentReader, { props: { body: 'first' } })
  await nextTick()
  const first = Parser.instances[0]
  await wrapper.setProps({ body: 'second' })
  const second = Parser.instances[1]
  expect(first.terminate).toHaveBeenCalledOnce()
  await first.send('PRIVATE OLD TEXT')
  expect(second.terminate).not.toHaveBeenCalled()
  expect(wrapper.text()).not.toContain('PRIVATE')
  await second.send('Current body')
  expect(wrapper.get('article').text()).toBe('Current body')
  wrapper.unmount()
})
it('access loss between render batches removes all text and prevents another append', async () => {
  vi.useFakeTimers()
  const wrapper = mount(DocumentReader, { props: { body: 'large' } })
  await nextTick()
  const rendering = Parser.instances[0].send('PRIVATE', 600)
  expect(wrapper.get('article').text()).toContain('PRIVATE')
  boundary.invalidate()
  await vi.runAllTimersAsync()
  await rendering
  expect(wrapper.get('article').text()).toBe('')
  expect(wrapper.find('nav').exists()).toBe(false)
  wrapper.unmount()
})
it('terminates a stalled parser at the bounded deadline', async () => {
  vi.useFakeTimers()
  const wrapper = mount(DocumentReader, {
    props: { body: 'hostile' },
    global: { stubs: { NeInlineNotification: true } },
  })
  await nextTick()
  await vi.advanceTimersByTimeAsync(10000)
  expect(Parser.instances[0].terminate).toHaveBeenCalledOnce()
  expect(wrapper.get('article').text()).toBe('')
  expect(wrapper.find('ne-inline-notification-stub').exists()).toBe(true)
  wrapper.unmount()
})
