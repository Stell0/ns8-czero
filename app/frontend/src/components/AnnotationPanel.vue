<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { request } from '../api/client'
import { useResource } from '../api/queries'
import ResourceState from './ResourceState.vue'
const props = defineProps<{ kind: string; id: string; revision: number }>()
const { t } = useI18n(),
  open = ref(false)
const { data, error, isPending } = useResource(
  () => `annotations:${props.kind}:${props.id}:${props.revision}`,
  async () =>
    Promise.all(
      ['applicability', 'verification'].map((namespace) =>
        request<{
          namespace: string
          status: string
          value: Record<string, unknown> | null
        }>(
          `knowledge/annotations/${props.kind}/${props.id}/${props.revision}/${namespace}`,
        ),
      ),
    ),
  () => open.value,
)
</script>
<template>
  <details @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary>{{ t('explore.annotations') }}</summary>
    <ResourceState v-if="open" :error="error" :loading="isPending"
      ><dl
        v-for="annotation in data"
        :key="annotation.namespace"
        class="mt-4 grid gap-3 sm:grid-cols-2"
      >
        <dt>{{ annotation.namespace }}</dt>
        <dd>{{ annotation.status }}</dd>
        <template v-for="(value, key) in annotation.value" :key="key"
          ><dt>{{ key }}</dt>
          <dd>{{ value }}</dd></template
        >
      </dl></ResourceState
    >
  </details>
</template>
