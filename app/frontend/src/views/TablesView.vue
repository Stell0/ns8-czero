<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  NeButton,
  NeSideDrawer,
  NeCheckbox,
  NeListbox,
  NeTextInput,
  NeTable,
  NeTableHead,
  NeTableHeadCell,
  NeTableBody,
  NeTableRow,
  NeTableCell,
} from '@nethesis/vue-components'
import { request } from '../api/client'
import { useResource } from '../api/queries'
import {
  fieldLabel,
  scalar,
  type RecordType,
  type TableRecord,
} from '../api/tables'
import ResourceState from '../components/ResourceState.vue'
import TableCollections from '../components/TableCollections.vue'
import RecordValue from '../components/RecordValue.vue'
const route = useRoute(),
  router = useRouter(),
  { t } = useI18n()
const type = computed(() => String(route.params.type || ''))
const offset = computed(() =>
  Math.min(100000, Math.max(0, Math.floor(Number(route.query.offset) || 0))),
)
const sort = computed(() => String(route.query.sort || ''))
const direction = computed(() =>
  route.query.direction === 'desc' ? 'desc' : 'asc',
)
const definition = useResource(
  () => `table-type:${type.value}`,
  () =>
    request<RecordType>(
      `object-types/${encodeURIComponent(type.value)}`,
      {},
      false,
    ),
  () => !!type.value,
)
const fields = computed(() =>
  Object.entries(definition.data.value?.schema.properties || {}),
)
const visible = ref<string[]>([])
const filterField = ref(''),
  filterValue = ref(''),
  filterTag = ref('')
