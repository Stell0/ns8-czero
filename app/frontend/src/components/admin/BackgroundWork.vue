<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeListbox,
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
} from '@nethesis/vue-components'
import { useDraftGuard } from '../../composables/draft'
import { ReplayIdentity } from '../../api/replay'
import { ApiError, request } from '../../api/client'
import { useResource } from '../../api/queries'
import ErrorNotice from '../ErrorNotice.vue'
import ResourceState from '../ResourceState.vue'
interface Job {
  id: string
  handler: string
  state: string
  attempts: number
}
interface Schedule {
  id: string
  name: string
  handler: string
  enabled: boolean
  interval_seconds: number
}
interface Unit {
  id: string
  ordinal: number
  state: string
  attempts: number
  lifetime_attempts: number
  duration_ms: number | null
  error_code: string | null
  available_at: string | null
  locator: { kind: string; first?: number }
}
interface Run {
  id: string
  state: string
  revision: number
  version_id: string
  processing_generation: number
  succeeded: number
  expected_units: number
  error_code: string | null
}
const { t } = useI18n(),
  mode = ref('jobs'),
  drawer = ref(false),
  name = ref(''),
  handler = ref(''),
  payload = ref('{}'),
  interval = ref('3600'),
  jobId = ref(''),
  schedule = ref<Schedule>(),
  runId = ref(''),
  offset = ref(0),
  unitOffset = ref(0),
  enabled = ref(false)
