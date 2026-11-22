<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import { NeButton, NeCheckbox } from '@nethesis/vue-components'
import { StorageSerializers, useSessionStorage } from '@vueuse/core'
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
  draft_id?: string
  profile?: { display_name?: string; username?: string }
  review_id?: string
  review_requested?: boolean
  csrf_token: string
  background_supported?: boolean
  background_ready?: boolean
  next?: string
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
watch(data, (value) => {
  if (value?.next === '/oauth/consent') location.assign(localURL(value.next))
})
const needsReview = computed(
  () =>
    connecting.value &&
    !!data.value &&
    (!data.value.approved ||
      data.value.eligible_scopes?.some(
        (scope) => !data.value?.allowed_scopes?.includes(scope),
      )),
)
const eligible = computed(() =>
  needsReview.value && session.isAdmin
    ? (data.value?.eligible_scopes || []).filter(
        (scope) =>
          !reviewed.value?.value.descriptor.scope_ceiling ||
          reviewed.value.value.descriptor.scope_ceiling.includes(scope),
      )
    : connecting.value
      ? (data.value?.eligible_scopes || []).filter((scope) =>
          data.value?.allowed_scopes?.includes(scope),
        )
      : data.value?.eligible_scopes || [],
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
  allowed_scopes?: string[]
}
const reviewed = ref<{ value: Review; existing?: Existing }>()
const choices = ref<Record<string, boolean>>({}),
  background = ref(false)
interface ConsentDraft {
  id: string
  choices: Record<string, boolean>
  background: boolean
}
const saved = useSessionStorage<ConsentDraft | null>('c0-consent-draft', null, {
  serializer: StorageSerializers.object,
})
let initialized: Consent | undefined
watch([data, eligible], ([value]) => {
  if (!value) return
  const id = value.draft_id || value.review_id
  const sameRequest =
    value === initialized ||
    (id && id === (initialized?.draft_id || initialized?.review_id))
  const savedChoices =
    value.draft_id && saved.value?.id === value.draft_id
      ? saved.value
      : undefined
  const stored = sameRequest ? choices.value : savedChoices?.choices
  choices.value = Object.fromEntries(
    eligible.value.map((scope) => [scope, stored?.[scope] ?? true]),
  )
  background.value =
    !!value.background_supported &&
    (sameRequest ? background.value : (savedChoices?.background ?? true))
  initialized = value
})
watch(
  [choices, background],
  () => {
    if (!data.value?.draft_id) return
    saved.value = {
      id: data.value.draft_id,
      choices: { ...choices.value },
      background: background.value,
    }
  },
  { deep: true },
)
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
    needsReview.value && session.isAdmin
      ? `${data.value?.metadata_url || ''}:${data.value?.callback || ''}`
      : '',
  (identity) => {
    if (identity && data.value?.metadata_url) preview.mutate()
  },
  { immediate: true },
)
async function approveApplication() {
  const review = reviewed.value
  if (!review || !data.value?.review_id || !selected.value.length)
    throw new ApiError(409)
  if (
    review.value.descriptor.scope_ceiling &&
    selected.value.some(
      (scope) => !review.value.descriptor.scope_ceiling!.includes(scope),
    )
  )
    throw new ApiError(422)
  await request(
    '/oauth/connect/approve',
    {
      method: 'POST',
      data: {
        metadata_digest: review.value.metadata_digest,
        review_id: data.value.review_id,
        scopes: selected.value,
        expected_revision: review.existing?.revision,
      },
    },
    false,
  )
}
const expanding = computed(
  () =>
    connecting.value &&
    selected.value.some(
      (scope) => !data.value?.allowed_scopes?.includes(scope),
    ),
)
const reviewRequest = useMutation({
  mutation: async () => {
    await request('/oauth/connect/review', { method: 'POST', data: {} }, false)
    await refetch()
  },
})
const canSubmit = computed(
  () =>
    !!data.value &&
    !!selected.value.length &&
    !submit.isLoading.value &&
    !preview.isLoading.value &&
    (!expanding.value || (session.isAdmin && !!reviewed.value)),
)
const submit = useMutation({
  mutation: async (approve: boolean) => {
    const current = draft.current()
    const value = data.value
    if (!value) return
    if (!connecting.value && !value.draft_id)
      throw new Error('Missing consent draft')
    if (approve && expanding.value) {
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
        data: connecting.value
          ? { scopes: selected.value }
          : signIn
            ? { draft_id: value.draft_id, scopes: selected.value }
            : {
                draft_id: value.draft_id,
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
    else if (!connecting.value && !signIn && result.redirect_uri) {
      saved.value = null
      location.assign(result.redirect_uri)
    } else throw new Error('Invalid consent destination')
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
        <p v-if="data.profile?.display_name || data.profile?.username">
          {{
            t('consent.signedIn', {
              name: data.profile.display_name || data.profile.username,
            })
          }}
        </p>
        <p v-if="data.scopes?.includes('c0:read')">
          {{ t('consent.readBoundary') }}
        </p>
      </div>
      <fieldset class="min-w-0 space-y-3" :disabled="submit.isLoading.value">
        <legend class="sr-only">{{ t('consent.permissions') }}</legend>
        <div v-for="scope in data.scopes" :key="scope" class="space-y-1">
          <NeCheckbox
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
          <p
            v-if="scope === 'c0:write' || scope === 'c0:admin'"
            class="text-sm text-text-secondary"
          >
            {{
              t(
                scope === 'c0:write'
                  ? 'consent.writeHelp'
                  : 'consent.manageHelp',
              )
            }}
          </p>
        </div>
      </fieldset>
      <p v-if="!connecting && !background" class="text-sm text-text-secondary">
        {{ t('consent.sessionHelp') }}
      </p>
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
      <dl class="space-y-1 text-sm">
        <dt class="font-medium">{{ t('consent.callback') }}</dt>
        <dd class="break-all">{{ data.callback }}</dd>
      </dl>
      <ErrorNotice
        v-if="
          submit.error.value || preview.error.value || reviewRequest.error.value
        "
        :error="
          submit.error.value || preview.error.value || reviewRequest.error.value
        "
      />
      <div v-if="connecting && needsReview" class="space-y-3">
        <p>
          {{
            t(
              session.isAdmin
                ? 'consent.adminApproval'
                : data.review_requested
                  ? 'consent.pending'
                  : 'consent.extraApproval',
            )
          }}
        </p>
        <p v-if="expanding && reviewed?.existing">
          {{ t('consent.reapproval') }}
        </p>
        <NeButton
          v-if="session.isAdmin && preview.error.value"
          kind="secondary"
          :disabled="preview.isLoading.value || submit.isLoading.value"
          @click="preview.mutate()"
          >{{ t('common.reload') }}</NeButton
        >
        <NeButton
          v-else-if="!session.isAdmin && data.review_requested"
          kind="secondary"
          @click="refetch()"
          >{{ t('common.reload') }}</NeButton
        >
        <NeButton
          v-else-if="!session.isAdmin"
          kind="secondary"
          :loading="reviewRequest.isLoading.value"
          @click="reviewRequest.mutate()"
          >{{ t('consent.requestApproval') }}</NeButton
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
              expanding && session.isAdmin
                ? 'consent.approveContinue'
                : connecting
                  ? 'consent.continueWithSelected'
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
