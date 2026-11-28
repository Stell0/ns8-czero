<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  NeButton,
  NeListbox,
  NeTextInput,
  NeSkeleton,
  NeSideDrawer,
} from '@nethesis/vue-components'
import { useSession } from './stores/session'
import { usePreferences } from './stores/preferences'
import { ApiError, boundary, localURL } from './api/client'
import ErrorNotice from './components/ErrorNotice.vue'

const session = useSession()
const preferences = usePreferences()
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const unavailableFlow =
  JSON.parse(document.getElementById('c0-boot')?.textContent || '{}').error ===
  'flow_unavailable'
    ? location.pathname + location.search
    : null
const authFlow = computed(() => /^\/(auth|oauth)\//.test(route.path))
const signedOut = computed(
  () => session.error instanceof ApiError && session.error.status === 401,
)
const signIn = computed(() => {
  const path = route.fullPath.slice(1).split('#', 1)[0]
  return localURL('/auth/sign-in?return_to=' + encodeURIComponent(path))
})
const menu = ref(false)
function openMenu() {
  document.getElementById('navigation-toggle')?.focus()
  menu.value = true
}
async function closeMenu() {
  const path = route.fullPath
  menu.value = false
  await nextTick()
  // Let the focus trap finish unmounting; navigation owns any new page focus.
  requestAnimationFrame(() => {
    if (!menu.value && route.fullPath === path)
      document.getElementById('navigation-toggle')?.focus()
  })
}
const query = ref('')
const main = ref<HTMLElement>()
const clearDrafts = boundary.onClear(() => {
  query.value = ''
  menu.value = false
})
const destinations = [
  'home',
  'wiki',
  'sources',
  'tables',
  'projects',
  'explore',
  'agents',
  'account',
]
const selected = computed(() => session.space?.id || '')
const title = computed(() => t(String(route.meta.title || 'nav.home')))
watch(
  () => preferences.language,
  (value) => {
    locale.value = value
  },
  { immediate: true },
)
watch(
  [
    () => route.query.space_id,
    () => route.meta.public,
    () => route.meta.optionalSession,
    () => route.fullPath.split('#')[0],
  ],
  (
    [value, isPublic, optional],
    [oldValue, wasPublic, wasOptional, previousLocation],
  ) => {
    if (isPublic && !optional) return
    if (
      previousLocation === undefined ||
      value !== oldValue ||
      isPublic !== wasPublic ||
      optional !== wasOptional ||
      (!session.ready &&
        (session.loading || (session.profile && session.space)))
    )
      void session.load(value ?? null)
  },
  { immediate: true },
)
watch(
  () => route.fullPath,
  async (to, from) => {
    query.value = String(route.query.query || '')
    if (from !== undefined && to.split('#')[0] !== from.split('#')[0]) {
      menu.value = false
      if (!route.hash) {
        await nextTick()
        main.value?.focus()
      }
    }
  },
  { immediate: true },
)
watch(
  title,
  (value) => {
    document.title = `${value} · C0`
  },
  { immediate: true },
)
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  timer = setInterval(() => void session.verify(), 30000)
  document.addEventListener('visibilitychange', session.verify)
})
onUnmounted(() => {
  clearDrafts()
  clearInterval(timer)
  document.removeEventListener('visibilitychange', session.verify)
})
function selectSpace(value: unknown) {
  if (
    typeof value !== 'string' ||
    value === selected.value ||
    session.loading ||
    !session.spaces.some((s) => s.id === value)
  )
    return
  void router.push({ path: '/', query: { space_id: value } })
}
function search() {
  void router.push({
    path: '/search',
    query: {
      ...(route.path === '/search' ? route.query : {}),
      space_id: route.query.space_id,
      query: query.value,
    },
  })
}
</script>

