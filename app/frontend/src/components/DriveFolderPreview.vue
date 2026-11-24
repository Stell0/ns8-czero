<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DrivePreview } from '../api/googleDrive'
defineProps<{ preview: DrivePreview }>()
const { t, te } = useI18n()
const heading = ref<HTMLElement>()
onMounted(() => {
  heading.value?.focus({ preventScroll: true })
  heading.value?.scrollIntoView({ block: 'start' })
})
function skipped(reason: string) {
  const key = `automatic.driveSkips.${reason}`
  return t(
    /^[a-z_]+$/.test(reason) && te(key) ? key : 'automatic.driveSkips.other',
  )
}
</script>
<template>
  <section
    class="space-y-3 rounded-lg border border-default p-4"
    aria-labelledby="drive-preview-heading"
  >
    <h2
      id="drive-preview-heading"
      ref="heading"
      tabindex="-1"
      class="font-medium"
    >
      {{ t('automatic.drivePreview', { name: preview.folder_name }) }}
    </h2>
    <p v-if="!preview.complete" class="text-sm text-text-secondary">
      {{ t('automatic.drivePartial') }}
    </p>
    <p v-else-if="!preview.items.length">{{ t('automatic.driveEmpty') }}</p>
    <ul class="divide-y divide-default">
      <li
        v-for="(item, index) in preview.items"
        :key="index"
        class="flex flex-wrap items-baseline justify-between gap-x-3 py-2"
      >
        <span class="font-medium">{{ item.title }}</span>
        <span class="text-sm text-text-secondary">{{
          item.outcome === 'include'
            ? t(
                item.reason === 'pdf_text_layer_only'
                  ? 'automatic.driveIncludeTextLayer'
                  : 'automatic.driveInclude',
              )
            : t('automatic.driveSkip', { reason: skipped(item.reason) })
        }}</span>
        <span
          v-if="item.textless_pages?.length"
          class="w-full text-sm text-text-secondary"
        >
          {{
            t('automatic.driveTextlessPages', {
              count: item.textless_page_count,
              pages:
                item.textless_pages.join(', ') +
                ((item.textless_page_count ?? 0) > item.textless_pages.length
                  ? '…'
                  : ''),
            })
          }}
        </span>
      </li>
    </ul>
  </section>
</template>
