<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import { NeButton, NeTextInput, NeListbox } from '@nethesis/vue-components'
import { useDraftGuard } from '../../composables/draft'
import { ReplayIdentity } from '../../api/replay'
import { request } from '../../api/client'
import { useResource } from '../../api/queries'
import { useSession } from '../../stores/session'
import ErrorNotice from '../ErrorNotice.vue'
import ResourceState from '../ResourceState.vue'
const session = useSession(),
  router = useRouter(),
  { t } = useI18n(),
  name = ref(''),
  audience = ref('restricted'),
  existingAudience = ref('restricted'),
  choices = ref<Record<string, string>>({}),
  audienceRevision = ref(0)
let observedAudience = 'restricted',
  observedSpace = ''
watch(
  () => session.space,
  (space) => {
    const next = space?.readable_by_all ? 'all' : 'restricted'
    if (
      observedSpace !== (space?.id || '') ||
      existingAudience.value === observedAudience
    ) {
      existingAudience.value = next
      audienceRevision.value = space?.revision || 0
    }
    observedSpace = space?.id || ''
    observedAudience = next
  },
  { immediate: true },
)
const audienceOptions = () => [
  { id: 'restricted', label: t('admin.selectedPeople') },
  { id: 'all', label: t('admin.allSignedIn') },
]
const replay = new ReplayIdentity()
interface Grant {
  account_id: string
  role: string | null
  revision: number
}
const { data, error, isPending, refetch } = useResource(
  () => `grants:${session.space?.id}`,
  async () => {
    const [accounts, grants] = await Promise.all([
      request<{
        accounts: {
          id: string
          username: string
          role: string
          is_owner: boolean
        }[]
      }>('access/accounts?limit=1000', {}, false),
      (async () => {
        const grants: Grant[] = []
        for (let offset = 0; ; offset += 100) {
          const page = await request<{ grants: Grant[] }>(
            `spaces/${session.space!.id}/grants?limit=100&offset=${offset}`,
            {},
            false,
          )
          grants.push(...page.grants)
          if (page.grants.length < 100) return { grants }
        }
      })(),
    ])
    return accounts.accounts.map((account) => {
      const grant = grants.grants.find((item) => item.account_id === account.id)
      return { ...account, grant }
    })
  },
  () => !!session.space && !session.space.shared,
)
const observed = new Map<string, string>()
watch(data, (accounts) => {
  for (const account of accounts || []) {
    const role = account.grant?.role || 'none'
    if (
      !(account.id in choices.value) ||
      choices.value[account.id] === observed.get(account.id)
    )
      choices.value[account.id] = role
    observed.set(account.id, role)
  }
})
const draft = useDraftGuard([name, audience, existingAudience])
const create = useMutation({
  mutation: async () => {
    const current = draft.current()
    const space = await request<{ id: string }>(
      'spaces',
      {
        method: 'POST',
        data: replay.data('spaces', {
          name: name.value.trim(),
          readable_by_all: audience.value === 'all',
        }),
      },
      false,
    )
    if (current())
      await router.push({
        path: '/admin/spaces',
        query: { space_id: space.id },
      })
  },
})
const saveAudience = useMutation({
  mutation: async () => {
    const space = session.space!
    const current = draft.current()
    await request(
      `spaces/${space.id}/access`,
      {
        method: 'PUT',
        data: replay.data(`spaces/${space.id}/access`, {
          readable_by_all: existingAudience.value === 'all',
          expected_revision: audienceRevision.value,
        }),
      },
      false,
    )
    if (!current()) return
    observedAudience = existingAudience.value
    replay.clear()
    await session.load()
  },
})
const save = useMutation({
  mutation: async (account: string) => {
    const old = data.value?.find((item) => item.id === account)?.grant
    await request(
      `spaces/${session.space!.id}/grants/${account}`,
      {
        method: 'PUT',
        data: replay.data(`spaces/${session.space!.id}/grants/${account}`, {
          role:
            choices.value[account] === 'none' ? null : choices.value[account],
          expected_revision: old?.revision || 0,
        }),
      },
      false,
    )
    replay.clear()
    await refetch()
  },
})
</script>
<template>
  <div class="space-y-6">
    <form
      class="flex flex-wrap items-end gap-4"
      @submit.prevent="!create.isLoading.value && create.mutate()"
    >
      <NeTextInput
        v-model="name"
        :label="t('common.name')"
        :disabled="create.isLoading.value"
      />
      <NeListbox
        v-model="audience"
        :label="t('admin.audience')"
        :options="audienceOptions()"
        :no-options-label="t('common.options')"
        :optional-label="t('common.optional')"
      />
      <NeButton
        type="submit"
        kind="primary"
        :loading="create.isLoading.value"
        :disabled="create.isLoading.value"
        >{{ t('admin.createSpace') }}</NeButton
      >
    </form>
    <form
      v-if="session.space && !session.space.shared"
      class="space-y-4"
      @submit.prevent="!saveAudience.isLoading.value && saveAudience.mutate()"
    >
      <NeListbox
        v-model="existingAudience"
        :label="t('admin.audience')"
        :options="audienceOptions()"
        :disabled="saveAudience.isLoading.value"
        :no-options-label="t('common.options')"
        :optional-label="t('common.optional')"
      />
      <p>{{ t('admin.audienceHelp') }}</p>
      <NeButton
        type="submit"
        :loading="saveAudience.isLoading.value"
        :disabled="saveAudience.isLoading.value"
        >{{ t('admin.saveAudience') }}</NeButton
      >
    </form>
    <ErrorNotice
      v-if="create.error.value || save.error.value || saveAudience.error.value"
      :error="
        create.error.value || save.error.value || saveAudience.error.value
      "
    /><ResourceState
      v-if="!session.space?.shared"
      :error="error"
      :loading="isPending"
      ><ul class="space-y-5">
        <li
          v-for="account in data"
          :key="account.id"
          class="flex flex-wrap items-end gap-4"
        >
          <NeListbox
            v-model="choices[account.id]"
            :label="account.username"
            :disabled="
              account.role === 'admin' ||
              account.is_owner ||
              save.isLoading.value
            "
            :options="[
              { id: 'none', label: t('admin.noGrant') },
              { id: 'reader', label: t('account.read') },
              { id: 'editor', label: t('admin.readWrite') },
            ]"
            :no-options-label="t('common.options')"
            :optional-label="t('common.optional')"
          /><NeButton
            v-if="account.role !== 'admin' && !account.is_owner"
            kind="secondary"
            :loading="save.isLoading.value"
            :disabled="save.isLoading.value"
            @click="save.mutate(account.id)"
            >{{ t('admin.grant') }}</NeButton
          >
        </li>
      </ul></ResourceState
    >
  </div>
</template>
