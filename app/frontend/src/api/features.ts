// Availability is presentation metadata; Core still checks all authority.
export function automaticSourcesAvailable() {
  return (
    document
      .querySelector('meta[name="c0-automatic-sources"]')
      ?.getAttribute('content') === 'true'
  )
}
