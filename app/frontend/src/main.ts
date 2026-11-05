import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { PiniaColada, useQueryCache, useMutationCache } from '@pinia/colada'
import { createI18n } from 'vue-i18n'
import { config } from '@fortawesome/fontawesome-svg-core'
import { boundary } from './api/client'
import { router } from './router'
import en from './locales/en.json'
import it from './locales/it.json'
import App from './App.vue'
import SpaceLink from './components/SpaceLink.vue'
import './style.css'

config.autoAddCss = false
const pinia = createPinia()
const app = createApp(App)
app
  .use(pinia)
  .use(PiniaColada)
  .use(
    createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: 'en',
      messages: { en, it },
    }),
  )
  .use(router)
const queries = useQueryCache(pinia)
const mutations = useMutationCache(pinia)
boundary.onClear(() => {
  queries.cancelQueries()
  for (const entry of queries.getEntries()) queries.remove(entry)
  for (const entry of mutations.getEntries()) mutations.remove(entry)
})
window.addEventListener('pagehide', () => boundary.invalidate())
window.addEventListener('pageshow', (event) => {
  if (event.persisted) location.reload()
})
app.component('RouterLink', SpaceLink)
router.isReady().then(() => app.mount('#app'))
