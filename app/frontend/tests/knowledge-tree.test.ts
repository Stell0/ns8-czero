import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import KnowledgeTree from '../src/components/KnowledgeTree.vue'
it('retains a thousand literal pages, virtual parents and prototype-named paths', () => {
  const pages = Array.from({ length: 1000 }, (_, i) => ({
    id: String(i),
    title: `<img> Chapter ${i}`,
    slug: `${i % 2 ? '__proto__' : 'constructor'}/page-${i}`,
    revision: 1,
    updated_at: '',
  }))
  const wrapper = mount(KnowledgeTree, {
    props: { pages },
    global: {
      plugins: [
        createI18n({
          legacy: false,
          locale: 'en',
          messages: { en: { common: { overview: 'Overview' } } },
        }),
      ],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
  expect(wrapper.findAll('a')).toHaveLength(1000)
  expect(wrapper.findAll('summary').map((node) => node.text())).toEqual([
    '__proto__',
    'constructor',
  ])
  expect(wrapper.findAll('img')).toHaveLength(0)
  expect(wrapper.text()).toContain('<img> Chapter 999')
})
