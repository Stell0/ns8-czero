<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NeListbox } from '@nethesis/vue-components'
import { request } from '../api/client'
import { knowledge } from '../api/knowledge'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
const { t } = useI18n()
const route = useRoute(),
  router = useRouter()
const query = computed(() => String(route.query.query || ''))
const kind = computed(() =>
  ['wiki', 'source'].includes(String(route.query.kind))
    ? String(route.query.kind)
    : 'all',
)
const advanced = ref(false)
const options = computed(() => ({
  mode: String(route.query.mode || 'text'),
  rerank: String(route.query.rerank || 'off'),
  graph_depth: String(route.query.graph_depth || '0'),
}))
const index = useResource(
  () => 'search-index',
  () =>
    request<{ configured: boolean; indexed: number }>('knowledge/index/status'),
  () => advanced.value,
)
function option(key: string, value: unknown) {
  void router.push({ query: { ...route.query, [key]: String(value) } })
}
const { data, error, isPending } = useResource(
  () => `search:${query.value}:${kind.value}:${JSON.stringify(options.value)}`,
  () => knowledge.search(query.value, kind.value, options.value),
  () => !!query.value,
)
</script>
<template>
  <div class="space-y-6">
    <NeListbox
      :model-value="kind"
      :label="t('search.kind')"
      :options="
        ['all', 'wiki', 'source'].map((id) => ({
          id,
          label: t(`search.${id}`),
        }))
      "
      :no-options-label="t('common.options')"
      :optional-label="t('common.optional')"
      @update:model-value="
        (value) =>
          router.push({ query: { ...route.query, kind: String(value) } })
      "
    />
    <details @toggle="advanced = ($event.target as HTMLDetailsElement).open">
      <summary>{{ t('search.advanced') }}</summary>
      <p class="my-4 text-text-secondary">{{ t('search.providerHelp') }}</p>
      <div class="grid gap-4 sm:grid-cols-3">
        <NeListbox
          :model-value="options.mode"
          :label="t('search.mode')"
          :options="
            ['text', 'auto', 'semantic', 'hybrid'].map((id) => ({
              id,
              label: t(`search.${id}`),
            }))
          "
          :no-options-label="t('common.options')"
          :optional-label="t('common.optional')"
          @update:model-value="option('mode', $event)"
        />
        <NeListbox
          :model-value="options.rerank"
          :label="t('search.scoring')"
          :options="
            ['off', 'rerank', 'filter'].map((id) => ({
              id,
              label: t(`search.${id}`),
            }))
          "
          :no-options-label="t('common.options')"
          :optional-label="t('common.optional')"
          @update:model-value="option('rerank', $event)"
        />
        <NeListbox
          :model-value="options.graph_depth"
          :label="t('search.depth')"
          :options="['0', '1', '2', '3'].map((id) => ({ id, label: id }))"
          :no-options-label="t('common.options')"
          :optional-label="t('common.optional')"
          @update:model-value="option('graph_depth', $event)"
        />
      </div>
      <p class="mt-4 text-sm">
        {{
          index.data.value?.configured
            ? t('search.indexed', { count: index.data.value.indexed })
            : t('search.noIndex')
        }}
      </p>
    </details>
    <p v-if="!query">{{ t('search.hint') }}</p>
    <ResourceState
      v-else
      :error="error"
      :loading="isPending"
      :empty="data?.hits.length === 0"
    >
      <p v-if="data?.fallback_reasons?.length" role="status">
        {{ t('search.fallback') }}
      </p>
      <ul class="space-y-6">
        <li
          v-for="hit in data?.hits"
          :key="hit.id"
          class="rounded-lg border border-default p-5"
        >
          <RouterLink
            class="text-link text-lg"
            :to="
              hit.wiki
                ? {
                    path: `/wiki/${hit.wiki.page_id}`,
                    query: { revision: hit.wiki.revision },
                  }
                : `/evidence/${hit.citation?.chunk_id}`
            "
            >{{ hit.title }}</RouterLink
          >
          <p class="mt-3 whitespace-pre-wrap text-text-secondary">
            {{ hit.excerpt }}
          </p>
        </li>
      </ul>
      <p class="text-sm text-text-secondary">{{ t('search.bounded') }}</p>
      <details v-if="data">
        <summary>{{ t('search.details') }}</summary>
        <p>
          {{ data.retrieval_method }} ·
          {{
            t('search.counts', {
              candidates: data.candidate_count,
              scored: data.scored_count,
            })
          }}
        </p>
      </details>
      <section
        v-for="graph in data?.graphs"
        :key="graph.root"
        class="space-y-3"
      >
        <h2 class="text-xl font-medium">{{ t('search.related') }}</h2>
        <ul class="space-y-2">
          <li v-for="node in graph.nodes" :key="node.id">
            <RouterLink
              :to="`/explore/entities/${node.id}`"
              class="text-link"
              >{{ node.label }}</RouterLink
            >
          </li>
        </ul>
        <p v-if="graph.truncated">{{ t('search.bounded') }}</p>
      </section>
    </ResourceState>
  </div>
</template>
