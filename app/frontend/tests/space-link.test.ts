import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SpaceLink from '../src/components/SpaceLink.vue'
it('puts the selected space in copyable links, preserving explicit destinations and hashes', async () => {
  const router = createRouter({
    history: createMemoryHistory('/memory/'),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<p />' } }],
  })
  await router.push('/wiki/current?space_id=protected')
  const wrapper = mount(SpaceLink, {
    props: { to: '/wiki/parent?revision=2#heading' },
    slots: { default: 'Parent' },
    global: { plugins: [router] },
  })
  expect(wrapper.get('a').attributes('href')).toBe(
    '/memory/wiki/parent?revision=2&space_id=protected#heading',
  )
  await wrapper.setProps({ to: '/sources/other?space_id=explicit' })
  expect(wrapper.get('a').attributes('href')).toBe(
    '/memory/sources/other?space_id=explicit',
  )
  await wrapper.setProps({ to: '/auth/sign-in' })
  expect(wrapper.get('a').attributes('href')).toBe('/memory/auth/sign-in')
})
