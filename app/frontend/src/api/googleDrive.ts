export const drivePath = 'automatic-sources/google-drive'

export interface DriveConnection {
  available: boolean
  connected: boolean
  offline: boolean
}

export interface DrivePreview {
  folder_name: string
  complete: boolean
  preview_token: string
  items: { title: string; outcome: 'include' | 'skip'; reason: string }[]
}

// Only the C0 editing context crosses the Google redirect. The folder link,
// preview and Google account data stay out of persistent browser storage.
const returnKey = 'c0-drive-editor'
export function rememberDriveEditor(
  account: string,
  space: string,
  id?: string,
) {
  sessionStorage.setItem(returnKey, JSON.stringify({ account, space, id }))
}

export function takeDriveEditor(account: string, space: string) {
  const raw = sessionStorage.getItem(returnKey)
  sessionStorage.removeItem(returnKey)
  if (!raw) return
  try {
    const value = JSON.parse(raw)
    if (
      value?.account === account &&
      value.space === space &&
      typeof value.id === 'string'
    )
      return value.id as string
  } catch {
    // The return marker is optional and never grants access.
  }
}
