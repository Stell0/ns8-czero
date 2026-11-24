<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useMutation } from '@pinia/colada'
import { useI18n } from 'vue-i18n'
import {
  NeButton,
  NeCheckbox,
  NeModal,
  NeTextInput,
} from '@nethesis/vue-components'
import { ApiError, request } from '../api/client'
import {
  drivePath,
  rememberDriveEditor,
  type DriveConnection,
} from '../api/googleDrive'
import { useSession } from '../stores/session'
import ErrorNotice from './ErrorNotice.vue'

const props = defineProps<{
  connection?: DriveConnection
  sourceId?: string
  enabled: boolean
  invalidMessage: string
  disconnectNames: string[]
}>()
const folder = defineModel<string>({ required: true })
const emit = defineEmits<{ refresh: []; busy: [value: boolean] }>()
const { t } = useI18n()
const session = useSession()
const offline = ref(false)
const disconnecting = ref(false)
const connected = computed(() => props.connection?.connected === true)
let active = true
onUnmounted(() => {
  active = false
  emit('busy', false)
})
const change = useMutation({
  mutation: async (action: 'connect' | 'disconnect') => {
    if (action === 'disconnect') {
      await request(`${drivePath}/connection`, { method: 'DELETE' })
      if (active) {
        disconnecting.value = false
        folder.value = ''
        emit('refresh')
      }
      return
    }
    const { url } = await request<{ url: string }>(`${drivePath}/connect`, {
      method: 'POST',
      data: { offline: props.enabled || offline.value },
    })
    if (!active || !session.canWrite || !session.space) return
    const destination = new URL(url)
    if (
      destination.origin !== 'https://accounts.google.com' ||
      destination.pathname !== '/o/oauth2/v2/auth' ||
      destination.username ||
      destination.password
    )
      throw new ApiError(502)
    rememberDriveEditor(session.account, session.space.id, props.sourceId)
    location.assign(destination.href)
  },
})
watch(change.isLoading, (value) => emit('busy', value), { flush: 'sync' })
</script>

<template>
  <section
    class="space-y-3 rounded-lg border border-default bg-elevation-1 p-4"
  >
    <h2 class="font-medium">{{ t('automatic.driveAccount') }}</h2>
    <ErrorNotice
      v-if="change.error.value && !disconnecting"
      :error="change.error.value"
    />
    <p class="text-sm text-text-secondary">{{ t('automatic.driveScope') }}</p>
    <p v-if="connected" class="text-sm">
      {{
        t(
          connection?.offline
            ? 'automatic.driveConnectedOffline'
            : 'automatic.driveConnected',
        )
      }}
    </p>
    <NeCheckbox
      v-if="!connected && !enabled"
      v-model="offline"
      :label="t('automatic.driveAllowOffline')"
    />
    <p v-if="connection?.available === false" role="alert">
      {{ t('automatic.errors.drive_unavailable') }}
    </p>
    <p v-if="connected && enabled && !connection?.offline" class="text-sm">
      {{ t('automatic.driveReconnectEffect') }}
    </p>
    <NeButton
      v-if="
        connection?.available &&
        (!connected || (enabled && !connection.offline))
      "
      kind="secondary"
      :loading="change.isLoading.value"
      @click="change.mutate('connect')"
      >{{
        t(
          connected
            ? 'automatic.driveAuthorizeOffline'
            : 'automatic.driveConnect',
        )
      }}</NeButton
    >
    <NeButton
      v-if="connected"
      kind="tertiary"
      :disabled="change.isLoading.value"
      @click="disconnecting = true"
      >{{ t('automatic.driveDisconnect') }}</NeButton
    >
  </section>
  <NeTextInput
    v-model="folder"
    :label="t('automatic.driveFolder')"
    :disabled="!connected"
    :helper-text="
      t(
        sourceId
          ? 'automatic.driveExistingFolderHelp'
          : 'automatic.driveFolderHelp',
      )
    "
    :aria-invalid="!!invalidMessage || undefined"
    :invalid-message="invalidMessage"
  />
  <div class="space-y-1 rounded-lg border border-default bg-elevation-1 p-4">
    <p class="font-medium">
      {{ t('automatic.driveDestination', { space: session.space?.name }) }}
    </p>
    <p class="text-sm text-text-secondary">
      {{ t('automatic.driveAudience') }}
    </p>
  </div>
  <NeModal
    v-if="disconnecting"
    :visible="true"
    :title="t('automatic.driveDisconnect')"
    :primary-label="t('automatic.driveDisconnect')"
    :cancel-label="t('common.cancel')"
    :close-aria-label="t('common.close')"
    kind="warning"
    primary-button-kind="danger"
    :primary-button-loading="change.isLoading.value"
    :primary-button-disabled="change.isLoading.value"
    @close="!change.isLoading.value && (disconnecting = false)"
    @primary-click="change.mutate('disconnect')"
  >
    <ErrorNotice v-if="change.error.value" :error="change.error.value" />
    <p>{{ t('automatic.driveDisconnectHelp') }}</p>
    <ul v-if="disconnectNames.length" class="mt-3 list-disc pl-5">
      <li v-for="(name, index) in disconnectNames" :key="index">{{ name }}</li>
    </ul>
  </NeModal>
</template>
