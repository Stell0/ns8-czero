// Availability is presentation metadata; Core still checks all authority.
export function automaticSourcesAvailable() {
  try {
    return (
      JSON.parse(document.getElementById('c0-boot')?.textContent || '{}')
        .features?.automatic_sources === true
    )
  } catch {
    return false
  }
}
