<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NeButton } from '@nethesis/vue-components'
import { request } from '../api/client'
import { useResource } from '../api/queries'
import type { RecordType } from '../api/tables'
import ResourceState from './ResourceState.vue'
const { t } = useI18n()
const route = useRoute()
const offset = computed(() =>
  Math.min(
    100000,
    Math.max(0, Math.floor(Number(route.query.collections_offset) || 0)),
  ),
)
const collections = useResource(
  () => `table-collections:${offset.value}`,
  () =>
    request<{ types: RecordType[] }>(
      `object-types?populated_only=true&limit=50&offset=${offset.value}`,
    ),
)
</script>
<template>
  <section class="space-y-3" :aria-label="t('nav.tables')">
    <h2 class="text-xl font-medium">{{ t('nav.tables') }}</h2>
    <ResourceState
      :error="collections.error.value"
      :loading="collections.isPending.value"
      :empty="collections.data.value?.types.length === 0"
    >
      <ul class="space-y-2">
        <li
          v-for="collection in collections.data.value?.types"
          :key="collection.name"
        >
          <RouterLink
            :to="{
              path: `/tables/${collection.name}`,
              query: { space_id: route.query.space_id },
            }"
            class="text-link"
            >{{ collection.label }}</RouterLink
          >
        </li>
      </ul>
      <div class="flex gap-3">
        <NeButton
          kind="secondary"
          :disabled="offset === 0"
          @click="
            $router.push({
              query: { ...route.query, collections_offset: offset - 50 },
            })
          "
          >{{ t('common.previous') }}</NeButton
        >
        <NeButton
          kind="secondary"
          :disabled="
            collections.data.value?.types.length !== 50 || offset >= 100000
          "
          @click="
            $router.push({
              query: { ...route.query, collections_offset: offset + 50 },
            })
          "
          >{{ t('common.next') }}</NeButton
        >
      </div>
    </ResourceState>
  </section>
</template>
