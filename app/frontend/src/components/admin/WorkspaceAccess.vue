<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMutation } from '@pinia/colada'
import {
  NeButton,
  NeListbox,
  NeCheckbox,
  NeModal,
  NeTable,
  NeTableHead,
  NeTableHeadCell,
  NeTableBody,
  NeTableRow,
  NeTableCell,
} from '@nethesis/vue-components'
import { useDraftGuard } from '../../composables/draft'
import { request } from '../../api/client'
import { useResource } from '../../api/queries'
import ResourceState from '../ResourceState.vue'
import ErrorNotice from '../ErrorNotice.vue'
interface Person {
  id: string
  username: string
  full_name?: string
  role: string | null
  is_owner: boolean
  blocked: boolean
  access_revision: number
}
interface Application {
  id: string
  kind: 'request' | 'connection'
  client_name: string
  client_id: string
  metadata_url?: string
  scopes: string[]
  status: string
  permissions?: Record<string, boolean>
}
interface Review {
  metadata_digest: string
  request: {
    callback: string
    scopes: string[]
  }
  descriptor: {
    client_name: string
    client_id: string
    redirect_uris: string[]
    scope_ceiling?: string[]
  }
  client: {
    client_id: string
    revision: number
    allowed_scopes: string[]
    enabled: boolean
    metadata_digest: string
    review_required: boolean
  } | null
}
const { t } = useI18n(),
  offset = ref(0),
  selected = ref<Person>(),
  role = ref('reader'),
  reviewed = ref<{ id: string; value: Review }>(),
  scopes = ref<Record<string, boolean>>({}),
  confirmation = ref<{
    id: string
    kind: 'request' | 'connection'
    name: string
  }>()
