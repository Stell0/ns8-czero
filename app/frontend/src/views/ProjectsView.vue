<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { request } from '../api/client'
import { useResource } from '../api/queries'
import { useSession } from '../stores/session'
import ResourceState from '../components/ResourceState.vue'
const { t } = useI18n(),
  session = useSession()
interface Manifest {
  space_id: string
  project_id: string
  name: string
  description: string
  purpose: string
  scope: string
  language: string
  timezone: string
  schedule: { enabled: boolean }
}
interface RecordEntry {
  id: string
  data: Record<string, unknown>
}
const { data, error, isPending } = useResource(
  () => 'project',
  async () => {
    const stored = await request<{
      data: { version: number; manifest: Manifest }
    }>('project')
    if (
      stored.data.manifest.space_id !== session.space?.id ||
      stored.data.manifest.project_id !== session.space.id
    )
      throw new Error('Project binding mismatch')
    const kinds = [
      'topic_v1',
      'connector_sync_v1',
      'queue_v1',
      'monitor_cycle_v1',
      'run_v1',
    ]
    const records = await Promise.all(
      kinds.map((kind) =>
        request<{ objects: RecordEntry[] }>(
          `project/records?kind=${kind}&limit=100&descending=${['run_v1', 'monitor_cycle_v1'].includes(kind)}`,
        ),
      ),
    )
    const diagnostics = await request<{
      project_id: string
      manifest_version: number
      connectors: {
        connector_id: string
        current_definition_verified: boolean
      }[]
      last_successful_runs: Record<string, RecordEntry | null>
      structural_findings: number
      errors: (RecordEntry & { type_name: string })[]
      errors_may_be_incomplete: boolean
      latest_daily_report: {
        data: {
          wiki_page_id: string
          wiki_revision: number
          local_date: string
          coverage_complete: boolean
        }
      } | null
    }>('project/diagnostics')
    if (
      diagnostics.project_id !== session.space.id ||
      diagnostics.manifest_version !== stored.data.version
    )
      throw new Error('Project binding mismatch')
    const report = diagnostics.latest_daily_report?.data
    if (
      report &&
      (!/^[0-9a-f-]{36}$/i.test(report.wiki_page_id) ||
        !Number.isSafeInteger(report.wiki_revision) ||
        report.wiki_revision < 1)
    )
      throw new Error('Invalid report identity')
    const verified = new Set(
      diagnostics.connectors
        .filter((item) => item.current_definition_verified)
        .map((item) => item.connector_id),
    )
    return {
      version: stored.data.version,
      diagnostics,
      runs: records[4].objects,
      manifest: stored.data.manifest,
      topics: records[0].objects,
      sync: records[1].objects.map((record) => ({
        ...record,
        data: {
          ...record.data,
          status: verified.has(String(record.data.connector_id))
            ? record.data.status
            : t('projects.unverified'),
          last_success_at: verified.has(String(record.data.connector_id))
            ? record.data.last_success_at
            : null,
        },
      })),
      work: records[2].objects,
      monitoring: records[3].objects,
      report,
    }
  },
  () => !!session.space && !session.space.shared,
)
</script>
<template>
  <p v-if="session.space?.shared">{{ t('projects.choose') }}</p>
  <ResourceState v-else :error="error" :loading="isPending"
    ><div v-if="data" class="space-y-8">
      <div>
        <h2 class="text-2xl font-medium">{{ data.manifest.name }}</h2>
        <p>{{ data.manifest.description }}</p>
      </div>
      <section>
        <h2 class="text-xl font-medium">{{ t('projects.purpose') }}</h2>
        <p class="mt-3 whitespace-pre-wrap">{{ data.manifest.purpose }}</p>
        <p>{{ data.manifest.scope }}</p>
        <p class="mt-3 text-text-secondary">
          {{
            t('projects.configuration', {
              version: data.version,
              language: data.manifest.language,
              timezone: data.manifest.timezone,
            })
          }}
        </p>
        <p>
          {{
            t(
              data.manifest.schedule.enabled
                ? 'projects.scheduleRequested'
                : 'projects.scheduleDisabled',
            )
          }}
        </p>
      </section>
      <section
        v-for="section in [
          'topics',
          'sync',
          'monitoring',
          'work',
          'runs',
        ] as const"
        :key="section"
      >
        <h2 class="mb-3 text-xl font-medium">
          {{ t(section === 'work' ? 'nav.work' : `projects.${section}`) }}
        </h2>
        <ul class="space-y-3">
          <li
            v-for="record in data[section]"
            :key="record.id"
            class="rounded-lg border border-default p-4"
          >
            <dl class="grid gap-2 sm:grid-cols-2">
              <template v-for="(value, key) in record.data" :key="key"
                ><dt>{{ key }}</dt>
                <dd class="break-words">{{ value }}</dd></template
              >
            </dl>
          </li>
        </ul>
        <p v-if="data[section].length === 100" class="mt-3 text-text-secondary">
          {{ t('projects.incomplete') }}
        </p>
        <p v-else-if="!data[section].length">{{ t('common.empty') }}</p>
      </section>
      <section class="space-y-3">
        <h2 class="text-xl font-medium">{{ t('projects.diagnostics') }}</h2>
        <p>
          {{
            t('projects.findings', {
              count: data.diagnostics.structural_findings,
            })
          }}
        </p>
        <ul>
          <li
            v-for="(run, kind) in data.diagnostics.last_successful_runs"
            :key="kind"
          >
            {{ t('projects.lastSuccess', { kind }) }}:
            {{ run?.data.local_cycle_date || t('common.empty') }}
          </li>
        </ul>
        <ul class="space-y-3">
          <li
            v-for="entry in data.diagnostics.errors"
            :key="entry.id"
            class="rounded-lg border border-default p-4"
          >
            <p>{{ entry.type_name }}</p>
            <dl class="grid gap-2 sm:grid-cols-2">
              <template v-for="(value, key) in entry.data" :key="key"
                ><dt>{{ key }}</dt>
                <dd class="break-words">{{ value }}</dd></template
              >
            </dl>
          </li>
        </ul>
        <p v-if="data.diagnostics.errors_may_be_incomplete">
          {{ t('projects.incomplete') }}
        </p>
      </section>
      <section>
        <h2 class="mb-3 text-xl font-medium">{{ t('projects.reports') }}</h2>
        <RouterLink
          v-if="data.report"
          :to="{
            path: `/wiki/${data.report.wiki_page_id}`,
            query: { revision: data.report.wiki_revision },
          }"
          class="text-link"
          >{{ data.report.local_date }}</RouterLink
        >
        <p v-if="data.report">
          {{
            t(
              data.report.coverage_complete
                ? 'projects.covered'
                : 'projects.partial',
            )
          }}
        </p>
        <p v-else>{{ t('common.empty') }}</p>
      </section>
      <p class="text-text-secondary">{{ t('projects.observations') }}</p>
    </div></ResourceState
  >
</template>
