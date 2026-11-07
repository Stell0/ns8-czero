<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import { NeButton, NeTextInput, NeTextArea } from '@nethesis/vue-components'
import { useSession } from '../stores/session'
import { useDraftGuard } from '../composables/draft'
import { ApiError, request, localURL } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
const session = useSession()
const { t } = useI18n(),
  appId = ref('')
const { data, error, isPending } = useResource(
  () => 'agent-connection',
  () =>
    request<{
      available: boolean
      mcp_url: string | null
      name: string
      description: string
    }>('/agents/connection.json', {}, false),
  () => true,
  true,
)
interface Workflow {
  id: string
  title: string
  steps: string[]
}
const capabilities = useResource(
  () => 'agent-capabilities',
  () =>
    request<{
      operations: { name: string }[]
      guidance: { rules: string[]; workflows: Workflow[] }
    }>('/agents/capabilities.json', {}, false),
)
const workflows = computed(
  () =>
    capabilities.data.value?.guidance.workflows.filter(
      (flow) =>
        session.canWrite ||
        ['research', 'structured-research', 'selective-context'].includes(
          flow.id,
        ),
    ) || [],
)
const operationNames = computed(
  () => new Set(capabilities.data.value?.operations.map((op) => op.name)),
)
const compilerAvailable = computed(() =>
  ['compilation_policy_get', 'compilation_status_get'].every((name) =>
    operationNames.value.has(name),
  ),
)
const compilerContext = useResource(
  () => 'compiler-prompt-context',
  async () => {
    const policy = await request<{
      space_id: string
      revision: number
      data: { enabled: boolean; timezone: string; publication_mode: string }
    }>('compilation/policy')
    if (policy.space_id !== session.space?.id) throw new ApiError(409)
    let project = null
    if (!session.space.shared && operationNames.value.has('project_get')) {
      try {
        const stored = await request<{
          data: {
            version: number
            manifest: {
              project_id: string
              space_id: string
              timezone: string
              schedule: Record<string, unknown>
            }
          }
        }>('project')
        if (
          stored.data.manifest.space_id !== session.space.id ||
          stored.data.manifest.project_id !== session.space.id
        )
          throw new ApiError(409)
        project = {
          manifest_version: stored.data.version,
          ...stored.data.manifest,
        }
      } catch (cause) {
        if (!(cause instanceof ApiError && cause.status === 404)) throw cause
      }
    }
    return {
      space_id: session.space.id,
      account_id: session.account,
      policy_revision: policy.revision,
      policy: policy.data,
      project,
    }
  },
  () => compilerAvailable.value,
)
const compilerTasks = computed(() => {
  if (
    !compilerContext.data.value ||
    compilerContext.data.value.space_id !== session.space?.id ||
    compilerContext.data.value.account_id !== session.account
  )
    return []
  const kinds = session.canWrite
    ? [
        'compile',
        'bootstrap',
        'feedback',
        'daily',
        'weekly',
        'chatgpt',
        'external',
        'status',
      ]
    : ['status']
  const required: Record<string, string[]> = {
    compile: [
      'compilation_plan_validate',
      'compilation_apply',
      'compilation_verify',
    ],
    bootstrap: ['compilation_discover', 'compilation_assessment_complete'],
    feedback: [
      'compilation_propose',
      'compilation_source_bindings_get',
      'compilation_tasks_list',
      'compilation_tasks_get',
      'knowledge_search',
      'wiki_pages_get',
      'spaces_get',
    ],
    daily: [
      'compilation_discover',
      'compilation_assessment_complete',
      'compilation_verify',
    ],
    weekly: ['compilation_semantic_select', 'compilation_semantic_review'],
    chatgpt: [
      'compilation_discover',
      'compilation_assessment_complete',
      'compilation_verify',
    ],
    external: [
      'compilation_discover',
      'compilation_assessment_complete',
      'compilation_verify',
    ],
    status: ['compilation_status_get'],
  }
  return kinds
    .filter((id) =>
      required[id].every((name) => operationNames.value.has(name)),
    )
    .map((id) => ({
      id,
      title: t(`agents.compiler.${id}Title`),
      body:
        t('agents.compiler.binding') +
        '\n' +
        JSON.stringify(
          { connection: data.value?.mcp_url, ...compilerContext.data.value },
          null,
          2,
        ) +
        '\n\n' +
        t(`agents.compiler.${id}`) +
        (id === 'chatgpt'
          ? '\n\n' +
            t('agents.compiler.daily') +
            '\n\n' +
            t('agents.compiler.weekly')
          : '') +
        '\n\n' +
        t('agents.compiler.rules'),
    }))
})
const tasks = computed(() => [
  ...compilerTasks.value,
  { id: 'read', title: t('agents.read'), body: t('agents.readTask') },
  ...(session.canWrite
    ? ['create', 'update', 'ingest'].map((id) => ({
        id,
        title: t(`agents.${id}`),
        body: t(`agents.${id}Task`),
      }))
    : []),
  ...workflows.value
    .filter((flow) =>
      ['evidence', 'investigation', 'consolidate'].includes(flow.id),
    )
    .map((flow) => ({
      id: flow.id,
      title: flow.title,
      body: flow.steps.join('\n'),
    })),
])
function instructions(body: string) {
  return (
    t('agents.taskConnection', {
      url: data.value?.mcp_url || '',
      space: session.space?.id || '',
    }) +
    '\n\n' +
    body +
    '\n\n' +
    t('agents.taskRules')
  )
}
const copied = ref(false)
watch(
  () => [session.space?.id, session.account, session.generation],
  () => {
    copied.value = false
  },
)
async function copy(body: string, task = true) {
  copied.value = false
  const current = draft.current()
  try {
    await navigator.clipboard.writeText(task ? instructions(body) : body)
    if (current()) copied.value = true
  } catch {
    /* The read-only field remains selectable. */
  }
}
const draft = useDraftGuard([appId])
const download = useMutation({
  mutation: async () => {
    const current = draft.current()
    const blob = await request<Blob>(
      '/agents/plugin.zip',
      {
        method: 'POST',
        data: { chatgpt_app_id: appId.value },
        responseType: 'blob',
      },
      false,
    )
    if (!current()) return
    if (blob.type !== 'application/zip') throw new ApiError(502)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'c0-plugin.zip'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
})
</script>
<template>
  <div class="space-y-6">
    <p>{{ t('agents.intro') }}</p>
    <ResourceState :error="error" :loading="isPending"
      ><template v-if="data?.available">
        <NeTextInput
          :model-value="data.name"
          :label="t('agents.connectionName')"
          readonly />
        <NeTextInput
          :model-value="data.description"
          :label="t('agents.connectionDescription')"
          readonly />
        <NeTextInput
          :model-value="data.mcp_url || ''"
          :label="t('agents.url')"
          readonly />
        <NeButton kind="secondary" @click="copy(data.mcp_url || '', false)">{{
          t('agents.copyURL')
        }}</NeButton>
        <a :href="localURL('agents/c0-memory.skill')" class="text-link">{{
          t('agents.skill')
        }}</a>
        <form
          v-if="session.ready"
          class="max-w-xl space-y-4"
          @submit.prevent="!download.isLoading.value && download.mutate()"
        >
          <NeTextInput v-model="appId" :label="t('agents.appId')" /><NeButton
            type="submit"
            kind="primary"
            :loading="download.isLoading.value"
            :disabled="download.isLoading.value"
            >{{ t('agents.plugin') }}</NeButton
          ><ErrorNotice
            v-if="download.error.value"
            :error="download.error.value"
          /></form
      ></template>
      <p v-else>{{ t('agents.unavailable') }}</p></ResourceState
    >
    <p>{{ t('agents.compiler.install') }}</p>
    <a
      v-if="!session.ready"
      :href="localURL('auth/sign-in?return_to=agents')"
      class="text-link"
      >{{ t('account.signin') }}</a
    >
    <ResourceState
      v-if="session.ready"
      :error="capabilities.error.value"
      :loading="capabilities.isPending.value"
    >
      <section class="space-y-4">
        <h2 class="text-xl font-medium">{{ t('agents.rules') }}</h2>
        <ul class="list-disc space-y-2 pl-5" lang="en">
          <li
            v-for="rule in capabilities.data.value?.guidance.rules"
            :key="rule"
          >
            {{ rule }}
          </li>
        </ul>
      </section>
      <section class="space-y-4">
        <h2 class="text-xl font-medium">{{ t('agents.workflows') }}</h2>
        <p>{{ t('agents.currentAccess', { role: session.space?.role }) }}</p>
        <details
          v-for="flow in workflows"
          :key="flow.id"
          :data-workflow="flow.id"
          class="rounded-lg border border-default p-4"
          lang="en"
        >
          <summary>{{ flow.title }}</summary>
          <ol class="mt-3 list-decimal space-y-3 pl-5">
            <li v-for="step in flow.steps" :key="step">{{ step }}</li>
          </ol>
        </details>
      </section>
      <p
        v-if="
          !compilerAvailable || (session.canWrite && compilerTasks.length < 8)
        "
      >
        {{ t('agents.compiler.upgrade') }}
      </p>
      <ResourceState
        v-else
        :error="compilerContext.error.value"
        :loading="compilerContext.isPending.value"
      />
      <section class="space-y-4">
        <h2 class="text-xl font-medium">{{ t('agents.tasks') }}</h2>
        <details
          v-for="task in tasks"
          :key="task.id"
          :data-task="task.id"
          class="rounded-lg border border-default p-4"
        >
          <summary>{{ task.title }}</summary>
          <div class="mt-4 space-y-3">
            <NeTextArea
              :model-value="instructions(task.body)"
              readonly
              :label="t('agents.instructions')"
              :rows="8"
            /><NeButton kind="secondary" @click="copy(task.body)">{{
              t('agents.copy')
            }}</NeButton>
          </div>
        </details>
        <p v-if="copied" role="status">{{ t('agents.copied') }}</p>
      </section>
    </ResourceState>
  </div>
</template>
