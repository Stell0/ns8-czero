<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NeButton, NeCheckbox } from '@nethesis/vue-components'
import AuthErrorView from './AuthErrorView.vue'
import { localURL } from '../api/client'
const { t } = useI18n(),
  remember = ref(false)
const boot = JSON.parse(
  document.getElementById('c0-boot')?.textContent || '{}',
) as { intent?: string; return_to?: string; error?: string }
</script>
<template>
  <AuthErrorView v-if="boot.error" />
  <form
    v-else
    class="max-w-xl space-y-6"
    method="post"
    :action="localURL('auth/sign-in')"
  >
    <input type="hidden" name="intent" :value="boot.intent" /><input
      type="hidden"
      name="return_to"
      :value="boot.return_to"
    /><input
      v-if="remember"
      type="hidden"
      name="remember"
      value="yes"
    /><NeCheckbox v-model="remember" :label="t('account.remember')" />
    <p>{{ t('account.rememberHelp') }}</p>
    <NeButton kind="primary" type="submit" :disabled="!boot.intent">{{
      t('account.continue')
    }}</NeButton>
  </form>
</template>
