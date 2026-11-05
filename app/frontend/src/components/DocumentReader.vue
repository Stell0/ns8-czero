<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { NeInlineNotification } from '@nethesis/vue-components'
import { boundary, localURL } from '../api/client'
import { contentLink } from '../api/content-links'
import { useSession } from '../stores/session'
import { renderTokens, type Heading, type Token } from './markdown'
const props = defineProps<{ body: string; baseUrl?: string }>()
const session = useSession()
const { t } = useI18n()
const route = useRoute()
const root = ref<HTMLElement>()
const headings = ref<Heading[]>([])
const failed = ref(false)
const rendering = ref(false)
let worker: Worker | undefined
let timeout: ReturnType<typeof setTimeout>
let generation = 0
function clear() {
  rendering.value = false
  generation++
  worker?.terminate()
  worker = undefined
  clearTimeout(timeout)
  root.value?.replaceChildren()
  headings.value = []
}
const unsubscribe = boundary.onClear(clear)
watch(
  [() => props.body, root],
  ([body, element]) => {
    clear()
    failed.value = false
    if (!element || !body) return
    rendering.value = true
    performance.mark('c0-document-start')
    const current = generation
    worker = new Worker(localURL('markdown-worker.js'))
    timeout = setTimeout(() => {
      if (current === generation) {
        clear()
        failed.value = true
      }
    }, 10000)
    worker.onerror = () => {
      if (current === generation) {
        clear()
        failed.value = true
      }
    }
    worker.onmessage = async (event: MessageEvent<{ tokens: Token[] }>) => {
      if (current !== generation) return
      worker?.terminate()
      worker = undefined
      clearTimeout(timeout)
      const outline: Heading[] = []
      let batch = 0
      for (const token of renderTokens(
        element,
        event.data.tokens,
        outline,
        (text) => t('reader.image', { text }),
        props.baseUrl || new URL(localURL('/'), location.origin).href,
        (href) =>
          contentLink(
            href,
            new URL(localURL('/'), location.origin).href,
            session.space?.id,
          ),
      )) {
        void token
        if (current !== generation) return
        if (++batch % 256 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0))
          if (current !== generation) return
        }
      }
      headings.value = outline
      rendering.value = false
      performance.measure('c0-document-render', 'c0-document-start')
    }
    worker.postMessage(body)
  },
  { flush: 'post' },
)
onBeforeUnmount(() => {
  clear()
  unsubscribe()
})
</script>
<template>
  <div class="grid min-w-0 gap-8 xl:grid-cols-4">
    <nav
      v-if="headings.length"
      :aria-label="t('reader.toc')"
      class="xl:order-2"
    >
      <h2 class="mb-3 font-medium">{{ t('reader.toc') }}</h2>
      <ul class="space-y-2 text-sm">
        <li v-for="heading in headings" :key="heading.id">
          <a
            :href="`${localURL(route.fullPath.split('#')[0])}#${heading.id}`"
            class="text-link"
            >{{ heading.label || t('reader.section') }}</a
          >
        </li>
      </ul>
    </nav>
    <div class="min-w-0 xl:col-span-3">
      <NeInlineNotification
        v-if="failed"
        kind="error"
        :title="t('reader.renderError')"
        :description="t('errors.unavailable')"
      />
      <article ref="root" class="reader" :aria-busy="rendering" />
    </div>
  </div>
</template>
