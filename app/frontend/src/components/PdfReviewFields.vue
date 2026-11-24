<script setup lang="ts">
import { NeCheckbox, NeTextInput } from '@nethesis/vue-components'
import { useI18n } from 'vue-i18n'
import { ref, watch } from 'vue'
import { useSession } from '../stores/session'

const props = defineProps<{
  filename: string
  passwordError: string
  approvalRequired: boolean
  disabled: boolean
}>()
const password = defineModel<string>('password', { required: true })
const approved = defineModel<boolean>('approved', { required: true })
const { t } = useI18n()
const session = useSession()
const passwordInput = ref<InstanceType<typeof NeTextInput>>()
const approvalFields = ref<HTMLElement>()
watch(
  () => [props.passwordError, props.approvalRequired, props.disabled],
  () => {
    if (props.disabled) return
    if (props.passwordError) passwordInput.value?.focus()
    else if (props.approvalRequired)
      approvalFields.value?.querySelector('input')?.focus()
  },
  { flush: 'post' },
)
</script>

<template>
  <NeTextInput
    v-if="passwordError"
    ref="passwordInput"
    v-model="password"
    is-password
    autocomplete="new-password"
    :show-password-label="t('sources.pdf.showPassword')"
    :hide-password-label="t('sources.pdf.hidePassword')"
    :label="t('sources.pdf.password')"
    :invalid-message="password ? '' : t(`sources.pdf.${passwordError}`)"
    :disabled="disabled"
  />
  <div v-if="approvalRequired" ref="approvalFields" class="space-y-3">
    <p role="status">
      {{
        t('sources.pdf.restriction', {
          file: filename,
          space: session.space?.name || '',
        })
      }}
    </p>
    <NeCheckbox
      v-model="approved"
      :label="t('sources.pdf.approve')"
      :disabled="disabled"
    />
  </div>
  <p
    v-if="passwordError || approvalRequired"
    class="text-sm text-text-secondary"
  >
    {{ t('sources.pdf.retentionHelp') }}
  </p>
</template>
