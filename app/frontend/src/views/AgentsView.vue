<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeLink,
  NeRadioSelection,
  NeTextInput,
  NeTextArea,
} from '@nethesis/vue-components'
import { useSession } from '../stores/session'
import { useDraftGuard } from '../composables/draft'
import { ApiError, request, localURL } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
const session = useSession()
const { t } = useI18n(),
  appId = ref('')
const assistants = [
  {
    id: 'chatgpt',
    label: 'ChatGPT',
    url: 'https://chatgpt.com/plugins?directoryTab=personal',
    skills: 'https://chatgpt.com/skills',
    download: 'agents/c0-memory.skill',
  },
  {
    id: 'claude',
    label: 'Claude',
    url: 'https://claude.ai/',
    download: 'agents/c0-skill.zip',
  },
  {
    id: 'grok',
    label: 'Grok',
    url: 'https://grok.com/connectors',
    download: 'agents/c0-skill.md',
  },
  {
    id: 'gemini',
    label: 'Gemini',
    url: 'https://gemini.google.com/',
    download: 'agents/c0-skill.md',
  },
]
const assistant = ref('')
const provider = computed(() =>
  assistants.find(({ id }) => id === assistant.value),
)
const advanced = ref(false)
const { data, error, isPending } = useResource(
  () => 'agent-connection',
  () =>
    request<{
      available: boolean
      mcp_url: string | null
      name: string
    }>('/agents/connection.json', {}, false),
  () => true,
  true,
)
const firstQuestion = computed(() =>
  t('agents.setup.firstQuestion', {
    url: data.value?.mcp_url || '',
    space: session.space
      ? t('agents.setup.useSpace', {
          name: session.space.name,
          id: session.space.id,
        })
      : t('agents.setup.chooseSpace'),
  }),
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
  () => advanced.value,
)
const workflows = computed(
  () =>
    capabilities.data.value?.guidance.workflows.filter(
      (flow) =>
        session.canWrite ||
        [
          'research',
          'structured-research',
          'selective-context',
          'cross-space-navigation',
        ].includes(flow.id),
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
  () => advanced.value && compilerAvailable.value,
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
const copied = ref('')
watch(
  () => [
    session.space?.id,
    session.account,
    session.generation,
    assistant.value,
  ],
  () => {
    copied.value = ''
  },
)
async function copy(body: string, target: string) {
  copied.value = ''
  const current = draft.current()
  try {
    await navigator.clipboard.writeText(body)
    if (current()) copied.value = target
  } catch {
    /* The read-only field remains selectable. */
  }
}
const draft = useDraftGuard([appId, assistant, advanced])
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
  <div class="max-w-3xl space-y-6">
    <ResourceState :error="error" :loading="isPending">
      <template v-if="data?.available && data.mcp_url">
        <NeRadioSelection
          v-model="assistant"
          :label="t('agents.setup.assistant')"
          :options="assistants"
          card
          grid-style="grid-cols-2 gap-3 sm:grid-cols-4"
        />
        <ol
          v-if="provider"
          class="mt-6 space-y-6 rounded-lg border border-default p-4 sm:p-6"
        >
          <li class="space-y-3">
            <h2 class="text-lg">{{ t('agents.setup.connect') }}</h2>
            <p>
              {{ t(`agents.setup.${assistant}.connect`, { name: data.name }) }}
            </p>
            <NeLink
              :href="provider.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ t('agents.setup.open', { name: provider.label }) }}
            </NeLink>
            <NeTextInput
              :model-value="data.mcp_url"
              :label="t('agents.url')"
              readonly
            />
            <div class="flex flex-wrap items-center gap-3">
              <NeButton kind="secondary" @click="copy(data.mcp_url, 'url')">
                {{ t('agents.copyURL') }}
              </NeButton>
              <p role="status" class="text-sm">
                {{ copied === 'url' ? t('agents.setup.urlCopied') : '' }}
              </p>
            </div>
            <p class="text-sm text-text-secondary">
              {{ t('agents.setup.authorize') }}
            </p>
            <p class="text-sm text-text-secondary">
              {{ t(`agents.setup.${assistant}.requirements`) }}
            </p>
          </li>
          <li class="space-y-3 border-t border-default pt-4">
            <h2 class="text-lg">{{ t('agents.setup.installSkill') }}</h2>
            <p>{{ t(`agents.setup.${assistant}.install`) }}</p>
            <div class="flex flex-wrap gap-x-4 gap-y-2">
              <NeLink :href="localURL(provider.download)">{{
                t('agents.skill')
              }}</NeLink>
              <NeLink
                v-if="provider.skills"
                :href="provider.skills"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ t('agents.setup.openSkills') }}
              </NeLink>
            </div>
          </li>
          <li class="space-y-3 border-t border-default pt-4">
            <h2 class="text-lg">{{ t('agents.setup.try') }}</h2>
            <p>{{ t('agents.setup.tryDescription') }}</p>
            <NeTextArea
              :model-value="firstQuestion"
              :label="t('agents.setup.question')"
              readonly
              :rows="5"
            />
            <div class="flex flex-wrap items-center gap-3">
              <NeButton
                kind="secondary"
                @click="copy(firstQuestion, 'question')"
              >
                {{ t('agents.setup.copyQuestion') }}
              </NeButton>
              <p role="status" class="text-sm">
                {{
                  copied === 'question' ? t('agents.setup.questionCopied') : ''
                }}
              </p>
            </div>
          </li>
        </ol>
      </template>
      <p v-else>{{ t('agents.unavailable') }}</p>
    </ResourceState>
    <RouterLink v-if="session.ready" to="/account" class="text-link">
      {{ t('agents.setup.manage') }}
    </RouterLink>
    <a
      v-else
      :href="localURL('auth/sign-in?return_to=agents')"
      class="text-link"
    >
      {{ t('account.signin') }}
    </a>
    <details
      v-if="session.ready"
      :open="advanced"
      class="rounded-lg border border-default p-4"
      @toggle="advanced = ($event.target as HTMLDetailsElement).open"
    >
      <summary>{{ t('agents.setup.advanced') }}</summary>
      <div v-if="advanced" class="mt-4 space-y-6">
        <form
          v-if="assistant === 'chatgpt' && data?.available"
          class="max-w-xl space-y-3"
          @submit.prevent="!download.isLoading.value && download.mutate()"
        >
          <h2 class="text-lg">{{ t('agents.setup.chatgpt.packageTitle') }}</h2>
          <p>{{ t('agents.setup.chatgpt.packageHelp') }}</p>
          <NeTextInput v-model="appId" :label="t('agents.appId')" />
          <NeButton
            type="submit"
            kind="secondary"
            :loading="download.isLoading.value"
            :disabled="download.isLoading.value || !appId.trim()"
          >
            {{ t('agents.plugin') }}
          </NeButton>
          <ErrorNotice
            v-if="download.error.value"
            :error="download.error.value"
          />
        </form>
        <RouterLink to="/account" class="text-link">
          {{ t('agents.automationKeys') }}
        </RouterLink>
        <ResourceState
          :error="capabilities.error.value"
          :loading="capabilities.isPending.value"
        >
          <section class="mt-4 space-y-4">
            <h2 class="text-lg">{{ t('agents.rules') }}</h2>
            <ul class="list-disc space-y-2 pl-5" lang="en">
              <li
                v-for="rule in capabilities.data.value?.guidance.rules"
                :key="rule"
              >
                {{ rule }}
              </li>
            </ul>
          </section>
          <section class="mt-4 space-y-4">
            <h2 class="text-lg">{{ t('agents.workflows') }}</h2>
            <p>
              {{ t('agents.currentAccess', { role: session.space?.role }) }}
            </p>
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
          <section class="mt-4 space-y-4">
            <h2 class="text-lg">{{ t('agents.tasks') }}</h2>
            <p
              v-if="
                !compilerAvailable ||
                (session.canWrite && compilerTasks.length < 8)
              "
            >
              {{ t('agents.compiler.upgrade') }}
            </p>
            <ResourceState
              v-else
              :error="compilerContext.error.value"
              :loading="compilerContext.isPending.value"
            />
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
                />
                <NeButton
                  kind="secondary"
                  @click="copy(instructions(task.body), task.id)"
                >
                  {{ t('agents.copy') }}
                </NeButton>
                <p role="status" class="text-sm">
                  {{ copied === task.id ? t('agents.copied') : '' }}
                </p>
              </div>
            </details>
          </section>
        </ResourceState>
      </div>
    </details>
  </div>
</template>