const { data, error, isPending, refetch } = useResource(
  () => `access:${offset.value}`,
  async () => {
    const result = await request<{ accounts: Person[]; has_more: boolean }>(
      `access/workspace?offset=${offset.value}`,
      {},
      false,
    )
    return {
      ...result,
      accounts: await Promise.all(
        result.accounts.map(async (person) => {
          const applications: Application[] = []
          for (let cursor = 0; ; cursor += 50) {
            const page = await request<{
              applications: Application[]
              has_more: boolean
            }>(
              `access/accounts/${person.id}/applications?limit=50&offset=${cursor}`,
              {},
              false,
            )
            applications.push(...page.applications)
            if (!page.has_more) break
          }
          return { ...person, applications }
        }),
      ),
    }
  },
)
const draft = useDraftGuard([selected, reviewed, confirmation])
const notice = ref('')
function permissionNames(values: string[]) {
  const names = values.map(
    (scope) =>
      ({ 'c0:read': 'read', 'c0:write': 'write', 'c0:admin': 'manage' })[
        scope
      ] || scope,
  )
  return (
    names.map((name) => t(`account.${name}`)).join(', ') ||
    t('admin.noPermissions')
  )
}
const mutation = useMutation({
  mutation: async (operation: {
    path: string
    method: string
    data?: object
  }) => {
    const current = draft.current()
    await request(
      operation.path,
      { method: operation.method, data: operation.data },
      false,
    )
    if (current()) {
      selected.value = undefined
      reviewed.value = undefined
      confirmation.value = undefined
    }
    await refetch()
  },
})
const preview = useMutation({
  mutation: async (id: string) => {
    const current = draft.start()
    const value = await request<Review>(
      `access/requests/${id}/preview`,
      { method: 'POST' },
      false,
    )
    if (!current()) return
    scopes.value = Object.fromEntries(
      ['c0:read', 'c0:write', 'c0:admin'].map((scope) => [
        scope,
        !!value.client?.allowed_scopes.includes(scope) ||
          (scope === 'c0:read' &&
            value.request.scopes.includes(scope) &&
            (!value.descriptor.scope_ceiling ||
              value.descriptor.scope_ceiling.includes(scope))),
      ]),
    )
    reviewed.value = { id, value }
  },
})
function edit(person: Person) {
  selected.value = person
  role.value = person.blocked ? 'blocked' : person.role || 'reader'
}
function saveRole() {
  const person = selected.value
  if (!person || mutation.isLoading.value) return
  if (
    (person.blocked && role.value === 'blocked') ||
    (!person.blocked && role.value === person.role)
  ) {
    selected.value = undefined
    return
  }
  mutation.mutate({
    path: `access/accounts/${person.id}`,
    method: 'PUT',
    data: {
      role: role.value === 'blocked' ? null : role.value,
      expected_revision: person.access_revision,
    },
  })
}
function approve() {
  const review = reviewed.value
  if (!review || mutation.isLoading.value) return
  const allowed = Object.keys(scopes.value)
    .filter((key) => scopes.value[key])
    .sort()
  const client = review.value.client
  if (
    client?.enabled &&
    !client.review_required &&
    client.metadata_digest === review.value.metadata_digest &&
    JSON.stringify([...client.allowed_scopes].sort()) ===
      JSON.stringify(allowed)
  ) {
    reviewed.value = undefined
    notice.value = t('admin.unchangedApproval')
    return
  }
  mutation.mutate({
    path: `access/requests/${review.id}/approve`,
    method: 'POST',
    data: {
      metadata_digest: review.value.metadata_digest,
      allowed_scopes: allowed,
      client_id: review.value.client?.client_id || null,
      expected_revision: review.value.client?.revision || null,
    },
  })
}
</script>
<template>
  <div class="space-y-5">
    <p v-if="notice" role="status">{{ notice }}</p>
    <NeButton kind="secondary" @click="refetch()">{{
      t('common.reload')
    }}</NeButton
    ><ErrorNotice
      v-if="mutation.error.value || preview.error.value"
      :error="mutation.error.value || preview.error.value"
    /><ResourceState :error="error" :loading="isPending"
      ><NeTable :aria-label="t('admin.people')" card-breakpoint="md"
        ><NeTableHead
          ><NeTableHeadCell>{{ t('common.name') }}</NeTableHeadCell
          ><NeTableHeadCell>{{ t('admin.role') }}</NeTableHeadCell
          ><NeTableHeadCell>{{
            t('common.actions')
          }}</NeTableHeadCell></NeTableHead
        ><NeTableBody
          ><template v-for="person in data?.accounts" :key="person.id"
            ><NeTableRow :data-account-id="person.id"
              ><NeTableCell :data-label="t('common.name')"
                >{{ person.username }}
                <p v-if="person.full_name" class="text-sm text-text-secondary">
                  {{ person.full_name }}
                </p></NeTableCell
              ><NeTableCell :data-label="t('admin.role')">{{
                person.is_owner
                  ? t('admin.owner')
                  : person.blocked
                    ? t('admin.block')
                    : t(
                        `account.${person.role === 'admin' ? 'manage' : person.role === 'editor' ? 'write' : 'read'}`,
                      )
              }}</NeTableCell
              ><NeTableCell :data-label="t('common.actions')"
                ><NeButton
                  v-if="!person.is_owner"
                  kind="secondary"
                  :disabled="mutation.isLoading.value"
                  @click="edit(person)"
                  >{{ t('admin.changePermissions') }}</NeButton
                ></NeTableCell
              ></NeTableRow
            ><NeTableRow
              v-for="application in person.applications"
              :key="application.id"
              :data-application-id="application.id"
              class="bg-elevation-1"
              ><NeTableCell :data-label="t('common.name')">{{
                application.client_name ||
                application.metadata_url ||
                application.client_id
              }}</NeTableCell
              ><NeTableCell :data-label="t('common.status')"
                ><p>
                  {{
                    t(`admin.states.${application.status}`, application.status)
                  }}
                </p>
                <p>
                  {{
                    t(
                      application.kind === 'request'
                        ? 'admin.requested'
                        : 'admin.consented',
                    )
                  }}: {{ permissionNames(application.scopes) }}
                </p>
                <p>
                  {{ t('admin.effective') }}:
                  {{
                    permissionNames(
                      Object.keys(application.permissions || {}).filter(
                        (key) => application.permissions?.[key],
                      ),
                    )
                  }}
                </p></NeTableCell
              ><NeTableCell :data-label="t('common.actions')"
                ><div class="flex flex-wrap gap-2">
                  <template v-if="application.kind === 'request'"
                    ><NeButton
                      v-if="
                        !person.blocked &&
                        person.role &&
                        application.status !== 'waiting_for_consent'
                      "
                      kind="secondary"
                      :loading="preview.isLoading.value"
                      :disabled="
                        preview.isLoading.value || mutation.isLoading.value
                      "
                      @click="preview.mutate(application.id)"
                      >{{ t('admin.approve') }}</NeButton
                    ><NeButton
                      kind="tertiary"
                      :disabled="mutation.isLoading.value"
                      @click="
                        confirmation = {
                          id: application.id,
                          kind: 'request',
                          name:
                            application.client_name ||
                            application.metadata_url ||
                            application.client_id,
                        }
                      "
                      >{{ t('admin.decline') }}</NeButton
                    ></template
                  ><NeButton
                    v-else
                    kind="secondary"
                    :disabled="mutation.isLoading.value"
                    @click="
                      confirmation = {
                        id: application.id,
                        kind: 'connection',
                        name: application.client_name || application.client_id,
                      }
                    "
                    >{{ t('account.disconnect') }}</NeButton
                  >
                </div></NeTableCell
              ></NeTableRow
            ></template
          ></NeTableBody
        ></NeTable
      >
      <div class="mt-4 flex gap-3">
        <NeButton kind="secondary" :disabled="!offset" @click="offset -= 25">{{
          t('common.previous')
        }}</NeButton
        ><NeButton
          kind="secondary"
          :disabled="!data?.has_more"
          @click="offset += 25"
          >{{ t('common.next') }}</NeButton
        >
      </div></ResourceState
    >
    <NeModal
      :visible="!!selected"
      :title="t('admin.changePermissions')"
      :primary-label="t('common.save')"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      :primary-button-loading="mutation.isLoading.value"
      :primary-button-disabled="mutation.isLoading.value"
      @close="selected = undefined"
      @primary-click="saveRole"
      ><ErrorNotice v-if="mutation.error.value" :error="mutation.error.value" />
      <p class="mb-4">{{ selected?.username }}</p>
      <NeListbox
        v-model="role"
        :label="t('admin.role')"
        :options="[
          { id: 'reader', label: t('account.read') },
          { id: 'editor', label: t('account.write') },
          { id: 'admin', label: t('account.manage') },
          { id: 'blocked', label: t('admin.block') },
        ]"
        :no-options-label="t('common.options')"
        :optional-label="t('common.optional')"
        :disabled="mutation.isLoading.value"
    /></NeModal>
    <NeModal
      :visible="!!reviewed"
      :title="t('admin.approve')"
      :primary-label="t('admin.approve')"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      :primary-button-loading="mutation.isLoading.value"
      :primary-button-disabled="mutation.isLoading.value"
      @close="reviewed = undefined"
      @primary-click="approve"
      ><div v-if="reviewed" class="space-y-4">
        <ErrorNotice
          v-if="mutation.error.value"
          :error="mutation.error.value"
        />
        <p>{{ reviewed.value.descriptor.client_name }}</p>
        <p class="break-all">{{ reviewed.value.descriptor.client_id }}</p>
        <p class="break-all">
          {{ t('consent.callback') }}: {{ reviewed.value.request.callback }}
        </p>
        <ul>
          <li
            v-for="callback in reviewed.value.descriptor.redirect_uris"
            :key="callback"
            class="break-all"
          >
            {{ callback }}
          </li>
        </ul>
        <NeCheckbox
          v-for="scope in ['c0:read', 'c0:write', 'c0:admin']"
          :key="scope"
          v-model="scopes[scope]"
          :label="
            t(`account.${scope === 'c0:admin' ? 'manage' : scope.slice(3)}`)
          "
          :disabled="
            mutation.isLoading.value ||
            (!reviewed.value.request.scopes.includes(scope) &&
              !reviewed.value.client?.allowed_scopes.includes(scope)) ||
            (!!reviewed.value.descriptor.scope_ceiling &&
              !reviewed.value.descriptor.scope_ceiling.includes(scope))
          "
        /></div
    ></NeModal>
    <NeModal
      :visible="!!confirmation"
      :title="
        t(
          confirmation?.kind === 'request'
            ? 'admin.decline'
            : 'account.disconnect',
        )
      "
      :primary-label="
        t(
          confirmation?.kind === 'request'
            ? 'admin.decline'
            : 'account.disconnect',
        )
      "
      primary-button-kind="danger"
      :cancel-label="t('common.cancel')"
      :close-aria-label="t('common.close')"
      :primary-button-loading="mutation.isLoading.value"
      :primary-button-disabled="mutation.isLoading.value"
      @close="confirmation = undefined"
      @primary-click="
        confirmation &&
        mutation.mutate({
          path: `access/${confirmation.kind === 'request' ? 'requests' : 'connections'}/${confirmation.id}`,
          method: 'DELETE',
        })
      "
    >
      <p>{{ confirmation?.name }}</p>
      <p v-if="confirmation?.kind === 'connection'">
        {{ t('account.disconnectHelp') }}
      </p>
      <ErrorNotice v-if="mutation.error.value" :error="mutation.error.value" />
    </NeModal>
  </div>
</template>
