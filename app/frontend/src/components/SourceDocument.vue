<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiURL } from '../api/client'
import type { FullDocument, Version } from '../api/knowledge'
import { safeURL } from './markdown'
import DocumentReader from './DocumentReader.vue'
const props = defineProps<{ document: FullDocument; versions?: Version[] }>()
const { t } = useI18n()
// Failed staging remains available to the API for recovery without retention.
const originals = computed(() =>
  props.document.original_version_ids.filter(
    (id) =>
      props.document.state === 'ready' ||
      props.versions?.some(
        (version) => version.id === id && version.retain_original,
      ),
  ),
)
</script>
<template>
  <div class="space-y-6">
    <div class="flex flex-wrap gap-4">
      <a
        v-for="version in originals"
        :key="version"
        :href="apiURL(`source-versions/${version}/original`)"
        class="text-link"
        >{{ t('reader.original') }}</a
      >
    </div>
    <p v-if="!originals.length" class="text-sm text-text-secondary">
      {{
        t(
          document.state === 'ready'
            ? 'reader.unretained'
            : 'reader.unavailable',
        )
      }}
    </p>
    <DocumentReader
      v-if="document.body !== null && document.media_type === 'text/markdown'"
      :body="document.body"
      :base-url="
        typeof document.metadata.canonical_url === 'string'
          ? safeURL(document.metadata.canonical_url) || undefined
          : undefined
      "
    />
    <pre
      v-else-if="document.body !== null"
      class="whitespace-pre-wrap break-words font-sans"
      role="article"
      >{{ document.body }}</pre>
    <p v-else>{{ document.state }}</p>
    <details class="rounded-lg border border-default p-4">
      <summary>{{ t('reader.provenance') }}</summary>
      <dl class="mt-4 space-y-3">
        <template v-for="(value, key) in document.metadata" :key="key"
          ><dt class="font-medium">{{ key }}</dt>
          <dd>
            <a
              v-if="
                typeof value === 'string' &&
                ['original_url', 'canonical_url'].includes(String(key)) &&
                safeURL(value)
              "
              :href="safeURL(value)!"
              rel="noopener noreferrer"
              referrerpolicy="no-referrer"
              class="text-link"
              >{{ value }}</a
            ><span v-else>{{ value }}</span>
          </dd></template
        >
      </dl>
    </details>
  </div>
</template>
