<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeListbox,
  NeTextInput,
  NeCheckbox,
  NeSideDrawer,
  NeModal,
} from '@nethesis/vue-components'
import { useDraftGuard } from '../composables/draft'
import { keyRequest } from '../api/key-form'
import { boundary, request } from '../api/client'
import { useResource } from '../api/queries'
import { useSession } from '../stores/session'
import { usePreferences } from '../stores/preferences'
import ResourceState from '../components/ResourceState.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
function date(value: string | null | undefined) {
  return value
    ? new Date(value).toLocaleString(preferences.language)
    : t('account.notRecorded')
}
const session = useSession(),
  preferences = usePreferences(),
  { t } = useI18n()
interface Connection {
  id: string
  client_name: string
  scopes: string[]
  persistent: boolean
  expires_at: string
  last_used_at: string | null
  idle_until: string
}
interface Key {
  id: string
  name: string
  scopes: string[]
  revoked_at: string | null
  expires_at: string | null
}
const connections = useResource(
  () => 'connections',
  () => request<{ connections: Connection[] }>('oauth/connections', {}, false),
)
const keys = useResource(
  () => 'api-keys',
  () => request<{ api_keys: Key[] }>('api-keys', {}, false),
)
const create = ref(false),
  name = ref(''),
  days = ref('90'),
  write = ref(false),
  selected = ref<Record<string, boolean>>({}),
  secret = ref('')
