<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeTextInput,
  NeTextArea,
  NeCheckbox,
  NeSideDrawer,
  NeListbox,
} from '@nethesis/vue-components'
import { useDraftGuard } from '../../composables/draft'
import { request } from '../../api/client'
import { useResource } from '../../api/queries'
import ResourceState from '../ResourceState.vue'
import ErrorNotice from '../ErrorNotice.vue'
interface Client {
  client_id: string
  client_name: string
  redirect_uris: string[]
  allowed_scopes: string[]
  enabled: boolean
  revision: number
  metadata_url?: string
}
interface Review {
  descriptor: {
    client_name: string
    client_id: string
    redirect_uris: string[]
    scope_ceiling: string[] | null
  }
  metadata_digest: string
}
const { t } = useI18n(),
  drawer = ref(false),
  name = ref(''),
  callbacks = ref(''),
  mode = ref('uuid'),
  url = ref(''),
  selected = ref<Client>(),
  reviewed = ref<Review>(),
  scopes = ref<Record<string, boolean>>({ 'c0:read': true })
const clients = useResource(
  () => 'clients',
  () => request<{ clients: Client[] }>('oauth/clients', {}, false),
)
const cimd = useResource(
  () => 'cimd',
  () =>
    request<{ enabled: boolean; clients: Client[] }>('oauth/cimd', {}, false),
)
watch([url, mode], () => {
  reviewed.value = undefined
})
const draft = useDraftGuard([drawer, url, mode, selected])
const preview = useMutation({
  mutation: async () => {
    const current = draft.start()
    const result = await request<Review>(
      'oauth/cimd/preview',
      { method: 'POST', data: { metadata_url: url.value } },
      false,
    )
    if (current()) {
      reviewed.value = result
      if (result.descriptor.scope_ceiling)
        scopes.value = Object.fromEntries(
          Object.entries(scopes.value).filter(([scope]) =>
            result.descriptor.scope_ceiling!.includes(scope),
          ),
        )
    }
  },
})
const save = useMutation({
  mutation: async () => {
    const current = draft.current()
    const allowed_scopes = Object.keys(scopes.value).filter(
      (scope) => scopes.value[scope],
    )
    if (mode.value === 'uuid')
      await request(
        'oauth/clients',
        {
          method: 'POST',
          data: {
            client_name: name.value,
            redirect_uris: callbacks.value
              .split('\n')
              .map((value) => value.trim())
              .filter(Boolean),
            allowed_scopes,
          },
        },
        false,
      )
    else {
      if (!reviewed.value) return
      const existing = selected.value
      await request(
        `oauth/cimd/clients${existing ? `/${existing.client_id}` : ''}`,
        {
          method: existing ? 'PUT' : 'POST',
          data: {
            metadata_digest: reviewed.value.metadata_digest,
            allowed_scopes,
            ...(existing
              ? { expected_revision: existing.revision }
              : { metadata_url: url.value }),
          },
        },
        false,
      )
    }
    if (current()) {
      drawer.value = false
      reviewed.value = undefined
    }
    await Promise.all([clients.refetch(), cimd.refetch()])
  },
})
const toggle = useMutation({
  mutation: async (client: Client) => {
    await request(
      `oauth/clients/${client.client_id}`,
      {
        method: 'PUT',
        data: { enabled: !client.enabled, expected_revision: client.revision },
      },
      false,
    )
    await Promise.all([clients.refetch(), cimd.refetch()])
  },
})
function create() {
  draft.clear()
  scopes.value = { 'c0:read': true }
  selected.value = undefined
  name.value = ''
  callbacks.value = ''
  url.value = ''
  mode.value = 'uuid'
  reviewed.value = undefined
  drawer.value = true
}
function review(client: Client) {
  draft.clear()
  selected.value = client
  url.value = client.metadata_url || ''
  mode.value = 'metadata'
  scopes.value = Object.fromEntries(
    client.allowed_scopes.map((scope) => [scope, true]),
  )
  reviewed.value = undefined
  drawer.value = true
}
</script>
<template>
  <div class="space-y-6">
    <NeButton kind="primary" @click="create">{{
      t('admin.createClient')
    }}</NeButton
    ><ErrorNotice
      v-if="toggle.error.value"
      :error="toggle.error.value"
    /><ResourceState
      :error="clients.error.value"
      :loading="clients.isPending.value"
      ><ul class="space-y-4">
        <li
          v-for="client in clients.data.value?.clients"
          :key="client.client_id"
          class="space-y-3 rounded-lg border border-default p-4"
        >
          <h2 class="text-lg font-medium">{{ client.client_name }}</h2>
          <p>{{ client.allowed_scopes.join(', ') }}</p>
          <details>
            <summary>{{ t('common.details') }}</summary>
            <pre class="overflow-auto text-sm">{{
              JSON.stringify(client, null, 2)
            }}</pre>
          </details>
          <div class="flex flex-wrap gap-3">
            <NeButton
              kind="secondary"
              :loading="toggle.isLoading.value"
              :disabled="toggle.isLoading.value"
              @click="toggle.mutate(client)"
              >{{
                t(client.enabled ? 'admin.disable' : 'admin.enable')
              }}</NeButton
            ><NeButton
              v-if="
                cimd.data.value?.clients.some(
                  (item) => item.client_id === client.client_id,
                )
              "
              kind="secondary"
              @click="
                review(
                  cimd.data.value!.clients.find(
                    (item) => item.client_id === client.client_id,
                  )!,
                )
              "
              >{{ t('admin.approve') }}</NeButton
            >
          </div>
        </li>
      </ul></ResourceState
    >
    <NeSideDrawer
      :is-shown="drawer"
      :title="t('admin.createClient')"
      :close-aria-label="t('common.close')"
      @close="drawer = false"
      ><form
        class="space-y-5"
        @submit.prevent="!save.isLoading.value && save.mutate()"
      >
        <ErrorNotice
          v-if="save.error.value || preview.error.value"
          :error="save.error.value || preview.error.value"
        /><NeListbox
          v-model="mode"
          :label="t('admin.clients')"
          :disabled="
            !!selected || save.isLoading.value || preview.isLoading.value
          "
          :options="[
            { id: 'uuid', label: 'OAuth' },
            {
              id: 'metadata',
              label: 'HTTPS',
              disabled: !cimd.data.value?.enabled,
            },
          ]"
          :no-options-label="t('common.options')"
          :optional-label="t('common.optional')"
        /><template v-if="mode === 'uuid'"
          ><NeTextInput
            v-model="name"
            :label="t('common.name')"
            :disabled="save.isLoading.value" /><NeTextArea
            v-model="callbacks"
            :label="t('consent.callback')"
            :disabled="save.isLoading.value" /></template
        ><template v-else
          ><NeTextInput
            v-model="url"
            :label="t('agents.url')"
            :disabled="
              !!selected || save.isLoading.value || preview.isLoading.value
            "
          /><NeButton
            kind="secondary"
            :loading="preview.isLoading.value"
            :disabled="preview.isLoading.value || save.isLoading.value"
            @click="preview.mutate()"
            >{{ t('common.details') }}</NeButton
          >
          <pre v-if="reviewed" class="overflow-auto text-sm">{{
            JSON.stringify(reviewed.descriptor, null, 2)
          }}</pre></template
        ><NeCheckbox
          v-for="scope in ['c0:read', 'c0:write', 'c0:admin']"
          :key="scope"
          v-model="scopes[scope]"
          :label="
            t(`account.${scope === 'c0:admin' ? 'manage' : scope.slice(3)}`)
          "
          :disabled="
            save.isLoading.value ||
            (!!reviewed?.descriptor.scope_ceiling &&
              !reviewed.descriptor.scope_ceiling.includes(scope))
          "
        /><NeButton
          kind="primary"
          type="submit"
          :loading="save.isLoading.value"
          :disabled="save.isLoading.value || (mode === 'metadata' && !reviewed)"
          >{{ t('admin.approve') }}</NeButton
        >
      </form></NeSideDrawer
    >
  </div>
</template>
