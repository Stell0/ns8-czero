<script setup lang="ts">
import { NeSkeleton, NeEmptyState } from '@nethesis/vue-components'
import { useI18n } from 'vue-i18n'
import ErrorNotice from './ErrorNotice.vue'
defineProps<{ error?: unknown; loading?: boolean; empty?: boolean }>()
const { t } = useI18n()
</script>
<template>
  <ErrorNotice v-if="error" :error="error" />
  <NeSkeleton
    v-else-if="loading"
    class="h-24"
    :aria-label="t('common.loading')"
  />
  <NeEmptyState
    v-else-if="empty"
    :title="t('common.empty')"
    :description="t('common.emptyHelp')"
  />
  <slot v-else />
</template>
