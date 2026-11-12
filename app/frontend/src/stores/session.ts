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
  boundary.onClear(() => {
    generation.value++
    ready.value = false
    profile.value = undefined
    space.value = undefined
    spaces.value = []
  })

  async function load(selected: string | null | (string | null)[] = selector) {
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
      if (current !== sequence) return
      if (
        me.id !== previous?.id ||
        me.role !== previous?.role ||
        me.csrf_token !== previous?.csrf_token ||
        found.role !== selected?.role ||
        found.revision !== selected?.revision
      )
        await load()
    } catch (cause) {
      if (!(cause instanceof StaleResponse)) error.value = cause
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
