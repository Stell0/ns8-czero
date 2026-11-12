export interface FieldSchema {
  type: string
  title?: string
  properties?: Record<string, FieldSchema>
  items?: FieldSchema
  enum?: unknown[]
}
export interface RecordType {
  name: string
  label: string
  schema: FieldSchema
}
export interface TableRecord {
  id: string
  type_name: string
  revision: number
  created_at: string
  updated_at: string
  tags: string[]
  data: Record<string, unknown>
}
export function fieldLabel(name: string, schema?: FieldSchema) {
  if (schema?.title) return schema.title
  const label = name.replaceAll('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}
export function scalar(schema: FieldSchema) {
  return ['string', 'integer', 'number', 'boolean'].includes(schema.type)
}
export function preview(value: unknown): string {
  if (typeof value === 'string')
    return value.length > 120 ? value.slice(0, 120) + '…' : value
  return String(value)
}
