<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PageSummary } from '../api/knowledge'
const props = withDefaults(
  defineProps<{ pages: PageSummary[]; prefix?: string }>(),
  { prefix: '' },
)
const { t } = useI18n()
const groups = computed(() => {
  const names = new Set(
    props.pages
      .filter((p) => p.slug.startsWith(props.prefix))
      .map((p) => p.slug.slice(props.prefix.length).split('/')[0]),
  )
  return [...names].sort().map((name) => ({
    name,
    path: props.prefix + name,
    page: props.pages.find((p) => p.slug === props.prefix + name),
    children: props.pages.filter((p) =>
      p.slug.startsWith(props.prefix + name + '/'),
    ),
  }))
})
</script>
<template>
  <ul class="space-y-3">
    <li v-for="group in groups" :key="group.path">
      <details
        v-if="group.children.length"
        class="rounded-lg border border-default p-3"
      >
        <summary class="cursor-pointer font-medium">
          {{ group.page?.title || group.name.replaceAll('-', ' ') }}
        </summary>
        <div class="mt-3 space-y-3 pl-3">
          <RouterLink
            v-if="group.page"
            :to="`/wiki/${group.page.id}`"
            class="text-link"
            >{{ t('common.overview') }}</RouterLink
          >
          <KnowledgeTree :pages="group.children" :prefix="group.path + '/'" />
        </div>
      </details>
      <RouterLink
        v-else-if="group.page"
        :to="`/wiki/${group.page.id}`"
        class="text-link"
        >{{ group.page.title }}</RouterLink
      >
    </li>
  </ul>
</template>
