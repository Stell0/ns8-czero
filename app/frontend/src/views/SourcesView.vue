<script setup lang="ts">
import { computed, ref, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeTextInput,
  NeProgressBar,
  NeInlineNotification,
  NeModal,
  NeTable,
  NeTableHead,
  NeTableHeadCell,
  NeTableBody,
  NeTableRow,
  NeTableCell,
} from '@nethesis/vue-components'
import { ReplayIdentity } from '../api/replay'
import { ApiError, request } from '../api/client'
import {
  knowledge,
  type FullDocument,
  type Version,
  type Citation,
} from '../api/knowledge'
import { useResource } from '../api/queries'
import { useSession } from '../stores/session'
import SourceUpload from '../components/SourceUpload.vue'
import ResourceState from '../components/ResourceState.vue'
import SourceDocument from '../components/SourceDocument.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
const route = useRoute(),
  router = useRouter(),
  session = useSession(),
  { t } = useI18n()
const id = computed(() => String(route.params.id || ''))
const offset = computed(() => Math.max(0, Number(route.query.offset) || 0))
const query = computed(() => String(route.query.query || ''))
const filter = ref(query.value),
  upload = ref(false),
  confirm = ref(false)
const list = useResource(
  () => `sources:${offset.value}`,
  () => knowledge.sources(offset.value),
  () => !id.value && !query.value,
)
const matches = useResource(
  () => `source-search:${query.value}:${offset.value}`,
  () =>
    request<{ citations: Citation[] }>(
      `sources/search?${new URLSearchParams({ query: query.value, limit: '50', offset: String(offset.value) })}`,
    ),
  () => !id.value && !!query.value,
)
const entries = computed(() => list.data.value?.documents || [])
watch(query, (value) => {
  filter.value = value
})
function search() {
  void router.push({
    query: {
      ...route.query,
      query: filter.value || undefined,
      offset: undefined,
    },
  })
}
const document = useResource(
  () =>
    `document:${id.value}:${route.query.version || ''}:${route.query.reference || ''}:${route.query.revision_id || ''}`,
  async () => {
    const { reference, version, revision_id: revision } = route.query
    const selectors = [reference, version, revision].filter(
      (value) => value !== undefined,
    )
    if (
      selectors.length > 1 ||
      selectors.some((value) => typeof value !== 'string' || !value) ||
      (reference !== undefined && reference !== 'document')
    )
      throw new ApiError(422)
    return reference === 'document'
      ? request<FullDocument>(
          `source-versions/${(await request<{ data: { version_id: string } }>(`references/document/${encodeURIComponent(id.value)}`)).data.version_id}/full-document`,
        )
      : typeof route.query.version === 'string'
        ? request<FullDocument>(
            `source-versions/${encodeURIComponent(route.query.version)}/full-document`,
          )
        : knowledge.document(
            id.value,
            typeof route.query.revision_id === 'string'
              ? route.query.revision_id
              : undefined,
          )
  },
  () => !!id.value,
)
const sourceId = computed(() =>
  document.data.value && !document.data.value.multipart
    ? document.data.value.parts[0]?.source_id || id.value
    : '',
)
const source = useResource(
  () => `source:${sourceId.value}`,
  () => knowledge.source(sourceId.value),
  () => !!sourceId.value,
)
const versions = useResource(
  () => `versions:${sourceId.value}`,
  () => knowledge.versions(sourceId.value),
  () => !!sourceId.value,
)
interface Progress {
  state: string
  error_code: string | null
  current_available: boolean
  run: {
    id: string
    state: string
    revision: number
    failed: number
    completed: number
    expected_units: number
    error_code: string | null
  } | null
}
const progress = useResource(
  () => `progress:${sourceId.value}`,
  () => request<Progress>(`sources/${sourceId.value}/extraction`),
  () => !!sourceId.value,
)
const latest = computed(() => versions.data.value?.versions[0])
const replay = new ReplayIdentity()
const recovery = useMutation({
  mutation: async (action: 'reprocess' | 'retry' | 'cancel') => {
    const run = progress.data.value?.run
    let path: string, data: object
    if (action === 'reprocess') {
      path = `sources/${sourceId.value}/reindex`
      data = {
        expected_revision: source.data.value?.revision,
      }
    } else if (
      run &&
      !(
        action === 'retry' &&
        progress.data.value?.error_code === 'staging_expired'
      )
    ) {
      path = `extraction-runs/${run.id}/${action}`
      data = {
        expected_revision: run.revision,
      }
    } else {
      path = `source-versions/${latest.value?.id}/retry`
      data = { expected_generation: latest.value?.generation }
    }
    await request(path, {
      method: 'POST',
      data:
        action === 'reprocess' ||
        (path.endsWith('/retry') && path.startsWith('extraction-runs/'))
          ? replay.data(path, data)
          : data,
    })
    replay.clear()
    confirm.value = false
    await reload()
  },
})
async function reload() {
  await Promise.all([
    document.refetch(),
    sourceId.value ? source.refetch() : Promise.resolve(),
    sourceId.value ? versions.refetch() : Promise.resolve(),
    sourceId.value ? progress.refetch() : Promise.resolve(),
  ])
}
let polling = true
let timer: ReturnType<typeof setTimeout>
async function poll() {
  try {
    if (
      session.ready &&
      id.value &&
      !window.document.hidden &&
      !route.query.version &&
      !route.query.revision_id &&
      [progress.data.value?.state, document.data.value?.state].some((state) =>
        ['queued', 'processing', 'retrying', 'incomplete'].includes(
          state || '',
        ),
      )
    )
      await reload()
  } finally {
    if (polling) timer = setTimeout(() => void poll(), 2500)
  }
}
timer = setTimeout(() => void poll(), 2500)
onUnmounted(() => {
  polling = false
  clearTimeout(timer)
})
async function uploaded(version: Version) {
  upload.value = false
  if (id.value) await reload()
  else await router.push(`/sources/${version.source_id}`)
}
</script>
<template>
  <div class="space-y-6">
    <div class="flex flex-wrap gap-3">
      <NeButton
        v-if="session.canWrite && (!id || source.data.value)"
        kind="primary"
        @click="upload = true"
        >{{ t(id ? 'sources.replace' : 'sources.upload') }}</NeButton
      >
      <NeButton
        kind="secondary"
        @click="id ? reload() : query ? matches.refetch() : list.refetch()"
        >{{ t('common.reload') }}</NeButton
      >
    </div>
    <template v-if="!id">
      <form class="flex items-end gap-3" @submit.prevent="search">
        <NeTextInput
          v-model="filter"
          :label="t('nav.search')"
          :is-search="true"
          :clear-search-label="t('common.clear')"
        /><NeButton type="submit" kind="primary">{{
          t('nav.search')
        }}</NeButton>
      </form>
      <ResourceState
        v-if="query"
        :error="matches.error.value"
        :loading="matches.isPending.value"
        :empty="!matches.data.value?.citations.length"
      >
        <ul class="space-y-5">
          <li v-for="hit in matches.data.value?.citations" :key="hit.chunk_id">
            <RouterLink :to="`/evidence/${hit.chunk_id}`" class="text-link">{{
              hit.title
            }}</RouterLink>
            <p class="mt-2 whitespace-pre-wrap">{{ hit.body }}</p>
          </li>
        </ul>
      </ResourceState>
      <ResourceState
        v-else
        :error="list.error.value"
        :loading="list.isPending.value"
        :empty="!entries.length"
      >
        <NeTable :aria-label="t('nav.sources')" card-breakpoint="md">
          <NeTableHead
            ><NeTableHeadCell>{{ t('common.title') }}</NeTableHeadCell
            ><NeTableHeadCell>{{
              t('common.status')
            }}</NeTableHeadCell></NeTableHead
          >
          <NeTableBody
            ><NeTableRow v-for="entry in entries" :key="entry.id"
              ><NeTableCell :data-label="t('common.title')"
                ><RouterLink :to="`/sources/${entry.id}`" class="text-link">{{
                  entry.title
                }}</RouterLink></NeTableCell
              ><NeTableCell :data-label="t('common.status')">{{
                t(
                  `sources.states.${entry.state}`,
                  t('sources.states.incomplete'),
                )
              }}</NeTableCell></NeTableRow
            ></NeTableBody
          >
        </NeTable>
      </ResourceState>
      <div class="flex gap-3">
        <NeButton
          :disabled="offset === 0"
          kind="secondary"
          @click="
            router.push({
              query: { ...route.query, offset: Math.max(0, offset - 50) },
            })
          "
          >{{ t('common.previous') }}</NeButton
        ><NeButton
          :disabled="
            (query
              ? matches.data.value?.citations.length
              : list.data.value?.documents.length) !== 50
          "
          kind="secondary"
          @click="
            router.push({ query: { ...route.query, offset: offset + 50 } })
          "
          >{{ t('common.next') }}</NeButton
        >
      </div>
    </template>
    <ResourceState
      v-else
      :error="document.error.value"
      :loading="document.isPending.value"
    >
      <template v-if="document.data.value">
        <h2 class="text-2xl font-medium">{{ document.data.value.title }}</h2>
        <div v-if="progress.data.value" role="status" class="space-y-2">
          <p>
            {{
              t(
                `sources.states.${progress.data.value.state}`,
                t('sources.states.incomplete'),
              )
            }}
          </p>
          <p v-if="progress.data.value.run">
            {{
              t('sources.units', {
                completed: progress.data.value.run.completed,
                total: progress.data.value.run.expected_units,
              })
            }}
          </p>
          <p v-if="progress.data.value.state === 'failed'">
            {{
              t(
                progress.data.value.error_code === 'staging_expired'
                  ? 'sources.expired'
                  : 'sources.failedHelp',
              )
            }}
          </p>
        </div>
        <NeInlineNotification
          v-if="
            progress.data.value?.current_available &&
            ['queued', 'processing', 'retrying'].includes(
              progress.data.value.state,
            )
          "
          kind="info"
          :title="t('sources.progress')"
          :description="t('reader.replacement')"
        />
        <NeProgressBar
          v-if="
            progress.data.value?.run &&
            !['ready', 'failed', 'cancelled'].includes(
              progress.data.value.state,
            )
          "
          :label="t('sources.progress')"
          :progress="
            Math.round(
              (100 * progress.data.value.run.completed) /
                (progress.data.value.run.expected_units || 1),
            )
          "
        />
        <div
          v-if="session.canWrite && source.data.value"
          class="flex flex-wrap gap-3"
        >
          <NeButton
            v-if="
              progress.data.value &&
              latest?.original_present &&
              latest.state === 'ready'
            "
            kind="secondary"
            @click="confirm = true"
            >{{ t('sources.reprocess') }}</NeButton
          >
          <NeButton
            v-if="latest?.original_present && latest.state === 'failed'"
            kind="secondary"
            :loading="recovery.isLoading.value"
            :disabled="recovery.isLoading.value"
            @click="recovery.mutate('retry')"
            >{{ t('sources.retry') }}</NeButton
          >
          <NeButton
            v-if="
              progress.data.value?.run &&
              !['ready', 'superseded', 'failed'].includes(
                progress.data.value.run.state,
              )
            "
            kind="tertiary"
            :loading="recovery.isLoading.value"
            :disabled="recovery.isLoading.value"
            @click="recovery.mutate('cancel')"
            >{{ t('sources.cancel') }}</NeButton
          >
        </div>
        <ErrorNotice
          v-if="recovery.error.value"
          :error="recovery.error.value"
        />
        <SourceDocument
          :document="document.data.value"
          :versions="versions.data.value?.versions"
        />
      </template>
    </ResourceState>
    <SourceUpload
      v-if="upload"
      :source="id ? source.data.value : undefined"
      @close="upload = false"
      @uploaded="uploaded"
    />
    <NeModal
      :visible="confirm"
      :title="t('sources.reprocess')"
      :primary-label="t('sources.reprocess')"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      :primary-button-loading="recovery.isLoading.value"
      :primary-button-disabled="recovery.isLoading.value"
      @close="confirm = false"
      @primary-click="recovery.mutate('reprocess')"
      ><p>{{ t('sources.confirmReprocess') }}</p></NeModal
    >
  </div>
</template>
