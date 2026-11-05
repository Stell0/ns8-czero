// Retry only the same operation and body. Keep identities in memory, never storage.
export class ReplayIdentity {
  private attempt?: { fingerprint: string; key: string }
  data<T extends object>(path: string, body: T) {
    const fingerprint = JSON.stringify([path, body])
    if (this.attempt?.fingerprint !== fingerprint)
      this.attempt = { fingerprint, key: crypto.randomUUID() }
    return { ...body, idempotency_key: this.attempt.key }
  }
  clear() {
    this.attempt = undefined
  }
}
