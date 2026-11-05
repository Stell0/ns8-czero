<script setup lang="ts">
import { computed } from 'vue'
import {
  RouterLink,
  useRoute,
  useRouter,
  type RouterLinkProps,
} from 'vue-router'
const props = defineProps<RouterLinkProps>()
const route = useRoute(),
  router = useRouter()
const target = computed(() => {
  const resolved = router.resolve(props.to)
  if (
    !route.query.space_id ||
    'space_id' in resolved.query ||
    resolved.path.startsWith('/auth/')
  )
    return props.to
  return {
    ...resolved,
    query: { ...resolved.query, space_id: route.query.space_id },
  }
})
</script>
<template>
  <RouterLink v-bind="props" :to="target"><slot /></RouterLink>
</template>
