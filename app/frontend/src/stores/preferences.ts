import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { usePreferredDark } from '@vueuse/core'

function saved(key: string) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
export const usePreferences = defineStore('preferences', () => {
  const chosenLanguage = saved('c0-language')
  const language = ref(
    chosenLanguage === 'it' ||
      (!chosenLanguage && navigator.language.startsWith('it'))
      ? 'it'
      : 'en',
  )
  const storedTheme = saved('c0-theme')
  const theme = ref(
    storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : 'system',
  )
  const systemDark = usePreferredDark()
  watch(
    [language, theme, systemDark],
    () => {
      document.documentElement.lang = language.value
      document.documentElement.classList.toggle(
        'dark',
        theme.value === 'dark' ||
          (theme.value === 'system' && systemDark.value),
      )
      try {
        localStorage.setItem('c0-language', language.value)
        localStorage.setItem('c0-theme', theme.value)
      } catch {
        /* Preferences remain usable in memory. */
      }
    },
    { immediate: true },
  )
  return { language, theme }
})