<template>
  <a
    class="skip-link"
    :href="`${localURL(route.fullPath.split('#')[0])}#main`"
    >{{ t('nav.skip') }}</a
  >
  <div class="min-h-screen" :class="!authFlow && 'lg:grid lg:grid-cols-5'">
    <aside
      v-if="!authFlow"
      class="sticky top-0 hidden h-screen overflow-auto border-r border-default bg-elevation-1 p-6 lg:col-span-1 lg:block"
    >
      <div class="flex items-center justify-between gap-4">
        <RouterLink
          to="/"
          class="text-2xl font-medium text-primary-700 dark:text-primary-400"
          >C0</RouterLink
        >
      </div>
      <nav
        id="navigation"
        :aria-label="t('nav.menu')"
        class="mt-6"
        data-c0-navigation
      >
        <ul class="space-y-2">
          <li v-for="destination in destinations" :key="destination">
            <RouterLink
              :to="destination === 'home' ? '/' : `/${destination}`"
              class="nav-link"
              >{{ t(`nav.${destination}`) }}</RouterLink
            >
          </li>
          <li v-if="session.isAdmin">
            <RouterLink to="/admin" class="nav-link">{{
              t('nav.admin')
            }}</RouterLink>
          </li>
        </ul>
      </nav>
    </aside>
    <div class="min-w-0" :class="!authFlow && 'lg:col-span-4'">
      <header
        class="sticky top-0 z-20 flex flex-wrap items-end gap-4 border-b border-default bg-elevation-0 p-4 lg:px-8"
      >
        <div
          class="flex w-full items-center justify-between"
          :class="!authFlow && 'lg:hidden'"
        >
          <RouterLink
            to="/"
            class="text-xl font-medium text-primary-700 dark:text-primary-400"
            >C0</RouterLink
          >
          <NeButton
            v-if="!authFlow"
            id="navigation-toggle"
            kind="tertiary"
            :aria-expanded="menu"
            aria-controls="mobile-navigation"
            @click="openMenu"
            >{{ t('nav.menu') }}</NeButton
          >
        </div>
        <template v-if="session.profile && !authFlow">
          <NeListbox
            class="w-full sm:w-64"
            :model-value="selected"
            :label="t('nav.space')"
            :options="session.spaces.map((s) => ({ id: s.id, label: s.name }))"
            :no-options-label="t('common.options')"
            :optional-label="t('common.optional')"
            @update:model-value="selectSpace"
          />
          <p
            v-if="session.space?.readable_by_all && !session.space.shared"
            class="text-sm text-text-secondary"
          >
            {{ t('admin.audienceReason') }}
          </p>
          <form
            class="flex flex-1 items-end gap-2"
            role="search"
            @submit.prevent="search"
          >
            <NeTextInput
              v-model="query"
              class="min-w-0 flex-1"
              :label="t('search.query')"
              :is-search="true"
              :clear-search-label="t('common.clear')"
            />
            <NeButton type="submit" kind="secondary">{{
              t('nav.search')
            }}</NeButton>
          </form></template
        >
        <template
          v-else-if="
            authFlow || (route.meta.public && !route.meta.optionalSession)
          "
        >
          <NeListbox
            v-model="preferences.language"
            :label="t('account.language')"
            :options="[
              { id: 'en', label: 'English' },
              { id: 'it', label: 'Italiano' },
            ]"
            :no-options-label="t('common.options')"
            :optional-label="t('common.optional')"
          />
          <NeListbox
            v-model="preferences.theme"
            :label="t('account.theme')"
            :options="
              ['system', 'light', 'dark'].map((id) => ({
                id,
                label: t(`account.${id}`),
              }))
            "
            :no-options-label="t('common.options')"
            :optional-label="t('common.optional')"
          />
        </template>
      </header>
      <main
        id="main"
        ref="main"
        tabindex="-1"
        class="mx-auto scroll-mt-72 space-y-6 p-4 outline-none sm:p-6 lg:scroll-mt-32 lg:p-8"
        :class="authFlow ? 'max-w-2xl' : 'max-w-screen-2xl'"
      >
        <h1 class="text-2xl font-medium">{{ title }}</h1>
        <p
          v-if="authFlow && session.profile"
          class="text-sm text-text-secondary"
        >
          {{ t('consent.signedIn', { name: session.profile.username }) }}
        </p>
        <p v-if="unavailableFlow === localURL(route.fullPath)" role="alert">
          {{ t('consent.unavailable') }}
        </p>
        <NeSkeleton
          v-else-if="session.loading && !route.meta.public"
          class="h-24"
          :aria-label="t('common.loading')"
        />
        <template
          v-else-if="
            route.meta.public ||
            (session.ready && (!route.meta.admin || session.isAdmin))
          "
        >
          <RouterView :key="`${session.generation}:${route.path}`" />
        </template>
        <template v-else-if="signedOut">
          <p>{{ t('account.signInRequired') }}</p>
          <a :href="signIn" class="text-link">{{ t('account.signin') }}</a>
        </template>
        <template
          v-else-if="
            session.error instanceof ApiError &&
            session.error.code === 'space_unavailable'
          "
        >
          <p role="alert">{{ t('errors.spaceDenied') }}</p>
          <a
            :href="
              localURL(
                '/' +
                  (session.spaces[0]
                    ? '?space_id=' + session.spaces[0].id
                    : ''),
              )
            "
            class="text-link"
            >{{ t('nav.home') }}</a
          >
        </template>
        <template
          v-else-if="
            !session.profile &&
            session.error instanceof ApiError &&
            session.error.status === 403
          "
        >
          <p role="alert">{{ t('errors.accountDenied') }}</p>
        </template>
        <template
          v-else-if="session.ready && route.meta.admin && !session.isAdmin"
        >
          <p role="alert">{{ t('errors.adminDenied') }}</p>
          <a :href="localURL('/')" class="text-link">{{ t('nav.home') }}</a>
        </template>
        <template v-else>
          <ErrorNotice v-if="session.error" :error="session.error" />
          <p v-else role="alert">{{ t('errors.access') }}</p>
          <NeButton kind="secondary" @click="session.load()">{{
            t('common.reload')
          }}</NeButton>
        </template>
      </main>
    </div>
  </div>
  <NeSideDrawer
    v-if="menu"
    :is-shown="true"
    :title="t('nav.menu')"
    :close-aria-label="t('common.close')"
    @close="closeMenu"
  >
    <nav id="mobile-navigation" :aria-label="t('nav.menu')" data-c0-navigation>
      <ul class="space-y-3">
        <li v-for="destination in destinations" :key="destination">
          <RouterLink
            :to="destination === 'home' ? '/' : `/${destination}`"
            class="nav-link"
            @click="menu = false"
            >{{ t(`nav.${destination}`) }}</RouterLink
          >
        </li>
        <li v-if="session.isAdmin">
          <RouterLink to="/admin" class="nav-link" @click="menu = false">{{
            t('nav.admin')
          }}</RouterLink>
        </li>
      </ul>
    </nav>
  </NeSideDrawer>
</template>
