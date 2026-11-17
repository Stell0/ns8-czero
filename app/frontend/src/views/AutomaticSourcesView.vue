<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import * as v from 'valibot'
import {
  NeButton,
  NeTextInput,
  NeTextArea,
  NeCheckbox,
  NeSideDrawer,
  NeTable,
  NeTableHead,
  NeTableHeadCell,
  NeTableBody,
  NeTableRow,
  NeTableCell,
  NeModal,
} from '@nethesis/vue-components'
import { ApiError, errorKey, request } from '../api/client'
import { ReplayIdentity } from '../api/replay'
import { useResource } from '../api/queries'
import { useSession } from '../stores/session'
import ResourceState from '../components/ResourceState.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
interface Definition {
  status: string | null
  id: string
  name: string
  kind: 'github' | 'website'
  config: Record<string, unknown>
  enabled: boolean
  interval_seconds: number | null
  revision: number
  next_run_at: string | null
  last_success_at: string | null
}
interface Run {
  id: string
  state: string
  processed: number
  error_code: string | null
}
const { t, locale } = useI18n(),
  session = useSession()
const offset = ref(0)
const listing = useResource(
  () => `automatic-sources:${offset.value}`,
  () =>
    request<{ definitions: Definition[] }>(
      `automatic-sources?offset=${offset.value}`,
    ),
)
const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString(locale.value) : t('automatic.never')
const entries = computed(() => listing.data.value?.definitions || [])
const drawer = ref(false),
  selected = ref<Definition>(),
  history = ref<Definition>(),
  removing = ref<Definition>()
const name = ref(''),
  kind = ref<'github' | 'website'>('website'),
  locations = ref(''),
  rootURLs = ref(''),
  sitemaps = ref(''),
  include = ref(''),
  exclude = ref(''),
  categories = ref('files'),
  branch = ref('HEAD'),
  enabled = ref(false),
  interval = ref('86400')
const preview = ref<{
  items: { title: string; url: string }[]
  complete: boolean
}>()
const invalid = ref(false)
const mutationMode = ref<'save' | 'preview'>('save')
const nameValid = computed(
  () =>
    v.safeParse(
      v.pipe(v.string(), v.trim(), v.minLength(1), v.maxLength(256)),
      name.value,
    ).success,
)
const intervalValid = computed(
  () =>
    !interval.value ||
    (Number.isInteger(Number(interval.value)) &&
      Number(interval.value) >= 300 &&
      Number(interval.value) <= 2678400),
)
const replay = new ReplayIdentity(),
  commandReplay = new ReplayIdentity()
let editorEpoch = 0
let active = true
onUnmounted(() => {
  active = false
})
const documents = useResource(
  () => `automatic-documents:${history.value?.id}`,
  () =>
    request<{ documents: { id: string; title: string }[] }>(
      `automatic-sources/${history.value!.id}/documents`,
    ),
  () => !!history.value,
)
const runs = useResource(
  () => `automatic-source-runs:${history.value?.id}`,
  () => request<{ runs: Run[] }>(`automatic-sources/${history.value!.id}/runs`),
  () => !!history.value,
)
const contentKinds = ['files', 'issues', 'pull_requests', 'releases'] as const
function toggleContent(value: string, checked: boolean) {
  const selected = new Set(
    categories.value
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean),
  )
  if (checked) selected.add(value)
  else selected.delete(value)
  categories.value = [...selected].join(',')
}
function chooseKind(value: 'github' | 'website') {
  kind.value = value
  preview.value = undefined
}
function reload() {
  void listing.refetch()
  if (history.value) void runs.refetch()
}
function clear() {
  editorEpoch++
  drawer.value = false
  selected.value = undefined
  history.value = undefined
  removing.value = undefined
  preview.value = undefined
  mutation.reset()
  replay.clear()
  commandReplay.clear()
}
watch(
  () => [
    session.account,
    session.space?.id,
    session.generation,
    session.canWrite,
  ],
  clear,
)
function edit(row?: Definition) {
  editorEpoch++
  mutation.reset()
  invalid.value = false
  selected.value = row
  name.value = row?.name || ''
  kind.value = row?.kind || 'website'
  const config = row?.config || {},
    website = (config.website || {}) as Record<string, unknown>
  locations.value = (
    ((kind.value === 'github'
      ? config.repositories
      : website.seeds) as string[]) || []
  ).join('\n')
  rootURLs.value = ((website.allowed_roots || []) as string[]).join('\n')
  sitemaps.value = ((website.sitemaps || []) as string[]).join('\n')
  include.value = (
    ((kind.value === 'github' ? config.paths : config.include) as string[]) ||
    []
  ).join('\n')
  exclude.value = (
    ((kind.value === 'github'
      ? config.exclude
      : website.exclude) as string[]) || []
  ).join('\n')
  categories.value = ((config.include as string[]) || ['files']).join(', ')
  branch.value = String(config.ref || 'HEAD')
  enabled.value = row?.enabled || false
  interval.value = String(row?.interval_seconds || '')
  preview.value = undefined
  replay.clear()
  drawer.value = true
}
const lines = (value: string) =>
  value
    .split(/\n/)
    .map((v) => v.trim())
    .filter(Boolean)
