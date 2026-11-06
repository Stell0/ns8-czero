<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import { NeButton, NeCheckbox } from '@nethesis/vue-components'
import { useDraftGuard } from '../composables/draft'
import { useSession } from '../stores/session'
import { ApiError, localURL, request } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
const session = useSession()
const route = useRoute(),
  { t } = useI18n()
const connecting = computed(() => route.params.flow === 'connect')
interface Consent {
  client_name?: string
  metadata_url?: string
  client_id?: string
  callback: string
  scopes: string[]
  eligible_scopes?: string[]
  allowed_scopes?: string[]
  approved?: boolean
  csrf_token: string
  background_supported?: boolean
  background_requested?: boolean
  background_ready?: boolean
  connection_idle_seconds?: number
}
const { data, error, isPending, refetch } = useResource(
  () => `consent:${route.params.flow}`,
  () =>
    request<Consent>(
      connecting.value ? '/oauth/connect/request' : '/oauth/consent/request',
      connecting.value ? { method: 'POST', data: {} } : {},
      false,
    ),
)
const eligible = computed(() =>
  connecting.value && session.isAdmin && !data.value?.approved
    ? (data.value?.scopes || []).filter(
        (scope) =>
          !reviewed.value?.value.descriptor.scope_ceiling ||
          reviewed.value.value.descriptor.scope_ceiling.includes(scope),
      )
    : data.value?.eligible_scopes || data.value?.allowed_scopes || [],
)
interface Review {
  metadata_digest: string
  descriptor: {
    client_id: string
    client_name: string
    redirect_uris: string[]
    scope_ceiling?: string[]
  }
}
interface Existing {
  client_id: string
  metadata_url: string
  enabled: boolean
  revision: number
}
const reviewed = ref<{ value: Review; existing?: Existing }>()
const choices = ref<Record<string, boolean>>({}),
  background = ref(false)