watch(
  [type, () => route.query.space_id, () => definition.data.value],
  () => {
    visible.value = fields.value
      .filter(([, schema]) => scalar(schema))
      .slice(0, 6)
      .map(([key]) => key)
    filterField.value = ''
    filterValue.value = ''
    filterTag.value = ''
  },
  { immediate: true },
)
const filterError = ref(false)
function applyFilter() {
  const schema = definition.data.value?.schema.properties?.[filterField.value]
  let value: unknown = filterValue.value
  if (schema?.type === 'integer' || schema?.type === 'number') {
    value = Number(filterValue.value)
    if (
      !filterValue.value.trim() ||
      !Number.isFinite(value) ||
      (schema.type === 'integer' && !Number.isInteger(value))
    ) {
      filterError.value = true
      return
    }
  } else if (schema?.type === 'boolean') {
    if (!['true', 'false'].includes(filterValue.value)) {
      filterError.value = true
      return
    }
    value = filterValue.value === 'true'
  }
  filterError.value = false
  void router.push({
    query: {
      ...route.query,
      offset: 0,
      where: schema
        ? JSON.stringify({ [filterField.value]: value })
        : undefined,
      tag: filterTag.value || undefined,
    },
  })
}
const records = useResource(
  () =>
    `table:${type.value}:${offset.value}:${sort.value}:${direction.value}:${String(route.query.where || '')}:${String(route.query.tag || '')}`,
  () => {
    const params = new URLSearchParams({
      type_name: type.value,
      limit: '50',
      offset: String(offset.value),
      where: String(route.query.where || '{}'),
    })
    if (sort.value) {
      params.set('sort', sort.value)
      params.set('direction', direction.value)
    }
    if (route.query.tag) params.set('tag', String(route.query.tag))
    return request<{ objects: TableRecord[] }>(`objects?${params}`)
  },
  () => !!definition.data.value && !!type.value,
)
const selectedId = ref('')
const record = computed(() =>
  definition.data.value
    ? records.data.value?.objects.find((item) => item.id === selectedId.value)
    : undefined,
)
watch(
  () => route.fullPath,
  () => {
    selectedId.value = ''
  },
)
function selectSort(value: unknown) {
  if (String(value) === sort.value) return
  void router.push({
    query: { ...route.query, sort: String(value) || undefined, offset: 0 },
  })
}
function sortBy(key: string) {
  void router.push({
    query: {
      ...route.query,
      sort: key,
      direction:
        sort.value === key && direction.value === 'asc' ? 'desc' : 'asc',
      offset: 0,
    },
  })
}
function column(key: string, checked: boolean) {
  visible.value = checked
    ? [...visible.value, key]
    : visible.value.filter((item) => item !== key)
}
</script>
<template>
  <div class="space-y-6">
    <TableCollections v-if="!type" />
    <template v-else>
      <RouterLink to="/tables" class="text-link">{{
        t('nav.tables')
      }}</RouterLink>
      <ResourceState
        :error="definition.error.value"
        :loading="definition.isPending.value"
      >
        <template v-if="definition.data.value">
          <h2 class="text-2xl font-medium">
            {{ definition.data.value.label }}
          </h2>
          <details>
            <summary>{{ t('tables.columns') }}</summary>
            <div class="grid gap-2 sm:grid-cols-3">
              <NeCheckbox
                v-for="[key, schema] in fields"
                :key="key"
                :model-value="visible.includes(key)"
                :label="fieldLabel(key, schema)"
                @update:model-value="column(key, $event)"
              />
            </div>
          </details>
          <div class="flex flex-wrap items-end gap-3">
            <NeListbox
              :model-value="sort"
              :label="t('tables.sort')"
              :options="[
                { id: '', label: t('tables.defaultOrder') },
                ...fields
                  .filter(([, schema]) => scalar(schema))
                  .map(([key, schema]) => ({
                    id: key,
                    label: fieldLabel(key, schema),
                  })),
                { id: '@created_at', label: t('tables.created') },
                { id: '@updated_at', label: t('common.updated') },
                { id: '@revision', label: t('tables.revision') },
              ]"
              :no-options-label="t('common.options')"
              :optional-label="t('common.optional')"
              @update:model-value="selectSort"
            />
            <NeButton
              kind="secondary"
              :disabled="!sort"
              @click="sortBy(sort)"
              >{{
                t(
                  direction === 'asc'
                    ? 'tables.ascending'
                    : 'tables.descending',
                )
              }}</NeButton
            >
          </div>
          <form
            class="flex flex-wrap items-end gap-3"
            @submit.prevent="applyFilter"
          >
            <NeListbox
              v-model="filterField"
              :label="t('tables.filterField')"
              :options="[
                { id: '', label: t('tables.all') },
                ...fields
                  .filter(([, s]) => scalar(s))
                  .map(([key, schema]) => ({
                    id: key,
                    label: fieldLabel(key, schema),
                  })),
              ]"
              :no-options-label="t('common.options')"
              :optional-label="t('common.optional')"
            />
            <NeTextInput
              v-model="filterValue"
              :label="t('tables.filterValue')"
              :invalid-message="filterError ? t('errors.invalid') : ''"
            />
            <NeTextInput v-model="filterTag" :label="t('tables.tag')" />
            <NeButton type="submit" kind="secondary">{{
              t('tables.apply')
            }}</NeButton>
            <NeButton
              kind="tertiary"
              @click="
                router.push({ query: { space_id: route.query.space_id } })
              "
              >{{ t('tables.reset') }}</NeButton
            >
          </form>
          <p v-if="route.query.where || route.query.tag" class="break-words">
            {{ t('tables.activeFilter') }} {{ route.query.where }}
            {{ route.query.tag }}
          </p>
          <ResourceState
            :error="records.error.value"
            :loading="records.isPending.value"
            :empty="records.data.value?.objects.length === 0"
          >
            <NeTable
              :aria-label="definition.data.value.label"
              card-breakpoint="md"
            >
              <NeTableHead>
                <NeTableHeadCell
                  v-for="[key, schema] in fields.filter(([key]) =>
                    visible.includes(key),
                  )"
                  :key="key"
                  :aria-sort="
                    sort === key
                      ? direction === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  "
                >
                  <NeButton
                    v-if="scalar(schema)"
                    kind="tertiary"
                    @click="sortBy(key)"
                    >{{ fieldLabel(key, schema)
                    }}{{
                      sort === key ? (direction === 'asc' ? ' ↑' : ' ↓') : ''
                    }}</NeButton
                  ><span v-else>{{ fieldLabel(key, schema) }}</span>
                </NeTableHeadCell>
                <NeTableHeadCell>{{ t('common.details') }}</NeTableHeadCell>
              </NeTableHead>
              <NeTableBody
                ><NeTableRow
                  v-for="record in records.data.value?.objects"
                  :key="record.id"
                >
                  <NeTableCell
                    v-for="[key, schema] in fields.filter(([key]) =>
                      visible.includes(key),
                    )"
                    :key="key"
                    :data-label="fieldLabel(key, schema)"
                    ><RecordValue :value="record.data[key]" :schema="schema"
                  /></NeTableCell>
                  <NeTableCell :data-label="t('common.details')"
                    ><NeButton kind="secondary" @click="selectedId = record.id"
                      >{{ t('common.details') }} · {{ record.id }}</NeButton
                    ></NeTableCell
                  >
                </NeTableRow></NeTableBody
              >
            </NeTable>
          </ResourceState>
          <div class="flex gap-3">
            <NeButton
              kind="secondary"
              :disabled="offset === 0"
              @click="
                router.push({ query: { ...route.query, offset: offset - 50 } })
              "
              >{{ t('common.previous') }}</NeButton
            ><NeButton
              kind="secondary"
              :disabled="
                records.data.value?.objects.length !== 50 || offset >= 100000
              "
              @click="
                router.push({ query: { ...route.query, offset: offset + 50 } })
              "
              >{{ t('common.next') }}</NeButton
            >
          </div>
        </template>
      </ResourceState>
      <NeSideDrawer
        v-if="record"
        :is-shown="true"
        :title="record.id"
        :close-aria-label="t('common.close')"
        @close="selectedId = ''"
        ><dl class="space-y-3">
          <template v-for="[key, schema] in fields" :key="key"
            ><dt class="font-medium">
              {{ fieldLabel(key, schema) }}
            </dt>
            <dd>
              <RecordValue
                :value="record.data[key]"
                :schema="schema"
                expanded
              /></dd
          ></template>
        </dl>
        <dl class="mt-4 space-y-2">
          <dt>{{ t('tables.revision') }}</dt>
          <dd>{{ record.revision }}</dd>
          <dt>{{ t('tables.created') }}</dt>
          <dd>{{ record.created_at }}</dd>
          <dt>{{ t('common.updated') }}</dt>
          <dd>{{ record.updated_at }}</dd>
          <dt>{{ t('tables.tag') }}</dt>
          <dd>{{ record.tags.join(', ') }}</dd>
        </dl>
        <RouterLink :to="`/explore/records/${record.id}`" class="text-link">{{
          t('tables.relationships')
        }}</RouterLink>
      </NeSideDrawer>
    </template>
  </div>
</template>
