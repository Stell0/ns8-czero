<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NeListbox, NeButton } from '@nethesis/vue-components'
import { request } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import AnnotationPanel from '../components/AnnotationPanel.vue'
const route = useRoute(),
  router = useRouter(),
  { t } = useI18n()
interface Item {
  id: string
  label?: string
  predicate?: string
  type_name?: string
  revision: number
  data?: Record<string, unknown>
  metadata?: Record<string, unknown>
  value?: Record<string, unknown>
  entity_id?: string
  page_id?: string | null
  evidence_stale?: boolean
  aliases?: { label: string }[]
  evidence?: { chunk_id: string; title: string; status?: string }[]
}
const kind = computed(() =>
  ['claims', 'records'].includes(String(route.params.kind))
    ? String(route.params.kind)
    : 'entities',
)
const endpoint = computed(() =>
  kind.value === 'records' ? 'objects' : kind.value,
)
const offset = computed(() => Math.max(0, Number(route.query.offset) || 0))
const id = computed(() => String(route.params.id || ''))
const types = useResource(
  () => 'object-types',
  () =>
    request<{ types: { name: string; label: string }[] }>(
      'object-types',
      {},
      false,
    ),
  () => kind.value === 'records',
)
const selectedType = computed(() =>
  String(route.query.type || types.data.value?.types[0]?.name || ''),
)
const list = useResource(
  () => `${kind.value}:${selectedType.value}:${offset.value}`,
  async () => {
    const params = new URLSearchParams({
      limit: '50',
      offset: String(offset.value),
    })
    if (kind.value === 'records') params.set('type_name', selectedType.value)
    const result = await request<Record<string, Item[]>>(
      `${endpoint.value}?${params}`,
    )
    return result[endpoint.value]
  },
  () => !id.value && (kind.value !== 'records' || !!selectedType.value),
)
const detail = useResource(
  () => `${kind.value}:${id.value}`,
  () => request<Item>(`${endpoint.value}/${encodeURIComponent(id.value)}`),
  () => !!id.value,
)
const relatedOffset = computed(() =>
  Math.max(0, Number(route.query.related_offset) || 0),
)
const relations = useResource(
  () => `relations:${kind.value}:${id.value}:${relatedOffset.value}`,
  () =>
    request<{
      relations: {
        id: string
        source_id: string
        target_id: string
        kind: string
      }[]
    }>(
      `${endpoint.value}/${encodeURIComponent(id.value)}/relations?limit=50&offset=${relatedOffset.value}`,
    ),
  () => !!detail.data.value && kind.value !== 'claims',
)
const entityClaims = useResource(
  () => `entity-claims:${id.value}:${relatedOffset.value}`,
  () =>
    request<{ claims: Item[] }>(
      `claims?entity_id=${encodeURIComponent(id.value)}&limit=50&offset=${relatedOffset.value}`,
    ),
  () => !!detail.data.value && kind.value === 'entities',
)
const references = useResource(
  () => `references:${id.value}:${relatedOffset.value}`,
  () =>
    request<{
      references: {
        id: string
        target_id: string
        target_kind: string
        label_snapshot: string
        missing: boolean
      }[]
    }>(
      `entities/${encodeURIComponent(id.value)}/references?limit=50&offset=${relatedOffset.value}`,
    ),
  () => !!detail.data.value && kind.value === 'entities',
)
function referencePath(kind: string, id: string) {
  if (kind === 'document') return `/sources/${id}?reference=document`
  return (
    {
      object: '/explore/records/',
      page: '/wiki/',
      source: '/sources/',
      chunk: '/evidence/',
    } as Record<string, string>
  )[kind]?.concat(id)
}
</script>
<template>
  <div class="space-y-6">
    <nav class="flex gap-5" :aria-label="t('nav.explore')">
      <RouterLink
        v-for="section in ['entities', 'claims', 'records']"
        :key="section"
        :to="`/explore/${section}`"
        class="text-link"
        >{{ t(`explore.${section}`) }}</RouterLink
      >
    </nav>
    <NeListbox
      v-if="kind === 'records' && !id"
      :model-value="selectedType"
      :label="t('explore.type')"
      :options="
        types.data.value?.types.map((type) => ({
          id: type.name,
          label: type.label,
        })) || []
      "
      :no-options-label="t('common.options')"
      :optional-label="t('common.optional')"
      @update:model-value="
        (value) =>
          router.push({
            query: { ...route.query, type: String(value), offset: 0 },
          })
      "
    />
    <ResourceState
      v-if="!id"
      :error="list.error.value"
      :loading="list.isPending.value"
      :empty="list.data.value?.length === 0"
      ><ul class="space-y-3">
        <li v-for="item in list.data.value" :key="item.id">
          <RouterLink :to="`/explore/${kind}/${item.id}`" class="text-link">{{
            item.label ||
            item.predicate ||
            item.data?.title ||
            item.data?.name ||
            item.id
          }}</RouterLink>
        </li>
      </ul>
      <div class="mt-4 flex gap-3">
        <NeButton
          kind="secondary"
          :disabled="offset === 0"
          @click="
            router.push({ query: { ...route.query, offset: offset - 50 } })
          "
          >{{ t('common.previous') }}</NeButton
        ><NeButton
          kind="secondary"
          :disabled="list.data.value?.length !== 50"
          @click="
            router.push({ query: { ...route.query, offset: offset + 50 } })
          "
          >{{ t('common.next') }}</NeButton
        >
      </div></ResourceState
    >
    <ResourceState
      v-else
      :error="detail.error.value"
      :loading="detail.isPending.value"
      ><div v-if="detail.data.value" class="space-y-6">
        <AnnotationPanel
          :id="id"
          :kind="
            kind === 'records'
              ? 'object'
              : kind === 'claims'
                ? 'claim'
                : 'entity'
          "
          :revision="detail.data.value.revision"
        />
        <h2 class="text-xl font-medium">
          {{
            detail.data.value.label ||
            detail.data.value.predicate ||
            detail.data.value.id
          }}
        </h2>
        <dl class="grid gap-3 sm:grid-cols-2">
          <template
            v-for="(value, key) in detail.data.value.data ||
            detail.data.value.value ||
            detail.data.value.metadata"
            :key="key"
            ><dt>{{ key }}</dt>
            <dd class="break-words">{{ value }}</dd></template
          >
        </dl>
        <p v-if="detail.data.value.aliases?.length">
          {{ detail.data.value.aliases.map((item) => item.label).join(' · ') }}
        </p>
        <p v-if="detail.data.value.evidence_stale">
          {{ t('errors.superseded') }}
        </p>
        <RouterLink
          v-if="detail.data.value.entity_id"
          :to="`/explore/entities/${detail.data.value.entity_id}`"
          class="text-link"
          >{{ t('explore.entity') }}</RouterLink
        >
        <RouterLink
          v-if="detail.data.value.page_id"
          :to="`/wiki/${detail.data.value.page_id}`"
          class="text-link"
          >{{ t('nav.wiki') }}</RouterLink
        >
        <ResourceState
          v-if="kind !== 'claims'"
          :error="relations.error.value"
          :loading="relations.isPending.value"
        >
          <section v-if="relations.data.value">
            <h2 class="mb-3 text-xl font-medium">
              {{ t('explore.relations') }}
            </h2>
            <ul class="space-y-3">
              <li
                v-for="relation in relations.data.value.relations"
                :key="relation.id"
              >
                <RouterLink
                  :to="`/explore/${kind}/${relation.source_id === id ? relation.target_id : relation.source_id}`"
                  class="text-link"
                  >{{ relation.kind }} ·
                  {{
                    relation.source_id === id
                      ? relation.target_id
                      : relation.source_id
                  }}</RouterLink
                >
              </li>
            </ul>
          </section></ResourceState
        >
        <template v-if="kind === 'entities'">
          <section class="space-y-3">
            <h2 class="text-xl font-medium">{{ t('reader.facts') }}</h2>
            <ResourceState
              :error="entityClaims.error.value"
              :loading="entityClaims.isPending.value"
              :empty="!entityClaims.data.value?.claims.length"
              ><ul class="space-y-3">
                <li
                  v-for="claim in entityClaims.data.value?.claims"
                  :key="claim.id"
                >
                  <RouterLink
                    :to="`/explore/claims/${claim.id}`"
                    class="text-link"
                    >{{ claim.predicate }}</RouterLink
                  >
                  <p>{{ claim.value }}</p>
                </li>
              </ul></ResourceState
            >
          </section>
          <section class="space-y-3">
            <h2 class="text-xl font-medium">{{ t('explore.references') }}</h2>
            <ResourceState
              :error="references.error.value"
              :loading="references.isPending.value"
              :empty="!references.data.value?.references.length"
              ><ul>
                <li
                  v-for="item in references.data.value?.references"
                  :key="item.id"
                >
                  <RouterLink
                    v-if="
                      !item.missing &&
                      referencePath(item.target_kind, item.target_id)
                    "
                    :to="referencePath(item.target_kind, item.target_id)!"
                    class="text-link"
                    >{{ item.label_snapshot }}</RouterLink
                  ><span v-else
                    >{{ item.label_snapshot }} · {{ t('errors.missing') }}</span
                  >
                </li>
              </ul></ResourceState
            >
          </section>
        </template>
        <div v-if="kind !== 'claims'" class="flex gap-3">
          <NeButton
            kind="secondary"
            :disabled="!relatedOffset"
            @click="
              router.push({
                query: { ...route.query, related_offset: relatedOffset - 50 },
              })
            "
            >{{ t('common.previous') }}</NeButton
          ><NeButton
            kind="secondary"
            :disabled="
              ![
                relations.data.value?.relations.length,
                entityClaims.data.value?.claims.length,
                references.data.value?.references.length,
              ].includes(50)
            "
            @click="
              router.push({
                query: { ...route.query, related_offset: relatedOffset + 50 },
              })
            "
            >{{ t('common.next') }}</NeButton
          >
        </div>
        <ul>
          <li
            v-for="citation in detail.data.value.evidence"
            :key="citation.chunk_id"
          >
            <span v-if="citation.status === 'superseded'">{{
              t('errors.superseded')
            }}</span
            ><RouterLink
              v-else
              :to="`/evidence/${citation.chunk_id}`"
              class="text-link"
              >{{ citation.title }}</RouterLink
            >
          </li>
        </ul>
      </div></ResourceState
    >
  </div>
</template>
