<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import * as v from 'valibot'
import {
  NeButton,
  NeTextInput,
  NeTextArea,
  NeCheckbox,
  NeListbox,
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
import DriveFolderFields from '../components/DriveFolderFields.vue'
import DriveFolderPreview from '../components/DriveFolderPreview.vue'
import {
  drivePath,
  takeDriveEditor,
  type DriveConnection,
  type DrivePreview,
} from '../api/googleDrive'

import { websitePdfAttachmentsAvailable } from '../api/features'

type SourceKind = 'github' | 'website' | 'google_drive'
interface Definition {
  owner_id: string
  status: string | null
  id: string
  name: string
  kind: SourceKind
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
  diagnostics?: {
    html?: Record<string, number>
    pdf?: Record<string, number>
    reasons?: Record<string, number>
    pending?: number
  }
  checkpoint_available?: boolean
  available_at?: string | null
}
interface SourcePreview {
  items: {
    title: string
    url: string
    kind?: 'pdf' | 'html'
    selection?: 'selected' | 'skipped'
    reason?: string
  }[]
  complete: boolean
}
const attachmentsAvailable = websitePdfAttachmentsAvailable()
const { t, te, locale } = useI18n(),
  session = useSession()
const offset = ref(0)
const listing = useResource(
  () => `automatic-sources:${offset.value}`,
  () =>
    request<{ definitions: Definition[] }>(
      `automatic-sources?offset=${offset.value}`,
    ),
)
const route = useRoute()
const router = useRouter()
const connection = useResource(
  () => 'google-drive-connection',
  () => request<DriveConnection>(`${drivePath}/connection`),
  () => session.canWrite,
)
const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString(locale.value) : t('automatic.never')
const entries = computed(() => listing.data.value?.definitions || [])
const drawer = ref(false),
  selected = ref<Definition>(),
  history = ref<Definition>(),
  removing = ref<Definition>()
function emptyDraft() {
  return {
    name: '',
    locations: '',
    rootURLs: '',
    collectPdfs: false,
    pdfRoots: '',
    pdfSeeds: '',
    pdfInclude: '',
    pageQueue: false,
    sitemaps: '',
    include: '',
    exclude: '',
    categories: 'files',
    branch: 'HEAD',
    enabled: false,
    interval: '',
  }
}
function emptyDrafts() {
  return {
    website: emptyDraft(),
    github: emptyDraft(),
    google_drive: emptyDraft(),
  }
}
const kind = ref<SourceKind>('website')
const drafts = ref(emptyDrafts())
const form = computed(() => drafts.value[kind.value])
const drivePreview = ref<DrivePreview>()
const driveBusy = ref(false)
const advanced = ref(false)
const returnNotice = ref('')
const owns = (row: Definition) =>
  row.kind !== 'google_drive' || row.owner_id === session.account
const sourceOptions = computed(() => {
  const kinds: SourceKind[] =
    selected.value?.kind === 'google_drive'
      ? ['google_drive']
      : ['website', 'github']
  if (!selected.value && connection.data.value?.available)
    kinds.push('google_drive')
  return kinds.map((id) => ({ id, label: t(`automatic.${id}`) }))
})
const preview = ref<SourcePreview>()
const invalid = ref(false)
const mutationMode = ref<'save' | 'preview'>('save')
const nameValid = computed(
  () =>
    v.safeParse(
      v.pipe(v.string(), v.trim(), v.minLength(1), v.maxLength(256)),
      form.value.name,
    ).success,
)
const intervalValid = computed(
  () =>
    !form.value.interval ||
    (Number.isInteger(Number(form.value.interval)) &&
      Number(form.value.interval) >= 300 &&
      Number(form.value.interval) <= 2678400),
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
    form.value.categories
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean),
  )
  if (checked) selected.add(value)
  else selected.delete(value)
  form.value.categories = [...selected].join(',')
}
function chooseKind(value: unknown) {
  advanced.value = !!selected.value
  const option = sourceOptions.value.find((option) => option.id === value)
  if (option) kind.value = option.id
  invalid.value = false
}
function reload() {
  void listing.refetch()
  if (session.canWrite) void connection.refetch()
  if (history.value) void runs.refetch()
}
function clear() {
  editorEpoch++
  drawer.value = false
  drafts.value = emptyDrafts()
  drivePreview.value = undefined
  driveBusy.value = false
  returnNotice.value = ''
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
  advanced.value = !!row
  editorEpoch++
  mutation.reset()
  invalid.value = false
  selected.value = row
  drafts.value = emptyDrafts()
  drivePreview.value = undefined
  returnNotice.value = ''
  kind.value = row?.kind || 'website'
  form.value.name = row?.name || ''
  const config = row?.config || {},
    website = (config.website || {}) as Record<string, unknown>
  form.value.locations = (
    ((kind.value === 'github'
      ? config.repositories
      : website.seeds) as string[]) || []
  ).join('\n')
  form.value.rootURLs = ((website.allowed_roots || []) as string[]).join('\n')
  const attachments = config.attachments as Record<string, unknown> | undefined
  form.value.collectPdfs = !!attachments
  form.value.pdfRoots = ((attachments?.allowed_roots || []) as string[]).join(
    '\n',
  )
  form.value.pdfSeeds = ((attachments?.seeds || []) as string[]).join('\n')
  form.value.pdfInclude = ((attachments?.include || []) as string[]).join('\n')
  form.value.pageQueue = attachments?.page_queue === true
  form.value.sitemaps = ((website.sitemaps || []) as string[]).join('\n')
  form.value.include = (
    ((kind.value === 'github' ? config.paths : config.include) as string[]) ||
    []
  ).join('\n')
  form.value.exclude = (
    ((kind.value === 'github'
      ? config.exclude
      : website.exclude) as string[]) || []
  ).join('\n')
  form.value.categories = (
    (row?.kind === 'github' && (config.include as string[])) || ['files']
  ).join(', ')
  form.value.branch = String(config.ref || 'HEAD')
  form.value.enabled = row?.enabled || false
  form.value.interval = String(row?.interval_seconds || '')
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
  const repositories = lines(form.value.locations)
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
      repositories: lines(form.value.locations),
      include: form.value.categories
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      paths: lines(form.value.include).length
        ? lines(form.value.include)
        : ['README*', 'docs/*'],
      exclude: lines(form.value.exclude),
      ref: form.value.branch,
    }
  const seeds = lines(form.value.locations)
  const { attachments, ...publicConfig } = previous
  return {
    ...publicConfig,
    ...(form.value.collectPdfs && attachmentsAvailable
      ? {
          attachments: {
            ...((attachments || {}) as Record<string, unknown>),
            allowed_roots: lines(form.value.pdfRoots),
            seeds: lines(form.value.pdfSeeds),
            include: lines(form.value.pdfInclude),
            page_queue: form.value.pageQueue,
          },
        }
      : {}),
    website: {
      ...((previous.website || {}) as Record<string, unknown>),
      seeds,
      allowed_roots: lines(form.value.rootURLs).length
        ? lines(form.value.rootURLs)
        : seeds,
      sitemaps: lines(form.value.sitemaps),
      exclude: lines(form.value.exclude),
    },
    include: lines(form.value.include),
  }
}
watch(
  form,
  () => {
    editorEpoch++
    preview.value = undefined
    if (mutation.error.value) mutation.reset()
  },
  { deep: true, flush: 'sync' },
)
watch(
  [kind, () => form.value.locations, () => connection.data.value?.connected],
  () => {
    drivePreview.value = undefined
  },
)
function driveConnectionChanged() {
  drivePreview.value = undefined
  reload()
}
function driveProblem(mode: 'save' | 'preview') {
  if (kind.value !== 'google_drive') return ''
  if (!connection.data.value?.connected) return 'automatic.driveConnectFirst'
  if (!form.value.locations.trim() && !selected.value)
    return 'automatic.driveEnterFolder'
  if (mode === 'save') {
    if (form.value.enabled && !connection.data.value.offline)
      return 'automatic.driveRequireOffline'
    if (!drivePreview.value) return 'automatic.drivePreviewFirst'
  }
  return ''
}
const mutation = useMutation({
  mutation: async (mode: 'save' | 'preview') => {
    mutationMode.value = mode
    invalid.value =
      (kind.value === 'google_drive'
        ? !!driveProblem(mode)
        : !lines(form.value.locations).length) ||
      (kind.value === 'github' &&
        (!repositoriesValid.value || !form.value.categories)) ||
      (mode === 'save' && (!nameValid.value || !intervalValid.value))
    if (invalid.value) return
    const epoch = editorEpoch
    const identity = {
      identifier: selected.value?.id || null,
      expected_revision: selected.value?.revision || null,
    }
    const drive = kind.value === 'google_drive'
    if (mode === 'preview' && drive) {
      drivePreview.value = undefined
      const result = await request<DrivePreview>(`${drivePath}/preview`, {
        method: 'POST',
        data: { ...identity, folder_url: form.value.locations.trim() || null },
      })
      if (active && drawer.value && editorEpoch === epoch) {
        if (!form.value.name.trim()) form.value.name = result.folder_name
        returnNotice.value = ''
        drivePreview.value = result
      }
      return
    }
    const selection = drive
      ? { preview_token: drivePreview.value!.preview_token }
      : { kind: kind.value, config: config() }
    if (mode === 'preview') {
      const result = await request<SourcePreview>('automatic-sources/preview', {
        method: 'POST',
        data: selection,
      })
      if (active && drawer.value && editorEpoch === epoch)
        preview.value = result
      return
    }
    const path = drive ? `${drivePath}/save` : 'automatic-sources'
    await request(path, {
      method: 'POST',
      data: replay.data(path, {
        ...selection,
        name: form.value.name,
        enabled: form.value.enabled,
        interval_seconds: form.value.interval
          ? Number(form.value.interval)
          : null,
        ...identity,
      }),
    })
    if (active && editorEpoch === epoch) {
      clear()
      await listing.refetch()
    }
  },
})
// A callback carries a fixed status. Refresh the owner-scoped connection before
// resuming; a query parameter alone cannot establish a Google connection.
watch(
  [connection.data, listing.data, () => route.query.google_drive],
  ([account, list, status]) => {
    if (
      !session.canWrite ||
      !session.space ||
      !account?.available ||
      !list ||
      !['connected', 'cancelled', 'error'].includes(String(status))
    )
      return
    const sourceId = takeDriveEditor(session.account, session.space.id)
    const row = list.definitions.find(
      (row) => row.id === sourceId && row.kind === 'google_drive' && owns(row),
    )
    if (!sourceId || row) {
      edit(row)
      kind.value = 'google_drive'
    }
    returnNotice.value =
      status === 'connected' && account.connected
        ? 'automatic.driveReturnConnected'
        : status === 'cancelled'
          ? 'automatic.driveReturnCancelled'
          : 'automatic.driveReturnError'
    const query = { ...route.query }
    delete query.google_drive
    delete query.offline
    void router.replace({ query })
  },
  { immediate: true },
)
watch(mutation.error, (error) => {
  if (
    error instanceof ApiError &&
    [
      'config.ref',
      'config.website.allowed_roots',
      'config.attachments.allowed_roots',
      'config.include',
      'config.exclude',
      'config.paths',
    ].includes(error.field)
  )
    advanced.value = true
  if (
    error instanceof ApiError &&
    [error.code, error.reason].some((code) =>
      ['drive_preview_required', 'drive_reconnect_required'].includes(code),
    )
  ) {
    drivePreview.value = undefined
    void connection.refetch()
  }
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
    : invalid.value && !lines(form.value.locations).length
      ? t('automatic.seedsRequired')
      : fieldError(
          kind.value === 'github'
            ? 'config.repositories'
            : 'config.website.seeds',
        ),
)
const driveError = computed(() => {
  const key = invalid.value && driveProblem(mutationMode.value)
  return key ? t(key) : ''
})
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
    const driveRun = row.kind === 'google_drive' && action === 'run'
    const path = driveRun
      ? `${drivePath}/${row.id}/run`
      : `automatic-sources/${row.id}/actions`
    await request(path, {
      method: 'POST',
      data: commandReplay.data(path, {
        expected_revision: row.revision,
        ...(driveRun ? {} : { action }),
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
    <p v-if="returnNotice && !drawer" role="status">{{ t(returnNotice) }}</p>
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
                    v-if="owns(row)"
                    kind="tertiary"
                    :disabled="mutation.isLoading.value"
                    @click="edit(row)"
                    >{{
                      t(
                        row.kind === 'google_drive' &&
                          connection.data.value &&
                          !connection.data.value.connected
                          ? 'automatic.driveReconnect'
                          : 'automatic.edit',
                      )
                    }}</NeButton
                  >
                  <NeButton
                    v-if="owns(row)"
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
            {{ t('automatic.processed', { count: run.processed }) }}
            <template v-if="run.error_code">
              ·
              {{
                te('automatic.errors.' + run.error_code)
                  ? t('automatic.errors.' + run.error_code)
                  : run.error_code
              }}</template
            >
            <dl v-if="run.diagnostics" class="mb-3 space-y-1 text-sm">
              <template v-for="type in ['html', 'pdf'] as const" :key="type">
                <template v-if="run.diagnostics[type]">
                  <dt>{{ t(`automatic.attachments.${type}`) }}</dt>
                  <dd class="flex flex-wrap gap-x-3">
                    <span
                      v-for="(count, outcome) in run.diagnostics[type]"
                      :key="outcome"
                    >
                      {{ t(`automatic.outcomes.${outcome}`, { count }) }}
                    </span>
                  </dd>
                </template>
              </template>
              <template v-if="run.diagnostics.pending">
                <dt>{{ t('automatic.states.pending') }}</dt>
                <dd>{{ run.diagnostics.pending }}</dd>
              </template>
              <template
                v-if="Object.keys(run.diagnostics.reasons || {}).length"
              >
                <dt>{{ t('automatic.attachments.unresolved') }}</dt>
                <dd
                  v-for="(count, reason) in run.diagnostics.reasons"
                  :key="reason"
                >
                  {{ t(`automatic.errors.${reason}`, reason) }} ({{ count }})
                </dd>
              </template>
            </dl>
            <p
              v-if="
                run.available_at && Date.parse(run.available_at) > Date.now()
              "
              class="text-sm"
            >
              {{
                t('automatic.attachments.availableAt', {
                  time: formatDate(run.available_at),
                })
              }}
            </p>
            <p v-if="run.checkpoint_available" class="text-sm">
              {{ t('automatic.attachments.checkpoint') }}
            </p>
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
      @close="!mutation.isLoading.value && !driveBusy && clear()"
    >
      <form
        class="space-y-6"
        @submit.prevent="
          !mutation.isLoading.value && !driveBusy && mutation.mutate('save')
        "
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
        <fieldset
          :disabled="mutation.isLoading.value || driveBusy"
          class="space-y-6"
        >
          <NeListbox
            :model-value="kind"
            :label="t('automatic.type')"
            :options="sourceOptions"
            :no-options-label="t('common.options')"
            :optional-label="t('common.optional')"
            :disabled="sourceOptions.length === 1"
            @update:model-value="chooseKind"
          />
          <NeTextInput
            v-model="form.name"
            :label="t('common.title')"
            :invalid-message="nameError"
            :aria-invalid="!!nameError || undefined"
          />
          <template v-if="kind === 'google_drive'">
            <p v-if="returnNotice" role="status">{{ t(returnNotice) }}</p>
            <DriveFolderFields
              v-model="form.locations"
              :source-id="selected?.id"
              :connection="connection.data.value"
              :enabled="form.enabled"
              :invalid-message="fieldError('folder_url')"
              :disconnect-names="
                entries
                  .filter(
                    (row) =>
                      row.kind === 'google_drive' && owns(row) && row.enabled,
                  )
                  .map((row) => row.name)
              "
              @busy="driveBusy = $event"
              @refresh="driveConnectionChanged"
            />
          </template>
          <template v-else>
            <NeTextArea
              v-model="form.locations"
              :invalid-message="locationsError"
              :aria-invalid="!!locationsError || undefined"
              :label="
                t(
                  kind === 'github'
                    ? 'automatic.repositories'
                    : 'automatic.urls',
                )
              "
              :helper-text="
                t(
                  kind === 'github'
                    ? 'automatic.repositoriesHelp'
                    : 'automatic.lines',
                )
              "
            />
            <fieldset
              v-if="kind === 'github'"
              class="space-y-3"
              :aria-describedby="
                invalid && !form.categories
                  ? 'automatic-content-error'
                  : undefined
              "
            >
              <legend>{{ t('automatic.categories') }}</legend>
              <NeCheckbox
                v-for="value in contentKinds"
                :key="value"
                :model-value="
                  form.categories
                    .split(',')
                    .map((v) => v.trim())
                    .includes(value)
                "
                :label="t(`automatic.contents.${value}`)"
                @update:model-value="toggleContent(value, $event)"
              />
              <p
                v-if="invalid && !form.categories"
                id="automatic-content-error"
                role="alert"
                class="text-sm text-red-700 dark:text-red-400"
              >
                {{ t('automatic.errors.invalid_github_selection') }}
              </p>
              <p class="text-sm">{{ t('automatic.filesHelp') }}</p>
            </fieldset>
            <details
              :open="advanced"
              class="space-y-4"
              @toggle="advanced = ($event.target as HTMLDetailsElement).open"
            >
              <summary>{{ t('automatic.advanced') }}</summary>
              <NeTextArea
                v-if="kind === 'website'"
                v-model="form.rootURLs"
                :label="t('automatic.roots')"
                :helper-text="t('automatic.rootsHelp')"
                :invalid-message="fieldError('config.website.allowed_roots')"
                :aria-invalid="
                  !!fieldError('config.website.allowed_roots') || undefined
                "
              />
              <NeTextArea
                v-if="kind === 'website'"
                v-model="form.sitemaps"
                :label="t('automatic.sitemaps')"
                :helper-text="t('automatic.lines')"
              />
              <NeTextInput
                v-if="kind === 'github'"
                v-model="form.branch"
                :label="t('automatic.branch')"
                :invalid-message="fieldError('config.ref')"
                :aria-invalid="!!fieldError('config.ref') || undefined"
              />
              <NeTextArea
                v-model="form.include"
                :label="t('automatic.include')"
                :helper-text="t('automatic.lines')"
              />
              <NeTextArea
                v-model="form.exclude"
                :label="t('automatic.exclude')"
                :helper-text="t('automatic.lines')"
              />
            </details>
          </template>
          <fieldset
            v-if="attachmentsAvailable && kind === 'website'"
            class="space-y-3"
          >
            <legend>{{ t('automatic.attachments.title') }}</legend>
            <NeCheckbox
              v-model="form.collectPdfs"
              :label="t('automatic.attachments.enable')"
            />
            <template v-if="form.collectPdfs">
              <NeTextArea
                v-model="form.pdfRoots"
                :label="t('automatic.attachments.roots')"
                :helper-text="t('automatic.attachments.rootsHelp')"
                :invalid-message="
                  fieldError('config.attachments.allowed_roots')
                "
                :aria-invalid="
                  !!fieldError('config.attachments.allowed_roots') || undefined
                "
              />
              <NeTextArea
                v-model="form.pdfSeeds"
                :label="t('automatic.attachments.seeds')"
                :helper-text="t('automatic.lines')"
              />
              <NeTextArea
                v-model="form.pdfInclude"
                :label="t('automatic.attachments.filters')"
                :helper-text="t('automatic.lines')"
              />
              <NeCheckbox
                v-model="form.pageQueue"
                :label="t('automatic.attachments.pageQueue')"
              />
              <p class="text-sm">
                {{ t('automatic.attachments.pageQueueHelp') }}
              </p>
            </template>
          </fieldset>
          <NeCheckbox v-model="form.enabled" :label="t('automatic.enable')" />
          <template v-if="kind !== 'google_drive' || form.enabled">
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
                  :aria-pressed="form.interval === seconds"
                  @click="form.interval = seconds"
                  >{{ t(`automatic.${label}`) }}</NeButton
                >
              </div>
            </fieldset>
            <NeTextInput
              v-model="form.interval"
              :invalid-message="intervalError"
              :aria-invalid="!!intervalError || undefined"
              :label="t('automatic.interval')"
              :helper-text="t('automatic.intervalHelp')"
            />
          </template>
          <p>{{ t('automatic.authority') }}</p>
          <p v-if="driveError" role="alert">{{ driveError }}</p>
          <DriveFolderPreview v-if="drivePreview" :preview="drivePreview" />
          <div v-if="preview">
            <p>{{ t('automatic.previewHelp') }}</p>
            <p v-if="!preview.complete">
              {{ t('automatic.attachments.partialPreview') }}
            </p>
            <ul>
              <li v-for="item in preview.items" :key="item.url">
                {{ item.title
                }}<template v-if="item.title !== item.url">
                  — {{ item.url }}</template
                >
                <template v-if="item.kind === 'pdf'">
                  ·
                  {{
                    t(`automatic.attachments.${item.selection || 'selected'}`)
                  }}
                  <template v-if="item.reason">
                    ·
                    {{
                      t(`automatic.errors.${item.reason}`, item.reason)
                    }}</template
                  >
                </template>
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
