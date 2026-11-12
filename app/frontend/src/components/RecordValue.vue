<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NeBadgeV2,
  NeTable,
  NeTableHead,
  NeTableHeadCell,
  NeTableBody,
  NeTableRow,
  NeTableCell,
} from '@nethesis/vue-components'
import { fieldLabel, preview, type FieldSchema } from '../api/tables'
const props = defineProps<{
  value?: unknown
  schema?: FieldSchema
  expanded?: boolean
}>()
const { t } = useI18n()
const object = computed(
  () =>
    props.value !== null &&
    typeof props.value === 'object' &&
    !Array.isArray(props.value),
)
const rows = computed(() => (Array.isArray(props.value) ? props.value : []))
const fields = computed(() =>
  Object.entries(props.schema?.items?.properties || {}),
)
</script>
<template>
  <span v-if="value === undefined">{{ t('tables.missing') }}</span>
  <span v-else-if="value === null">{{ t('tables.null') }}</span>
  <span v-else-if="value === ''">{{ t('tables.empty') }}</span>
  <span v-else-if="typeof value === 'boolean'">{{
    t(value ? 'tables.yes' : 'tables.no')
  }}</span>
  <details v-else-if="Array.isArray(value)" :open="expanded">
    <summary>{{ t('tables.items', { count: value.length }) }}</summary>
    <NeTable
      v-if="schema?.items?.type === 'object' && fields.length"
      :aria-label="t('tables.items', { count: value.length })"
      card-breakpoint="md"
    >
      <NeTableHead
        ><NeTableHeadCell v-for="[key, field] in fields" :key="key">{{
          fieldLabel(key, field)
        }}</NeTableHeadCell></NeTableHead
      >
      <NeTableBody
        ><NeTableRow v-for="(row, index) in rows" :key="index"
          ><NeTableCell
            v-for="[key, field] in fields"
            :key="key"
            :data-label="fieldLabel(key, field)"
            ><RecordValue
              :value="row?.[key]"
              :schema="field" /></NeTableCell></NeTableRow
      ></NeTableBody>
    </NeTable>
    <ol v-else class="space-y-2 pl-4">
      <li v-for="(item, index) in value" :key="index">
        <RecordValue :value="item" :schema="schema?.items" />
      </li>
    </ol>
  </details>
  <details v-else-if="object" :open="expanded">
    <summary>{{ t('tables.object') }}</summary>
    <dl class="space-y-2 pl-4">
      <template
        v-for="(item, key) in value as Record<string, unknown>"
        :key="key"
        ><dt class="font-medium">
          {{ fieldLabel(String(key), schema?.properties?.[key]) }}
        </dt>
        <dd class="break-words">
          <RecordValue :value="item" :schema="schema?.properties?.[key]" /></dd
      ></template>
    </dl>
  </details>
  <NeBadgeV2 v-else-if="schema?.enum">{{ value }}</NeBadgeV2>
  <span v-else class="whitespace-pre-wrap break-words">{{
    expanded ? value : preview(value)
  }}</span>
</template>
