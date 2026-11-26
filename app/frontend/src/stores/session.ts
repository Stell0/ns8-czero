import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  ApiError,
  bindContext,
  boundary,
  endSession,
  request,
  StaleResponse,
} from '../api/client'

export interface Space {
  id: string
  name: string
  shared: boolean
  readable_by_all: boolean
  role: 'reader' | 'editor' | 'admin'
  revision: number
}
export interface Profile {
  id: string
  account_id?: string
  username: string
  role: Space['role']
  is_owner: boolean
  csrf_token: string
  browser_session?: { remembered: boolean }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function sameAuthority(
  me: Profile,
  found: Space,
  previous?: Profile,
  selected?: Space,
) {
  return (
    me.id === previous?.id &&
    me.role === previous?.role &&
    me.csrf_token === previous?.csrf_token &&
    found.role === selected?.role
  )
}

export const useSession = defineStore('session', () => {
  const profile = ref<Profile>()
  const spaces = ref<Space[]>([])
  const space = ref<Space>()
  const ready = ref(false)
  const loading = ref(false)
  const error = ref<unknown>()
  const generation = ref(0)
  let sequence = 0
  let selector: string | null | (string | null)[] = null
  const account = computed(
    () => profile.value?.id || profile.value?.account_id || '',
  )
  const canWrite = computed(
    () => ready.value && ['editor', 'admin'].includes(space.value?.role || ''),
  )
  const isAdmin = computed(() => profile.value?.role === 'admin')
  bindContext(() => ({
    csrf: profile.value?.csrf_token,
    space: space.value?.id,
    ready: ready.value,
  }))
  boundary.onClear((rejection) => {
    const previous =
      ready.value && rejection
        ? { profile: profile.value, space: space.value, rejection }
        : undefined
    const epoch = boundary.epoch
    generation.value++
    ready.value = false
    profile.value = undefined
    space.value = undefined
    spaces.value = []
    if (previous) {
      // Let every boundary listener erase its private state before rechecking.
      queueMicrotask(() => {
        if (boundary.epoch === epoch) void load(selector, previous)
      })
    }
  })

  async function load(
    selected: string | null | (string | null)[] = selector,
    previous?: { profile?: Profile; space?: Space; rejection: ApiError },
  ) {
    const current = ++sequence
    boundary.invalidate()
    loading.value = true
    error.value = undefined
    selector = Array.isArray(selected) ? [...selected] : selected
    try {
      if (
        Array.isArray(selected) ||
        (selected !== null && !uuid.test(selected))
      )
        throw new ApiError(422, 'invalid_space_request')
      const me = await request<Profile>('me', {}, false)
      const collected: Space[] = []
      for (let offset = 0; ; offset += 100) {
        const result = await request<{ spaces: Space[] }>(
          `spaces?limit=100&offset=${offset}`,
          {},
          false,
        )
        if (current !== sequence) return
        collected.push(...result.spaces)
        if (result.spaces.length < 100) break
      }
      if (current !== sequence) return
      profile.value = me
      spaces.value = collected
      space.value =
        selected === null
          ? collected.find((s) => s.shared)
          : collected.find((s) => s.id === selected.toLowerCase())
      if (!space.value) throw new ApiError(403, 'space_unavailable')
      // Remounting a view with unchanged authority can repeat the rejected request.
      if (
        previous &&
        sameAuthority(me, space.value, previous.profile, previous.space)
      )
        throw previous.rejection
      ready.value = true
    } catch (cause) {
      if (current === sequence && !(cause instanceof StaleResponse))
        error.value = cause
    } finally {
      if (current === sequence) loading.value = false
    }
  }

  async function verify() {
    if (!ready.value || document.hidden) return
    const current = sequence
    const previous = profile.value
    const selected = space.value
    try {
      const [me, found] = await Promise.all([
        request<Profile>('me', {}, false),
        request<Space>(`spaces/${selected!.id}`, {}, false),
      ])
      if (current !== sequence || !ready.value) return
      if (!sameAuthority(me, found, previous, selected)) await load()
      else if (found.revision > (space.value?.revision || 0)) {
        // Refresh policy metadata without discarding an unchanged-authority draft.
        space.value = found
        spaces.value = spaces.value.map((item) =>
          item.id === found.id ? found : item,
        )
      }
    } catch (cause) {
      if (
        current !== sequence ||
        !ready.value ||
        cause instanceof StaleResponse
      )
        return
      error.value = cause
    }
  }

  async function logout() {
    try {
      const value = await endSession()
      location.assign(value.logout_url)
    } catch (cause) {
      if (cause instanceof StaleResponse) return
      boundary.invalidate()
      error.value = cause
    }
  }
  return {
    profile,
    spaces,
    space,
    ready,
    loading,
    error,
    generation,
    account,
    canWrite,
    isAdmin,
    load,
    verify,
    logout,
  }
})
