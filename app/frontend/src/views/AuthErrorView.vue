<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { localURL } from '../api/client'
const { t } = useI18n()
const boot = JSON.parse(
  document.getElementById('c0-boot')?.textContent || '{}',
) as { error?: string }
const unavailable = boot.error === 'remembered_unavailable'
</script>
<template>
  <div class="max-w-xl space-y-6" role="alert">
    <h2 class="text-xl font-medium">
      {{
        t(unavailable ? 'account.rememberUnavailable' : 'account.accessDenied')
      }}
    </h2>
    <p>
      {{
        t(
          unavailable
            ? 'account.rememberUnavailableHelp'
            : 'account.accessDeniedHelp',
        )
      }}
    </p>
    <a
      :href="
        localURL(
          unavailable ? '/auth/sign-in' : '/auth/login?switch_account=true',
        )
      "
      class="text-link"
      >{{
        t(unavailable ? 'account.returnSignin' : 'account.switchAccount')
      }}</a
    >
  </div>
</template>
