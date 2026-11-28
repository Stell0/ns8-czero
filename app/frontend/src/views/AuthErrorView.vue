<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { localURL } from '../api/client'
const { t } = useI18n()
const boot = JSON.parse(
  document.getElementById('c0-boot')?.textContent || '{}',
) as { error?: string; restart?: string; reference?: string }

const messages = {
  access_denied: ['accessDenied', 'accessDeniedHelp', 'switchAccount'],
  remembered_unavailable: [
    'rememberUnavailable',
    'rememberUnavailableHelp',
    'returnSignin',
  ],
  callback_rejected: ['loginExpired', 'loginExpiredHelp', 'freshSignin'],
  native_authority_rejected: [
    'sessionUnavailable',
    'sessionUnavailableHelp',
    'freshSignin',
  ],
  provider_rejected: [
    'providerRejected',
    'providerRejectedHelp',
    'freshSignin',
  ],
  dependency_unavailable: [
    'serviceUnavailable',
    'serviceUnavailableHelp',
    'freshSignin',
  ],
  provider_unavailable: [
    'providerUnavailable',
    'providerUnavailableHelp',
    'freshSignin',
  ],
} as const
const error = Object.hasOwn(messages, boot.error || '')
  ? (boot.error as keyof typeof messages)
  : 'callback_rejected'
const [title, help, action] = messages[error]
const restart = /^\/oauth\/(consent|connect)\?flow=[A-Za-z0-9_-]{43}$/.test(
  boot.restart || '',
)
  ? boot.restart!
  : error === 'access_denied'
    ? '/auth/login?switch_account=true'
    : '/auth/sign-in'
</script>
<template>
  <div class="max-w-xl space-y-6" role="alert">
    <h2 class="text-xl font-medium">{{ t('account.' + title) }}</h2>
    <p>{{ t('account.' + help) }}</p>
    <p v-if="boot.reference" class="text-sm">
      {{ t('account.requestRef', { reference: boot.reference }) }}
    </p>
    <a :href="localURL(restart)" class="text-link">{{
      t('account.' + action)
    }}</a>
  </div>
</template>