const repositoriesValid = computed(() => {
  const repositories = lines(locations.value)
  return (
    repositories.length >= 1 &&
    repositories.length <= 100 &&
    new Set(repositories).size === repositories.length &&
    repositories.every((repository) =>
      /^[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$/.test(
        repository,
      ),
    )
  )
})
function config() {
  const previous =
    selected.value?.kind === kind.value ? selected.value.config : {}
  if (kind.value === 'github')
    return {
      ...previous,
      repositories: lines(locations.value),
      include: categories.value
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      paths: lines(include.value).length
        ? lines(include.value)
        : ['README*', 'docs/*'],
      exclude: lines(exclude.value),
      ref: branch.value,
    }
  const seeds = lines(locations.value)
  return {
    ...previous,
    website: {
      ...((previous.website || {}) as Record<string, unknown>),
      seeds,
      allowed_roots: lines(rootURLs.value).length
        ? lines(rootURLs.value)
        : seeds,
      sitemaps: lines(sitemaps.value),
      exclude: lines(exclude.value),
    },
    include: lines(include.value),
  }
}
watch(
  [
    name,
    kind,
    locations,
    rootURLs,
    sitemaps,
    include,
    exclude,
    categories,
    branch,
    enabled,
    interval,
  ],
  () => {
    editorEpoch++
    preview.value = undefined
    if (mutation.error.value) mutation.reset()
  },
  { flush: 'sync' },
)
const mutation = useMutation({
  mutation: async (mode: 'save' | 'preview') => {
    mutationMode.value = mode
    invalid.value =
      !lines(locations.value).length ||
      (kind.value === 'github' &&
        (!repositoriesValid.value || !categories.value)) ||
      (mode === 'save' && (!nameValid.value || !intervalValid.value))
    if (invalid.value) return
    const epoch = editorEpoch
    const draft = { kind: kind.value, config: config() }
    if (mode === 'preview') {
      const result = await request<{
        items: { title: string; url: string }[]
        complete: boolean
      }>('automatic-sources/preview', { method: 'POST', data: draft })
      if (active && drawer.value && editorEpoch === epoch)
        preview.value = result
      return
    }
    await request('automatic-sources', {
      method: 'POST',
      data: replay.data('automatic-sources', {
        ...draft,
        name: name.value,
        enabled: enabled.value,
        interval_seconds: interval.value ? Number(interval.value) : null,
        identifier: selected.value?.id || null,
        expected_revision: selected.value?.revision || null,
      }),
    })
    if (active && editorEpoch === epoch) {
      clear()
      await listing.refetch()
    }
  },
})
function fieldError(field: string) {
  const error = mutation.error.value
  return error instanceof ApiError && error.field === field
    ? t(errorKey(error))
    : ''
}
const nameError = computed(() =>
  invalid.value && mutationMode.value === 'save' && !nameValid.value
    ? t('automatic.errors.invalid_source_name')
    : fieldError('name'),
)
const locationsError = computed(() =>
  invalid.value && kind.value === 'github' && !repositoriesValid.value
    ? t('automatic.errors.invalid_github_repositories')
    : invalid.value && !lines(locations.value).length
      ? t('automatic.seedsRequired')
      : fieldError(
          kind.value === 'github'
            ? 'config.repositories'
            : 'config.website.seeds',
        ),
)
const intervalError = computed(() =>
  invalid.value && mutationMode.value === 'save' && !intervalValid.value
    ? t('automatic.errors.invalid_source_interval')
    : fieldError('interval_seconds'),
)
const command = useMutation({
  mutation: async ({
    row,
    action,
  }: {
    row: Definition
    action: 'run' | 'pause' | 'remove'
  }) => {
    const path = `automatic-sources/${row.id}/actions`
    await request(path, {
      method: 'POST',
      data: commandReplay.data(path, {
        expected_revision: row.revision,
        action,
      }),
    })
    if (active) {
      if (action === 'remove' && history.value?.id === row.id)
        history.value = undefined
      removing.value = undefined
      commandReplay.clear()
      await listing.refetch()
      if (history.value) await runs.refetch()
    }
  },
})
</script>
<template>
  <div class="space-y-6">
    <p>{{ t('automatic.help') }}</p>
    <div class="flex flex-wrap gap-3">
      <NeButton
        v-if="session.canWrite"
        kind="primary"
        :disabled="mutation.isLoading.value"
        @click="edit()"
        >{{ t('automatic.add') }}</NeButton
      >
      <NeButton kind="secondary" @click="reload">{{
        t('common.reload')
      }}</NeButton>
    </div>
    <ErrorNotice v-if="command.error.value" :error="command.error.value" />
    <ResourceState
      :error="listing.error.value"
      :loading="listing.isPending.value"
      :empty="!entries.length"
    >
      <NeTable :aria-label="t('automatic.title')">
        <NeTableHead
          ><NeTableHeadCell>{{ t('common.title') }}</NeTableHeadCell
          ><NeTableHeadCell>{{ t('automatic.type') }}</NeTableHeadCell
          ><NeTableHeadCell>{{ t('automatic.last') }}</NeTableHeadCell
          ><NeTableHeadCell>{{ t('automatic.next') }}</NeTableHeadCell
          ><NeTableHeadCell>{{
            t('automatic.actions')
          }}</NeTableHeadCell></NeTableHead
        >
        <NeTableBody
          ><NeTableRow v-for="row in entries" :key="row.id">
            <NeTableCell :data-label="t('common.title')">{{
              row.name
            }}</NeTableCell>
            <NeTableCell :data-label="t('automatic.type')">{{
              t(`automatic.${row.kind}`)
            }}</NeTableCell>
            <NeTableCell :data-label="t('automatic.last')">{{
              formatDate(row.last_success_at)
            }}</NeTableCell>
            <NeTableCell :data-label="t('automatic.next')">{{
              row.enabled
                ? row.next_run_at
                  ? formatDate(row.next_run_at)
                  : t('automatic.manual')
                : t('automatic.paused')
            }}</NeTableCell>
            <NeTableCell :data-label="t('automatic.actions')"
              ><div class="flex flex-wrap gap-2">
                <NeButton kind="tertiary" @click="history = row">{{
                  t('automatic.runs')
                }}</NeButton>
                <template v-if="session.canWrite">
                  <NeButton
                    kind="tertiary"
                    :disabled="mutation.isLoading.value"
                    @click="edit(row)"
                    >{{ t('automatic.edit') }}</NeButton
                  >
                  <NeButton
                    kind="tertiary"
                    :disabled="!row.enabled || command.isLoading.value"
                    @click="command.mutate({ row, action: 'run' })"
                    >{{ t('automatic.run') }}</NeButton
                  >
                  <NeButton
                    kind="tertiary"
                    :disabled="!row.enabled || command.isLoading.value"
                    @click="command.mutate({ row, action: 'pause' })"
                    >{{ t('automatic.pause') }}</NeButton
                  >
                  <NeButton kind="tertiary" @click="removing = row">{{
                    t('automatic.remove')
                  }}</NeButton>
                </template>
              </div></NeTableCell
            >
          </NeTableRow></NeTableBody
        >
      </NeTable>
    </ResourceState>
    <div class="flex gap-3">
      <NeButton
        kind="secondary"
        :disabled="offset === 0"
        @click="offset -= 50"
        >{{ t('common.previous') }}</NeButton
      ><NeButton
        kind="secondary"
        :disabled="entries.length < 50"
        @click="offset += 50"
        >{{ t('common.next') }}</NeButton
      >
    </div>
    <section v-if="history" class="space-y-3">
      <ResourceState
        :error="documents.error.value"
        :loading="documents.isPending.value"
        ><ul>
          <li
            v-for="document in documents.data.value?.documents"
            :key="document.id"
          >
            <RouterLink
              :to="{ path: `/sources/${document.id}`, query: $route.query }"
              >{{ document.title }}</RouterLink
            >
          </li>
        </ul></ResourceState
      >
      <h2 class="text-xl font-medium">
        {{ history.name }} — {{ t('automatic.runs') }}
      </h2>
      <ResourceState
        :error="runs.error.value"
        :loading="runs.isPending.value"
        :empty="!runs.data.value?.runs.length"
        ><ul>
          <li v-for="run in runs.data.value?.runs" :key="run.id">
            {{ t(`automatic.states.${run.state}`) }} ·
            {{ t('automatic.processed', { count: run.processed }) }} ·
            {{ run.error_code }}
          </li>
        </ul></ResourceState
      >
    </section>
    <NeSideDrawer
      v-if="drawer && session.canWrite"
      :is-shown="true"
      :title="t(selected ? 'automatic.edit' : 'automatic.add')"
      :close-aria-label="t('common.close')"
      :close-on-click-outside="false"
      @close="!mutation.isLoading.value && clear()"
    >
      <form
        class="space-y-6"
        @submit.prevent="!mutation.isLoading.value && mutation.mutate('save')"
      >
        <ErrorNotice
          v-if="mutation.error.value"
          :error="mutation.error.value"
          :title-key="
            mutationMode === 'save'
              ? 'automatic.saveError'
              : 'automatic.previewError'
          "
        />
        <fieldset :disabled="mutation.isLoading.value" class="space-y-6">
          <NeTextInput
            v-model="name"
            :label="t('common.title')"
            :invalid-message="nameError"
            :aria-invalid="!!nameError || undefined"
          />
          <fieldset class="space-y-2">
            <legend>{{ t('automatic.type') }}</legend>
            <NeButton
              v-for="value in ['website', 'github'] as const"
              :key="value"
              kind="secondary"
              :aria-pressed="kind === value"
              @click="chooseKind(value)"
              >{{ t(`automatic.${value}`) }}</NeButton
            >
          </fieldset>
          <NeTextArea
            v-model="locations"
            :invalid-message="locationsError"
            :aria-invalid="!!locationsError || undefined"
            :label="
              t(kind === 'github' ? 'automatic.repositories' : 'automatic.urls')
            "
            :helper-text="
              t(
                kind === 'github'
                  ? 'automatic.repositoriesHelp'
                  : 'automatic.lines',
              )
            "
          />
          <NeTextArea
            v-if="kind === 'website'"
            v-model="rootURLs"
            :label="t('automatic.roots')"
            :helper-text="t('automatic.rootsHelp')"
            :invalid-message="fieldError('config.website.allowed_roots')"
            :aria-invalid="
              !!fieldError('config.website.allowed_roots') || undefined
            "
          />
          <NeTextArea
            v-if="kind === 'website'"
            v-model="sitemaps"
            :label="t('automatic.sitemaps')"
            :helper-text="t('automatic.lines')"
          />
          <fieldset
            v-if="kind === 'github'"
            class="space-y-3"
            :aria-describedby="
              invalid && !categories ? 'automatic-content-error' : undefined
            "
          >
            <legend>{{ t('automatic.categories') }}</legend>
            <NeCheckbox
              v-for="value in contentKinds"
              :key="value"
              :model-value="
                categories
                  .split(',')
                  .map((v) => v.trim())
                  .includes(value)
              "
              :label="t(`automatic.contents.${value}`)"
              @update:model-value="toggleContent(value, $event)"
            />
            <p
              v-if="invalid && !categories"
              id="automatic-content-error"
              role="alert"
              class="text-sm text-red-700 dark:text-red-400"
            >
              {{ t('automatic.errors.invalid_github_selection') }}
            </p>
            <p class="text-sm">{{ t('automatic.filesHelp') }}</p>
          </fieldset>
          <NeTextInput
            v-if="kind === 'github'"
            v-model="branch"
            :label="t('automatic.branch')"
            :invalid-message="fieldError('config.ref')"
            :aria-invalid="!!fieldError('config.ref') || undefined"
          />
          <NeTextArea
            v-model="include"
            :label="t('automatic.include')"
            :helper-text="t('automatic.lines')"
          />
          <NeTextArea
            v-model="exclude"
            :label="t('automatic.exclude')"
            :helper-text="t('automatic.lines')"
          />
          <fieldset class="space-y-2">
            <legend>{{ t('automatic.frequency') }}</legend>
            <div class="flex flex-wrap gap-2">
              <NeButton
                v-for="(seconds, label) in {
                  manual: '',
                  hourly: '3600',
                  daily: '86400',
                  weekly: '604800',
                }"
                :key="label"
                kind="secondary"
                :aria-pressed="interval === seconds"
                @click="interval = seconds"
                >{{ t(`automatic.${label}`) }}</NeButton
              >
            </div>
          </fieldset>
          <NeTextInput
            v-model="interval"
            :invalid-message="intervalError"
            :aria-invalid="!!intervalError || undefined"
            :label="t('automatic.interval')"
            :helper-text="t('automatic.intervalHelp')"
          />
          <NeCheckbox v-model="enabled" :label="t('automatic.enable')" />
          <p>{{ t('automatic.authority') }}</p>
          <div v-if="preview">
            <p>{{ t('automatic.previewHelp') }}</p>
            <ul>
              <li v-for="item in preview.items" :key="item.url">
                {{ item.title }} — {{ item.url }}
              </li>
            </ul>
          </div>
          <div class="flex gap-3">
            <NeButton
              kind="secondary"
              :disabled="mutation.isLoading.value"
              @click="mutation.mutate('preview')"
              >{{ t('automatic.preview') }}</NeButton
            ><NeButton
              type="submit"
              kind="primary"
              :loading="mutation.isLoading.value"
              >{{ t('automatic.save') }}</NeButton
            >
          </div>
        </fieldset>
      </form>
    </NeSideDrawer>
    <NeModal
      v-if="removing"
      :visible="true"
      :title="t('automatic.remove')"
      :primary-label="t('automatic.remove')"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      kind="warning"
      primary-button-kind="danger"
      :primary-button-disabled="command.isLoading.value"
      :primary-button-loading="command.isLoading.value"
      @close="!command.isLoading.value && (removing = undefined)"
      @primary-click="command.mutate({ row: removing!, action: 'remove' })"
      ><ErrorNotice v-if="command.error.value" :error="command.error.value" />
      <p>{{ t('automatic.removeHelp') }}</p></NeModal
    >
  </div>
</template>