let initialized = false
watch([data, eligible], ([value]) => {
  if (!value) return
  choices.value = Object.fromEntries(
    eligible.value.map((scope) => [
      scope,
      initialized
        ? !!choices.value[scope]
        : !connecting.value || scope === 'c0:read',
    ]),
  )
  initialized = true
  background.value =
    !!value?.background_supported && !!value.background_requested
})
const selected = computed(() =>
  Object.keys(choices.value).filter((scope) => choices.value[scope]),
)
const draft = useDraftGuard([data, selected, background])
const preview = useMutation({
  mutation: async () => {
    if (!session.isAdmin || !data.value?.metadata_url) return
    reviewed.value = undefined
    const current = draft.start()
    const identity = data.value.metadata_url,
      callback = data.value.callback
    const value = await request<Review>(
      'oauth/cimd/preview',
      { method: 'POST', data: { metadata_url: identity } },
      false,
    )
    const clients = await request<{ clients: Existing[] }>(
      'oauth/cimd',
      {},
      false,
    )
    if (
      value.descriptor.client_id !== identity ||
      !value.descriptor.redirect_uris.includes(callback)
    )
      throw new ApiError(409)
    const existing = clients.clients.find(
      (client) => client.metadata_url === identity,
    )
    if (existing && !existing.enabled) throw new ApiError(409)
    if (current()) reviewed.value = { value, existing }
  },
})
watch(
  () =>
    connecting.value && !data.value?.approved && session.isAdmin
      ? `${data.value?.metadata_url || ''}:${data.value?.callback || ''}`
      : '',
  (identity) => {
    if (identity && data.value?.metadata_url) preview.mutate()
  },
  { immediate: true },
)
async function approveApplication() {
  const review = reviewed.value
  if (!review || !data.value || !selected.value.length) throw new ApiError(409)
  if (
    review.value.descriptor.scope_ceiling &&
    selected.value.some(
      (scope) => !review.value.descriptor.scope_ceiling!.includes(scope),
    )
  )
    throw new ApiError(422)
  await request(
    `oauth/cimd/clients${review.existing ? '/' + review.existing.client_id : ''}`,
    {
      method: review.existing ? 'PUT' : 'POST',
      data: {
        metadata_digest: review.value.metadata_digest,
        allowed_scopes: [...selected.value],
        ...(review.existing
          ? { expected_revision: review.existing.revision }
          : { metadata_url: data.value.metadata_url }),
      },
    },
    false,
  )
}
const canSubmit = computed(
  () =>
    !!data.value &&
    !!selected.value.length &&
    !submit.isLoading.value &&
    !preview.isLoading.value &&
    (!connecting.value ||
      data.value.approved ||
      (session.isAdmin && !!reviewed.value)),
)
const submit = useMutation({
  mutation: async (approve: boolean) => {
    const current = draft.current()
    const value = data.value
    if (!value) return
    if (approve && connecting.value && !value.approved) {
      await approveApplication()
      if (!current()) return
    }
    const signIn =
      approve &&
      background.value &&
      !value.background_ready &&
      !connecting.value
    const path = connecting.value
      ? '/oauth/connect/continue'
      : signIn
        ? '/oauth/consent/background'
        : '/oauth/consent'
    const result = await request<{ next?: string; redirect_uri?: string }>(
      path,
      {
        method: 'POST',
        data:
          connecting.value || signIn
            ? { scopes: selected.value }
            : {
                approve,
                scopes: selected.value,
                persistent: approve && background.value,
              },
      },
      false,
    )
    if (!current()) return
    if (signIn && result.next === '/auth/login')
      location.assign(localURL(result.next))
    else if (connecting.value && result.next === '/oauth/consent')
      location.assign(localURL(result.next))
    else if (!connecting.value && !signIn && result.redirect_uri)
      location.assign(result.redirect_uri)
    else throw new Error('Invalid consent destination')
  },
})
</script>
<template>
  <ResourceState :error="error" :loading="isPending">
    <form
      v-if="data"
      class="min-w-0 space-y-6"
      @submit.prevent="canSubmit && submit.mutate(true)"
    >
      <div class="space-y-3">
        <h2 class="text-xl font-medium">
          {{
            data.client_name ||
            reviewed?.value.descriptor.client_name ||
            data.metadata_url
          }}
        </h2>
        <p
          v-if="data.metadata_url"
          class="break-all text-sm text-text-secondary"
        >
          {{ data.metadata_url }}
        </p>
        <p>{{ t('consent.permissions') }}</p>
      </div>
      <fieldset class="min-w-0 space-y-3" :disabled="submit.isLoading.value">
        <legend class="sr-only">{{ t('consent.permissions') }}</legend>
        <NeCheckbox
          v-for="scope in data.scopes"
          :key="scope"
          v-model="choices[scope]"
          :label="
            t(`account.${scope === 'c0:admin' ? 'manage' : scope.slice(3)}`)
          "
          :disabled="
            submit.isLoading.value ||
            preview.isLoading.value ||
            !eligible.includes(scope)
          "
        />
      </fieldset>
      <div v-if="data.background_supported" class="space-y-3">
        <NeCheckbox
          v-model="background"
          :label="t('consent.background')"
          :disabled="submit.isLoading.value"
        />
        <p class="text-sm text-text-secondary">
          {{
            t('consent.backgroundHelp', {
              days: (data.connection_idle_seconds || 0) / 86400,
            })
          }}
        </p>
      </div>
      <details>
        <summary class="cursor-pointer text-link">
          {{ t('common.details') }}
        </summary>
        <p class="mt-3 break-all text-sm">
          {{ t('consent.callback') }}: {{ data.callback }}
        </p>
      </details>
      <ErrorNotice
        v-if="submit.error.value || preview.error.value"
        :error="submit.error.value || preview.error.value"
      />
      <div v-if="connecting && !data.approved" class="space-y-3">
        <p>
          {{ t(session.isAdmin ? 'consent.adminApproval' : 'consent.pending') }}
        </p>
        <NeButton
          v-if="session.isAdmin && preview.error.value"
          kind="secondary"
          :disabled="preview.isLoading.value || submit.isLoading.value"
          @click="preview.mutate()"
          >{{ t('common.reload') }}</NeButton
        >
        <NeButton
          v-else-if="!session.isAdmin"
          kind="secondary"
          @click="refetch()"
          >{{ t('common.reload') }}</NeButton
        >
      </div>
      <div class="flex flex-wrap gap-4">
        <NeButton
          kind="primary"
          type="submit"
          :disabled="!canSubmit"
          :loading="submit.isLoading.value || preview.isLoading.value"
        >
          {{
            t(
              connecting && !data.approved && session.isAdmin
                ? 'consent.approveContinue'
                : background && !data.background_ready
                  ? 'consent.continue'
                  : 'consent.authorize',
            )
          }}
        </NeButton>
        <NeButton
          v-if="!connecting"
          kind="secondary"
          :disabled="submit.isLoading.value"
          @click="submit.mutate(false)"
          >{{ t('consent.deny') }}</NeButton
        >
      </div>
    </form>
  </ResourceState>
  <RouterLink to="/agents" class="text-link">{{
    t('consent.back')
  }}</RouterLink>
</template>
