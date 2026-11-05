<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import WorkspaceAccess from '../components/admin/WorkspaceAccess.vue'
import ProtectedSpaces from '../components/admin/ProtectedSpaces.vue'
import TechnicalClients from '../components/admin/TechnicalClients.vue'
import BackgroundWork from '../components/admin/BackgroundWork.vue'
const route = useRoute(),
  { t } = useI18n()
</script>
<template>
  <div class="space-y-6">
    <nav class="flex flex-wrap gap-5" :aria-label="t('nav.admin')">
      <RouterLink to="/admin" class="text-link">{{
        t('admin.people')
      }}</RouterLink
      ><RouterLink
        v-for="area in ['spaces', 'advanced', 'work']"
        :key="area"
        :to="`/admin/${area}`"
        class="text-link"
        >{{ t(`nav.${area}`) }}</RouterLink
      >
    </nav>
    <ProtectedSpaces v-if="route.params.area === 'spaces'" /><TechnicalClients
      v-else-if="route.params.area === 'advanced'"
    /><BackgroundWork
      v-else-if="route.params.area === 'work'"
    /><WorkspaceAccess v-else />
  </div>
</template>