const handlers = useResource(
  () => 'handlers',
  () =>
    request<{ handlers: { name: string; timeout_seconds: number }[] }>(
      'jobs/handlers',
      {},
      false,
    ),
)
const jobs = useResource(
  () => `jobs:${offset.value}`,
  () =>
    request<{ jobs: Job[] }>(`jobs?limit=50&offset=${offset.value}`, {}, false),
  () => mode.value === 'jobs',
)
const schedules = useResource(
  () => `schedules:${offset.value}`,
  () =>
    request<{ schedules: Schedule[] }>(
      `schedules?limit=50&offset=${offset.value}`,
      {},
      false,
    ),
  () => mode.value === 'schedules',
)
const runs = useResource(
  () => `extractions:${offset.value}`,
  () =>
    request<{ runs: Run[] }>(`extraction-runs?limit=50&offset=${offset.value}`),
  () => mode.value === 'extractions',
)
const job = useResource(
  () => `job:${jobId.value}`,
  async () => ({
    job: await request(`jobs/${jobId.value}`, {}, false),
    runs: await request(`jobs/${jobId.value}/runs`, {}, false),
  }),
  () => !!jobId.value && mode.value === 'jobs',
)
const scheduleRuns = useResource(
  () => `schedule:${schedule.value?.id}`,
  () => request(`schedules/${schedule.value!.id}/runs`, {}, false),
  () => !!schedule.value && mode.value === 'schedules',
)
const units = useResource(
  () => `units:${runId.value}:${unitOffset.value}`,
  () =>
    request<{ run: Run; parser: object; units: Unit[] }>(
      `extraction-runs/${runId.value}/units?limit=50&offset=${unitOffset.value}`,
    ),
  () => !!runId.value && mode.value === 'extractions',
)
const replay = new ReplayIdentity()
async function reload() {
  if (mode.value === 'jobs') await jobs.refetch()
  else if (mode.value === 'schedules') await schedules.refetch()
  else {
    await runs.refetch()
    if (runId.value) await units.refetch()
  }
}
const draft = useDraftGuard([drawer, mode, schedule])
const create = useMutation({
  mutation: async () => {
    const current = draft.current()
    let data: unknown
    try {
      data = JSON.parse(payload.value)
    } catch {
      throw new ApiError(422)
    }
    if (!data || typeof data !== 'object' || Array.isArray(data))
      throw new ApiError(422)
    if (mode.value === 'jobs') {
      await request(
        'jobs',
        {
          method: 'POST',
          data: replay.data('jobs', { handler: handler.value, payload: data }),
        },
        false,
      )
      replay.clear()
    } else
      await request(
        'schedules',
        {
          method: 'POST',
          data: {
            name: name.value,
            handler: handler.value,
            payload: data,
            interval_seconds: Number(interval.value),
          },
        },
        false,
      )
    if (current()) drawer.value = false
    await reload()
  },
})
const saveSchedule = useMutation({
  mutation: async () => {
    if (!schedule.value) return
    const current = draft.current()
    await request(
      `schedules/${schedule.value.id}`,
      {
        method: 'PUT',
        data: {
          enabled: enabled.value,
          interval_seconds: Number(interval.value),
        },
      },
      false,
    )
    if (current()) schedule.value = undefined
    await reload()
  },
})
const recover = useMutation({
  mutation: async (action: 'retry' | 'cancel' | 'restart') => {
    const run = units.data.value?.run
    if (!run) return
    const path =
      action === 'restart'
        ? `source-versions/${run.version_id}/retry`
        : `extraction-runs/${run.id}/${action}`
    const data =
      action === 'restart'
        ? { expected_generation: run.processing_generation }
        : action === 'cancel'
          ? { expected_revision: run.revision }
          : replay.data(path, { expected_revision: run.revision })
    await request(path, { method: 'POST', data })
    replay.clear()
    await reload()
  },
})
function selectSchedule(item: Schedule) {
  schedule.value = item
  interval.value = String(item.interval_seconds)
  enabled.value = item.enabled
}
function selectRun(id: string) {
  runId.value = id
  unitOffset.value = 0
}
</script>
<template>
  <div class="space-y-5">
    <NeListbox
      v-model="mode"
      :label="t('nav.work')"
      :options="
        ['jobs', 'schedules', 'extractions'].map((id) => ({
          id,
          label: t(`admin.${id}`),
        }))
      "
      :no-options-label="t('common.options')"
      :optional-label="t('common.optional')"
    />
    <div class="flex flex-wrap gap-3">
      <NeButton
        v-if="mode !== 'extractions'"
        kind="primary"
        @click="drawer = true"
        >{{
          t(mode === 'jobs' ? 'admin.enqueue' : 'admin.createSchedule')
        }}</NeButton
      ><NeButton kind="secondary" @click="reload">{{
        t('common.reload')
      }}</NeButton>
    </div>
    <ErrorNotice
      v-if="recover.error.value || saveSchedule.error.value"
      :error="recover.error.value || saveSchedule.error.value"
    />
    <ResourceState
      v-if="mode === 'jobs'"
      :error="jobs.error.value"
      :loading="jobs.isPending.value"
      ><ul class="space-y-3">
        <li
          v-for="item in jobs.data.value?.jobs"
          :key="item.id"
          class="flex flex-wrap items-center gap-4"
        >
          <span>{{ item.handler }} · {{ item.state }}</span>
          <span class="break-all text-sm text-text-secondary">{{
            item.id
          }}</span
          ><NeButton kind="secondary" @click="jobId = item.id">{{
            t('common.details')
          }}</NeButton>
        </li>
      </ul>
      <pre
        v-if="job.data.value"
        class="mt-4 overflow-auto rounded-lg bg-elevation-1 p-4 text-sm"
        >{{ JSON.stringify(job.data.value, null, 2) }}</pre>
    </ResourceState>
    <ResourceState
      v-else-if="mode === 'schedules'"
      :error="schedules.error.value"
      :loading="schedules.isPending.value"
      ><ul class="space-y-3">
        <li
          v-for="item in schedules.data.value?.schedules"
          :key="item.id"
          class="flex flex-wrap items-center gap-4"
        >
          <span>{{ item.name }} · {{ item.interval_seconds }}</span
          ><NeButton kind="secondary" @click="selectSchedule(item)">{{
            t('common.details')
          }}</NeButton>
        </li>
      </ul>
      <form
        v-if="schedule"
        class="mt-6 space-y-4"
        @submit.prevent="saveSchedule.mutate()"
      >
        <NeTextInput
          v-model="interval"
          :label="t('admin.interval')"
          :disabled="saveSchedule.isLoading.value"
        /><NeCheckbox
          v-model="enabled"
          :label="t('admin.enabled')"
          :disabled="saveSchedule.isLoading.value"
        /><NeButton
          kind="secondary"
          type="submit"
          :loading="saveSchedule.isLoading.value"
          :disabled="saveSchedule.isLoading.value"
          >{{ t('common.save') }}</NeButton
        >
        <pre class="overflow-auto text-sm">{{
          JSON.stringify(scheduleRuns.data.value, null, 2)
        }}</pre>
      </form></ResourceState
    >
    <ResourceState
      v-else
      :error="runs.error.value"
      :loading="runs.isPending.value"
      ><ul class="space-y-3">
        <li
          v-for="run in runs.data.value?.runs"
          :key="run.id"
          class="flex flex-wrap items-center gap-4"
        >
          <span>{{ run.id }} · {{ run.state }}</span
          ><NeButton kind="secondary" @click="selectRun(run.id)">{{
            t('common.details')
          }}</NeButton>
        </li>
      </ul>
      <section
        v-if="units.data.value"
        class="mt-6 space-y-4"
        data-testid="extraction-details"
      >
        <h2 class="text-xl font-medium">{{ t('admin.extractionUnits') }}</h2>
        <p role="status">
          {{ units.data.value.run.state }} ·
          {{
            t('sources.units', {
              completed: units.data.value.run.succeeded,
              total: units.data.value.run.expected_units,
            })
          }}
        </p>
        <p>{{ t('reader.replacement') }}</p>
        <div class="flex flex-wrap gap-3">
          <NeButton
            kind="secondary"
            :disabled="
              recover.isLoading.value ||
              units.data.value.run.state !== 'failed' ||
              units.data.value.run.error_code === 'staging_expired'
            "
            :loading="recover.isLoading.value"
            @click="recover.mutate('retry')"
            >{{ t('sources.retry') }}</NeButton
          ><NeButton
            kind="secondary"
            :disabled="
              recover.isLoading.value ||
              ['ready', 'superseded'].includes(units.data.value.run.state)
            "
            :loading="recover.isLoading.value"
            @click="recover.mutate('cancel')"
            >{{ t('sources.cancel') }}</NeButton
          ><NeButton
            kind="secondary"
            :disabled="
              recover.isLoading.value ||
              !['failed', 'superseded'].includes(units.data.value.run.state)
            "
            :loading="recover.isLoading.value"
            @click="recover.mutate('restart')"
            >{{ t('sources.reprocess') }}</NeButton
          >
        </div>
        <NeTable :aria-label="t('admin.extractionUnits')" card-breakpoint="md">
          <NeTableHead
            ><NeTableHeadCell>{{ t('admin.unit') }}</NeTableHeadCell
            ><NeTableHeadCell>{{ t('common.status') }}</NeTableHeadCell
            ><NeTableHeadCell>{{ t('admin.attempts') }}</NeTableHeadCell
            ><NeTableHeadCell>{{
              t('admin.failure')
            }}</NeTableHeadCell></NeTableHead
          >
          <NeTableBody
            ><NeTableRow v-for="unit in units.data.value.units" :key="unit.id">
              <NeTableCell :data-label="t('admin.unit')"
                >{{ unit.ordinal
                }}<span v-if="unit.locator.kind === 'page'">
                  · {{ t('admin.page', { number: unit.locator.first }) }}</span
                ></NeTableCell
              >
              <NeTableCell :data-label="t('common.status')">{{
                unit.state
              }}</NeTableCell>
              <NeTableCell :data-label="t('admin.attempts')"
                >{{ unit.attempts }} / {{ unit.lifetime_attempts }}</NeTableCell
              >
              <NeTableCell :data-label="t('admin.failure')"
                >{{ unit.error_code || '—'
                }}<span v-if="unit.state === 'retry_wait'">
                  · {{ unit.available_at }}</span
                ></NeTableCell
              >
            </NeTableRow></NeTableBody
          >
        </NeTable>
        <details>
          <summary>{{ t('admin.parser') }}</summary>
          <pre class="overflow-auto rounded-lg bg-elevation-1 p-4 text-sm">{{
            JSON.stringify(units.data.value.parser, null, 2)
          }}</pre>
        </details>
        <div class="flex flex-wrap gap-3">
          <NeButton
            kind="secondary"
            :disabled="!unitOffset"
            @click="unitOffset -= 50"
            >{{ t('common.previous') }}</NeButton
          ><NeButton
            kind="secondary"
            :disabled="units.data.value.units.length < 50"
            @click="unitOffset += 50"
            >{{ t('common.next') }}</NeButton
          >
        </div>
      </section></ResourceState
    >
    <div class="flex flex-wrap gap-3">
      <NeButton kind="secondary" :disabled="!offset" @click="offset -= 50">{{
        t('common.previous')
      }}</NeButton
      ><NeButton
        kind="secondary"
        :disabled="
          (mode === 'jobs'
            ? jobs.data.value?.jobs.length
            : mode === 'schedules'
              ? schedules.data.value?.schedules.length
              : runs.data.value?.runs.length) !== 50
        "
        @click="offset += 50"
        >{{ t('common.next') }}</NeButton
      >
    </div>
    <NeSideDrawer
      :is-shown="drawer"
      :title="t(mode === 'jobs' ? 'admin.enqueue' : 'admin.createSchedule')"
      :close-aria-label="t('common.close')"
      @close="drawer = false"
      ><form class="space-y-5" @submit.prevent="create.mutate()">
        <ErrorNotice
          v-if="create.error.value"
          :error="create.error.value"
        /><NeTextInput
          v-if="mode === 'schedules'"
          v-model="name"
          :label="t('common.name')"
          :disabled="create.isLoading.value"
        /><NeListbox
          v-model="handler"
          :label="t('admin.handler')"
          :options="
            handlers.data.value?.handlers.map((item) => ({
              id: item.name,
              label: item.name,
            })) || []
          "
          :no-options-label="t('common.options')"
          :optional-label="t('common.optional')"
          :disabled="create.isLoading.value"
        /><NeTextArea
          v-model="payload"
          :label="t('admin.payload')"
          :disabled="create.isLoading.value"
        /><NeTextInput
          v-if="mode === 'schedules'"
          v-model="interval"
          :label="t('admin.interval')"
          :disabled="create.isLoading.value"
        /><NeButton
          kind="primary"
          type="submit"
          :loading="create.isLoading.value"
          :disabled="create.isLoading.value"
          >{{
            t(mode === 'jobs' ? 'admin.enqueue' : 'admin.createSchedule')
          }}</NeButton
        >
      </form></NeSideDrawer
    >
  </div>
</template>