const confirm = ref<{ id: string; kind: 'key' | 'connection'; name: string }>()
const clearSecret = boundary.onClear(() => {
  secret.value = ''
  create.value = false
  selected.value = {}
  name.value = ''
})
onBeforeUnmount(() => {
  keyDraft++
  secret.value = ''
  clearSecret()
})
let keyDraft = 0
function openCreate() {
  keyDraft++
  name.value = ''
  days.value = '90'
  write.value = false
  selected.value = {}
  secret.value = ''
  create.value = true
}
function closeCreate() {
  keyDraft++
  create.value = false
  secret.value = ''
}
const creation = useMutation({
  mutation: async () => {
    if (!create.value || secret.value) return
    const draft = keyDraft
    const result = await request<{ key: string }>(
      'api-keys',
      {
        method: 'POST',
        data: keyRequest(
          {
            name: name.value,
            days: days.value,
            write: write.value,
            selected: selected.value,
          },
          session.spaces,
        ),
      },
      false,
    )
    if (draft === keyDraft && create.value) {
      secret.value = result.key
    }
    await keys.refetch()
    // Do not return the secret to Colada's mutation cache.
  },
})
const confirmationDraft = useDraftGuard([confirm])
const removal = useMutation({
  mutation: async () => {
    if (!confirm.value) return
    const current = confirmationDraft.current()
    const item = { ...confirm.value }
    await request(
      `${item.kind === 'key' ? 'api-keys' : 'oauth/connections'}/${item.id}`,
      { method: 'DELETE' },
      false,
    )
    if (current()) confirm.value = undefined
    await (item.kind === 'key' ? keys.refetch() : connections.refetch())
  },
})
</script>
<template>
  <div class="space-y-8">
    <section class="space-y-4">
      <h2 class="text-xl font-medium">{{ t('account.identity') }}</h2>
      <p>{{ session.profile?.username }}</p>
      <p class="text-sm text-text-secondary">
        {{
          t(
            session.profile?.browser_session?.remembered
              ? 'account.rememberedSession'
              : 'account.ordinarySession',
          )
        }}
      </p>
      <NeButton kind="secondary" @click="session.logout()">{{
        t('account.signout')
      }}</NeButton>
    </section>
    <div class="grid gap-4 sm:grid-cols-2">
      <NeListbox
        v-model="preferences.language"
        :label="t('account.language')"
        :options="[
          { id: 'en', label: 'English' },
          { id: 'it', label: 'Italiano' },
        ]"
        :no-options-label="t('common.options')"
        :optional-label="t('common.optional')"
      />
      <NeListbox
        v-model="preferences.theme"
        :label="t('account.theme')"
        :options="
          ['system', 'light', 'dark'].map((id) => ({
            id,
            label: t(`account.${id}`),
          }))
        "
        :no-options-label="t('common.options')"
        :optional-label="t('common.optional')"
      />
    </div>
    <section class="space-y-4">
      <h2 class="text-xl font-medium">{{ t('account.connections') }}</h2>
      <ResourceState
        :error="connections.error.value"
        :loading="connections.isPending.value"
        :empty="connections.data.value?.connections.length === 0"
      >
        <ul class="space-y-4">
          <li
            v-for="connection in connections.data.value?.connections"
            :key="connection.id"
            class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default p-4"
          >
            <div>
              <h3>{{ connection.client_name }}</h3>
              <p class="text-sm text-text-secondary">
                {{ connection.scopes.join(', ') }}
              </p>
              <p class="text-sm text-text-secondary">
                {{
                  t(
                    connection.persistent
                      ? 'account.backgroundUntil'
                      : 'account.sessionUntil',
                    {
                      date: date(
                        connection.persistent
                          ? connection.idle_until
                          : connection.expires_at,
                      ),
                    },
                  )
                }}
              </p>
              <p class="text-sm text-text-secondary">
                {{
                  t('account.lastUsed', { date: date(connection.last_used_at) })
                }}
              </p>
            </div>
            <NeButton
              kind="secondary"
              @click="
                confirm = {
                  id: connection.id,
                  kind: 'connection',
                  name: connection.client_name,
                }
              "
              >{{ t('account.disconnect') }}</NeButton
            >
          </li>
        </ul>
      </ResourceState>
    </section>
    <section class="space-y-4">
      <h2 class="text-xl font-medium">{{ t('account.keys') }}</h2>
      <NeButton kind="primary" @click="openCreate">{{
        t('account.createKey')
      }}</NeButton>
      <ResourceState
        :error="keys.error.value"
        :loading="keys.isPending.value"
        :empty="keys.data.value?.api_keys.length === 0"
        ><ul class="space-y-4">
          <li
            v-for="key in keys.data.value?.api_keys"
            :key="key.id"
            class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default p-4"
          >
            <span
              >{{ key.name }} · {{ key.scopes.join(', ')
              }}<span v-if="key.revoked_at">
                · {{ t('account.revoked') }}</span
              ></span
            ><NeButton
              v-if="!key.revoked_at"
              kind="secondary"
              @click="confirm = { id: key.id, kind: 'key', name: key.name }"
              >{{ t('account.revokeKey') }}</NeButton
            >
          </li>
        </ul></ResourceState
      >
    </section>
    <NeSideDrawer
      :is-shown="create"
      :title="t(secret ? 'account.keys' : 'account.createKey')"
      :close-aria-label="t('common.close')"
      @close="closeCreate"
    >
      <div v-if="secret" class="space-y-5">
        <NeTextInput
          data-c0-secret
          :model-value="secret"
          :label="t('account.secret')"
          readonly
          autocomplete="off"
        />
        <NeButton kind="primary" @click="closeCreate">{{
          t('account.dismissSecret')
        }}</NeButton>
      </div>
      <form
        v-else
        class="space-y-5"
        @submit.prevent="!creation.isLoading.value && creation.mutate()"
      >
        <ErrorNotice
          v-if="creation.error.value"
          :error="creation.error.value"
        />
        <NeTextInput
          v-model="name"
          :label="t('common.name')"
          :disabled="creation.isLoading.value"
        />
        <NeTextInput
          v-model="days"
          :label="t('account.days')"
          :disabled="creation.isLoading.value"
        />
        <NeCheckbox
          v-model="write"
          :label="t('account.write')"
          :disabled="creation.isLoading.value"
        />
        <fieldset class="space-y-3">
          <legend class="mb-3 font-medium">{{ t('nav.space') }}</legend>
          <NeCheckbox
            v-for="space in session.spaces"
            :key="space.id"
            v-model="selected[space.id]"
            :label="space.name"
            :disabled="
              creation.isLoading.value || (write && space.role === 'reader')
            "
          />
        </fieldset>
        <NeButton
          type="submit"
          kind="primary"
          :loading="creation.isLoading.value"
          :disabled="creation.isLoading.value"
          >{{ t('account.createKey') }}</NeButton
        >
      </form>
    </NeSideDrawer>
    <NeModal
      :visible="!!confirm"
      :title="
        t(confirm?.kind === 'key' ? 'account.revokeKey' : 'account.disconnect')
      "
      :primary-label="
        t(confirm?.kind === 'key' ? 'account.revokeKey' : 'account.disconnect')
      "
      primary-button-kind="danger"
      :primary-button-loading="removal.isLoading.value"
      :primary-button-disabled="removal.isLoading.value"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      @close="confirm = undefined"
      @primary-click="removal.mutate()"
      ><p>{{ confirm?.name }}</p>
      <p v-if="confirm?.kind === 'connection'">
        {{ t('account.disconnectHelp') }}
      </p>
      <ErrorNotice v-if="removal.error.value" :error="removal.error.value"
    /></NeModal>
  </div>
</template>
