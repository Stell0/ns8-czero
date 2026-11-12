<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { knowledge } from '../api/knowledge'
import { useResource } from '../api/queries'
import ResourceState from '../components/ResourceState.vue'
import KnowledgeTree from '../components/KnowledgeTree.vue'
import TableCollections from '../components/TableCollections.vue'
const { t } = useI18n()
const { data, error, isPending } = useResource(
  () => 'home',
  () => knowledge.pages(),
)
</script>
<template>
  <div class="space-y-6">
    <div>
      <h2 class="mb-3 text-3xl font-medium">{{ t('home.title') }}</h2>
      <p class="text-text-secondary">{{ t('home.intro') }}</p>
    </div>
    <TableCollections />
    <h2 class="text-xl font-medium">{{ t('home.sections') }}</h2>
    <ResourceState
      :error="error"
      :loading="isPending"
      :empty="data?.pages.length === 0"
      ><KnowledgeTree v-if="data" :pages="data.pages"
    /></ResourceState>
    <RouterLink
      v-if="data?.pages.length === 100"
      to="/wiki"
      class="text-link"
      >{{ t('common.more') }}</RouterLink
    >
    <RouterLink to="/sources" class="text-link">{{
      t('home.sources')
    }}</RouterLink>
  </div>
</template>
