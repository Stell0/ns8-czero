import { request } from './client'

export interface PageSummary {
  id: string
  slug: string
  title: string
  revision: number
  updated_at: string
}
export interface Page extends PageSummary {
  content: {
    body: string
    number: number
    title: string
    metadata: Record<string, unknown>
  }
}
export interface Source {
  id: string
  title: string
  metadata: Record<string, unknown>
  revision: number
  updated_at: string
  deleted: boolean
}
export interface Version {
  id: string
  source_id: string
  number: number
  state: string
  original_present: boolean
  generation: number
  error_code: string | null
}
export interface SourceDocument {
  id: string
  title: string
  state: string
  media_type: string
  updated_at: string
  metadata: Record<string, unknown>
  multipart: boolean
}
export interface FullDocument extends SourceDocument {
  body: string | null
  revision_id: string
  number: number | null
  parts: { source_id: string; version_id: string }[]
  original_version_ids: string[]
}
export interface Citation {
  chunk_id: string
  source_id: string
  version_id: string
  title: string
  body: string
  content_hash: string
  status?: string
}
export interface Claim {
  id: string
  predicate: string
  value: Record<string, unknown>
  evidence_stale: boolean
  evidence?: Citation[]
}
export interface SearchHit {
  id: string
  kind: 'chunk' | 'wiki_revision'
  title: string
  excerpt: string
  citation: Citation | null
  wiki: { page_id: string; revision: number } | null
}
export const knowledge = {
  pages: (offset = 0) =>
    request<{ pages: PageSummary[] }>(`wiki/pages?limit=100&offset=${offset}`),
  page: (id: string, revision?: string) =>
    request<Page>(
      `wiki/pages/${encodeURIComponent(id)}${revision ? `?revision=${encodeURIComponent(revision)}` : ''}`,
    ),
  claims: (page: string, offset = 0) =>
    request<{ claims: Claim[] }>(
      `claims?page_id=${encodeURIComponent(page)}&limit=20&offset=${offset}`,
    ),
  claim: (id: string) => request<Claim>(`claims/${encodeURIComponent(id)}`),
  sources: (offset = 0) =>
    request<{ documents: SourceDocument[] }>(
      `source-documents?limit=50&offset=${offset}`,
    ),
  document: (id: string, snapshot?: string) =>
    request<FullDocument>(
      `source-documents/${encodeURIComponent(id)}${snapshot ? `?revision_id=${encodeURIComponent(snapshot)}` : ''}`,
    ),
  source: (id: string) => request<Source>(`sources/${encodeURIComponent(id)}`),
  versions: (id: string) =>
    request<{ versions: Version[] }>(
      `sources/${encodeURIComponent(id)}/versions?limit=100`,
    ),
  citation: (id: string) =>
    request<Citation>(`chunks/${encodeURIComponent(id)}/citation`),
  search: (query: string, kind: string, options: Record<string, string> = {}) =>
    request<{
      hits: SearchHit[]
      retrieval_method: string
      fallback_reasons: string[]
      candidate_count: number
      scored_count: number
      graphs: {
        root: string
        nodes: { id: string; label: string }[]
        truncated: boolean
      }[]
    }>(
      `knowledge/search?${new URLSearchParams({ query, kind, mode: 'text', limit: '50', ...options })}`,
    ),
}
