<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NeButton } from '@nethesis/vue-components'
import { knowledge, type Page, type PageSummary } from '../api/knowledge'
import { ApiError, apiURL, request } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import DocumentReader from '../components/DocumentReader.vue'
import KnowledgeTree from '../components/KnowledgeTree.vue'
const { t } = useI18n(),
  route = useRoute(),
  router = useRouter()
const id = computed(() => String(route.params.id || ''))
const offset = ref(0),
  earlier = ref<PageSummary[]>([])
const list = useResource(
  () => `wiki:${offset.value}`,
  () => knowledge.pages(offset.value),
  () => !id.value,
)
const page = useResource(
  () => `page:${id.value}:${route.query.revision || ''}`,
  () =>
    knowledge.page(
      id.value,
      typeof route.query.revision === 'string'
        ? route.query.revision
        : undefined,
    ),
  () => !!id.value,
)
const factsOffset = computed(() =>
  Math.max(0, Number(route.query.facts_offset) || 0),
)
const facts = useResource(
  () => `page-facts:${id.value}:${factsOffset.value}`,
  async () => {
    const result = await knowledge.claims(id.value, factsOffset.value)
    return Promise.all(result.claims.map((claim) => knowledge.claim(claim.id)))
  },
  () => !!page.data.value,
)
const breadcrumbs = useResource(
  () => `wiki-parents:${page.data.value?.slug || ''}`,
  () =>
    Promise.all(
      (page.data.value?.slug.split('/').slice(0, -1) || []).map(
        async (name, index, parts) => {
          const slug = parts.slice(0, index + 1).join('/')
          try {
            const parent = await request<Page>(
              `wiki/pages/resolve?slug=${encodeURIComponent(slug)}`,
            )
            return { slug, label: parent.content.title, id: parent.id }
          } catch (error) {
            if (error instanceof ApiError && error.status === 404)
              return { slug, label: name.replaceAll('-', ' '), id: '' }
            throw error
          }
        },
      ),
    ),
  () => !!page.data.value,
)
const pages = computed(() => [
  ...new Map(
    [...earlier.value, ...(list.data.value?.pages || [])].map((page) => [
      page.id,
      page,
    ]),
  ).values(),
])
function more() {
  earlier.value.push(...(list.data.value?.pages || []))
  offset.value += 100
}
</script>
<template>
  <div class="space-y-6">
    <ResourceState
      v-if="!id"
      :error="list.error.value"
      :loading="list.isPending.value"
    >
      <KnowledgeTree :pages="pages" />
      <NeButton
        v-if="list.data.value?.pages.length === 100"
        kind="secondary"
        @click="more"
        >{{ t('common.more') }}</NeButton
      >
    </ResourceState>
    <ResourceState
      v-else
      :error="page.error.value"
      :loading="page.isPending.value"
    >
      <template v-if="page.data.value">
        <nav :aria-label="t('nav.wiki')" class="flex flex-wrap gap-2 text-sm">
          <RouterLink to="/wiki" class="text-link">{{
            t('nav.wiki')
          }}</RouterLink
          ><span v-for="parent in breadcrumbs.data.value" :key="parent.slug">
            /
            <RouterLink
              v-if="parent.id"
              :to="`/wiki/${parent.id}`"
              class="text-link"
              >{{ parent.label }}</RouterLink
            >
            <span v-else>{{ parent.label }}</span>
          </span>
        </nav>
        <h2 class="text-2xl font-medium">
          {{ page.data.value.content.title }}
        </h2>
        <div class="flex gap-4">
          <a
            v-for="format in ['markdown', 'json']"
            :key="format"
            class="text-link"
            :href="
              apiURL(
                `wiki/pages/${id}/export?format=${format}&revision=${page.data.value.content.number}`,
              )
            "
            >{{ t(`reader.${format}`) }}</a
          >
        </div>
        <DocumentReader :body="page.data.value.content.body" />
        <ResourceState
          :error="facts.error.value"
          :loading="facts.isPending.value"
        >
          <section
            v-if="facts.data.value?.length"
            class="space-y-4 border-t border-default pt-6"
          >
            <h2 class="text-xl font-medium">{{ t('reader.facts') }}</h2>
            <div
              v-for="claim in facts.data.value"
              :key="claim.id"
              class="rounded-lg bg-elevation-1 p-4"
            >
              <h3>
                <RouterLink
                  :to="`/explore/claims/${claim.id}`"
                  class="text-link"
                  >{{ claim.predicate }}</RouterLink
                >
              </h3>
              <p>{{ Object.values(claim.value).join(' · ') }}</p>
              <p v-if="claim.evidence_stale">{{ t('errors.superseded') }}</p>
              <ul>
                <li v-for="citation in claim.evidence" :key="citation.chunk_id">
                  <span v-if="citation.status === 'superseded'">{{
                    t('errors.superseded')
                  }}</span
                  ><RouterLink
                    v-else
                    class="text-link"
                    :to="`/evidence/${citation.chunk_id}`"
                    >{{ citation.title }}</RouterLink
                  >
                </li>
              </ul>
            </div>
          </section>
          <div
            v-if="factsOffset || facts.data.value?.length === 20"
            class="flex gap-3"
          >
            <NeButton
              kind="secondary"
              :disabled="!factsOffset"
              @click="
                router.push({
                  query: { ...route.query, facts_offset: factsOffset - 20 },
                })
              "
              >{{ t('common.previous') }}</NeButton
            >
            <NeButton
              kind="secondary"
              :disabled="facts.data.value?.length !== 20"
              @click="
                router.push({
                  query: { ...route.query, facts_offset: factsOffset + 20 },
                })
              "
              >{{ t('common.next') }}</NeButton
            >
          </div>
        </ResourceState>
      </template>
    </ResourceState>
  </div>
</template>
