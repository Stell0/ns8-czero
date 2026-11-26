// Availability is presentation metadata; Core still checks all authority.
function hasFeature(name: string) {
  return (
    document
      .querySelector(`meta[name="c0-${name}"]`)
      ?.getAttribute('content') === 'true'
  )
}

export function automaticSourcesAvailable() {
  return hasFeature('automatic-sources')
}

export function websitePdfAttachmentsAvailable() {
  return hasFeature('website-pdf-attachments')
}

export function ingestionDiagnosticsAvailable() {
  return hasFeature('ingestion-diagnostics')
}
