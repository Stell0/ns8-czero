<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import { NeModal } from '@nethesis/vue-components'
import { request } from '../api/client'
import type { Version } from '../api/knowledge'
import { usePdfReview } from '../api/pdfReview'
import ErrorNotice from './ErrorNotice.vue'
import PdfReviewFields from './PdfReviewFields.vue'

const props = defineProps<{ version: Version; title: string }>()
const emit = defineEmits<{ close: []; queued: [] }>()
const { t } = useI18n()
const review = usePdfReview()
const { password, passwordError, approved, approvalToken, canSubmit } = review
let active = true
onBeforeUnmount(() => {
  active = false
  review.clear()
})

const mutation = useMutation({
  mutation: async () => {
    if (!canSubmit.value) return
    try {
      await request(`source-versions/${props.version.id}/pdf-retry`, {
        method: 'POST',
        data: {
          expected_generation: props.version.generation,
          ...review.fields(),
        },
      })
    } catch (error) {
      if (active && !review.prompt(error)) throw error
      return
    }
    if (active) {
      review.clear()
      emit('queued')
    }
  },
})
</script>

<template>
  <NeModal
    :visible="true"
    :title="t('sources.pdf.reviewRetry')"
    :primary-label="t('sources.pdf.continue')"
    :cancel-label="t('common.cancel')"
    :close-aria-label="t('common.close')"
    :primary-button-loading="mutation.isLoading.value"
    :primary-button-disabled="mutation.isLoading.value || !canSubmit"
    @close="emit('close')"
    @primary-click="!mutation.isLoading.value && mutation.mutate()"
  >
    <div class="space-y-3">
      <ErrorNotice v-if="mutation.error.value" :error="mutation.error.value" />
      <p v-if="!passwordError && !approvalToken">
        {{ t('sources.pdf.retryHelp', { file: version.filename || title }) }}
      </p>
      <PdfReviewFields
        v-model:password="password"
        v-model:approved="approved"
        :filename="version.filename || title"
        :password-error="passwordError"
        :approval-required="!!approvalToken"
        :disabled="mutation.isLoading.value"
      />
    </div>
  </NeModal>
</template>
