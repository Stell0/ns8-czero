<script setup lang="ts">
import { NeInlineNotification } from '@nethesis/vue-components'
import { useI18n } from 'vue-i18n'
import { errorKey } from '../api/client'
defineProps<{ error: unknown }>()
const { t } = useI18n()
</script>
<template>
  <NeInlineNotification
    role="alert"
    kind="error"
    :title="t('errors.title')"
    :description="t(errorKey(error))"
  />
</template>
