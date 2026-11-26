import { computed, ref } from 'vue'
import { ApiError } from './client'

export function usePdfReview() {
  const password = ref('')
  const approved = ref(false)
  const passwordError = ref('')
  const approvalToken = ref('')

  function clear() {
    password.value = ''
    approved.value = false
    passwordError.value = ''
    approvalToken.value = ''
  }

  function prompt(error: unknown) {
    if (error instanceof ApiError && error.status === 422) {
      if (
        error.code === 'pdf_password_required' ||
        error.code === 'pdf_password_incorrect'
      ) {
        clear()
        passwordError.value = error.code
        return true
      }
      if (
        error.code === 'pdf_extraction_approval_required' &&
        error.approvalToken
      ) {
        passwordError.value = ''
        approved.value = false
        approvalToken.value = error.approvalToken
        return true
      }
    }
    clear()
    return false
  }

  const canSubmit = computed(
    () =>
      (!passwordError.value || !!password.value) &&
      (!approvalToken.value || approved.value),
  )
  const fields = () => ({
    ...(password.value ? { pdf_password: password.value } : {}),
    ...(approvalToken.value && approved.value
      ? { pdf_approval_token: approvalToken.value }
      : {}),
  })
  return {
    password,
    approved,
    passwordError,
    approvalToken,
    canSubmit,
    fields,
    prompt,
    clear,
  }
}
