<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { request } from '../api/client'
import { knowledge, type FullDocument } from '../api/knowledge'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import SourceDocument from '../components/SourceDocument.vue'
const route = useRoute(),
  { t } = useI18n()
const citation = useResource(
  () => `citation:${route.params.id}`,
  () => knowledge.citation(String(route.params.id)),
)
const document = useResource(
  () =>
    `citation-document:${route.params.id}:${citation.data.value?.version_id || ''}`,
  () =>
    request<FullDocument>(
      `source-versions/${encodeURIComponent(citation.data.value!.version_id)}/full-document`,
    ),
  () => !!citation.data.value,
)
</script>
<template>
  <ResourceState
    :error="citation.error.value || document.error.value"
    :loading="citation.isPending.value || document.isPending.value"
  >
    <div v-if="citation.data.value && document.data.value" class="space-y-6">
      <h2 class="text-xl font-medium">{{ document.data.value.title }}</h2>
      <details class="rounded-lg border border-default p-4">
        <summary>{{ t('reader.evidence') }}</summary>
        <blockquote class="my-4 whitespace-pre-wrap">
          {{ citation.data.value.body }}
        </blockquote>
        <dl class="break-all text-sm">
          <dt>{{ t('reader.citationId') }}</dt>
          <dd>{{ citation.data.value.chunk_id }}</dd>
          <dt>{{ t('reader.contentHash') }}</dt>
          <dd>{{ citation.data.value.content_hash }}</dd>
        </dl>
      </details>
      <SourceDocument :document="document.data.value" />
    </div>
  </ResourceState>
</template>
