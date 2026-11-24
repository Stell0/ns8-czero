<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeSideDrawer,
  NeTextInput,
  NeCheckbox,
  NeFileInput,
  NeButton,
} from '@nethesis/vue-components'
import * as v from 'valibot'
import { request } from '../api/client'
import type { Source, Version } from '../api/knowledge'
import ErrorNotice from './ErrorNotice.vue'
import PdfReviewFields from './PdfReviewFields.vue'
import { usePdfReview } from '../api/pdfReview'
const props = defineProps<{ source?: Source }>()
const emit = defineEmits<{ close: []; uploaded: [version: Version] }>()
const { t } = useI18n()
const title = ref(props.source?.title || ''),
  provenance = ref(''),
  file = ref<File | null>(null),
  retain = ref(false),
  invalid = ref(false),
  progress = ref(0)
const review = usePdfReview()
const { password, passwordError, approved, approvalToken, canSubmit } = review
let active = true
let draft = 0
onBeforeUnmount(() => {
  active = false
  review.clear()
})
const types: Record<string, string> = {
  txt: 'text/plain',
  md: 'text/markdown',
  markdown: 'text/markdown',
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
const mutation = useMutation({
  mutation: async () => {
    if (!canSubmit.value) return
    const attempt = draft
    const valid = v.safeParse(
      v.pipe(v.string(), v.trim(), v.minLength(1), v.maxLength(256)),
      title.value,
    )
    const media = types[file.value?.name.split('.').pop()?.toLowerCase() || '']
    invalid.value = !valid.success || !file.value || !media
    if (invalid.value) return
    const form = new FormData()
    form.append('file', file.value!)
    form.append('title', title.value)
    form.append('media_type', media)
    form.append('retain_original', String(retain.value))
    form.append(
      'metadata',
      JSON.stringify(
        props.source?.metadata ||
          (provenance.value ? { original_url: provenance.value } : {}),
      ),
    )
    if (props.source) {
      form.append('source_id', props.source.id)
      form.append('expected_revision', String(props.source.revision))
    }
    if (media === 'application/pdf') {
      for (const [key, value] of Object.entries(review.fields())) {
        form.append(key, value)
      }
    }
    try {
      const version = await request<Version>('sources/upload', {
        method: 'POST',
        data: form,
        onUploadProgress: (event) => {
          if (active && draft === attempt)
            progress.value = Math.round((event.progress || 0) * 100)
        },
      })
      if (active && draft === attempt) {
        review.clear()
        emit('uploaded', version)
      }
    } catch (error) {
      if (active && draft === attempt && !review.prompt(error)) throw error
    }
  },
})
watch(
  [file, () => props.source?.id, () => props.source?.revision],
  () => {
    draft++
    review.clear()
    mutation.reset()
  },
  { flush: 'sync' },
)
</script>
<template>
  <NeSideDrawer
    :is-shown="true"
    :title="t(source ? 'sources.replace' : 'sources.upload')"
    :close-aria-label="t('common.close')"
    :close-on-click-outside="false"
    @close="emit('close')"
  >
    <form
      class="space-y-6"
      @submit.prevent="!mutation.isLoading.value && mutation.mutate()"
    >
      <ErrorNotice v-if="mutation.error.value" :error="mutation.error.value" />
      <NeTextInput
        v-model="title"
        :label="t('common.title')"
        :disabled="!!source || mutation.isLoading.value"
        :invalid-message="
          invalid && (!title.trim() || title.trim().length > 256)
            ? t('errors.invalid')
            : ''
        "
      />
      <NeTextInput
        v-if="!source"
        v-model="provenance"
        :label="t('sources.provenance')"
        :optional="true"
        :optional-label="t('common.optional')"
        :disabled="mutation.isLoading.value"
      />
      <NeFileInput
        v-model="file"
        :label="t('sources.file')"
        accept=".txt,.md,.markdown,.pdf,.docx"
        :helper-text="t('sources.formats')"
        :dropzone-label="t('sources.drop')"
        :disabled="mutation.isLoading.value"
        :show-progress="mutation.isLoading.value"
        :progress="progress"
        :invalid-message="invalid ? t('sources.invalidFile') : ''"
      />
      <NeCheckbox
        v-model="retain"
        :label="t('sources.retention')"
        :disabled="mutation.isLoading.value"
      />
      <p class="text-sm text-text-secondary">
        {{ t('sources.retentionHelp') }}
      </p>
      <PdfReviewFields
        v-if="file"
        v-model:password="password"
        v-model:approved="approved"
        :filename="file.name"
        :password-error="passwordError"
        :approval-required="!!approvalToken"
        :disabled="mutation.isLoading.value"
      />
      <NeButton
        kind="primary"
        type="submit"
        :loading="mutation.isLoading.value"
        :disabled="mutation.isLoading.value || !canSubmit"
        >{{ t(source ? 'sources.replace' : 'sources.upload') }}</NeButton
      >
    </form>
  </NeSideDrawer>
</template>
