import { computed } from 'vue'
import { useQuery } from '@pinia/colada'
import { useSession } from '../stores/session'

export function useResource<T>(
  identity: () => string,
  query: () => Promise<T>,
  enabled = () => true,
  publicData = false,
) {
  const session = useSession()
  const result = useQuery({
    key: () => [
      'c0',
      session.account,
      session.space?.id || '',
      session.generation,
      identity(),
    ],
    query,
    enabled: () => (session.ready || publicData) && enabled(),
    staleTime: 0,
    gcTime: 0,
  })
  // Colada can retain earlier data on a failed refresh; never display it on error.
  const data = computed(() =>
    (session.ready || publicData) && !result.error.value
      ? result.data.value
      : undefined,
  )
  return { ...result, data }
}
