import * as v from 'valibot'
import { ApiError } from './client'

const schema = v.object({
  name: v.pipe(v.string(), v.trim(), v.minLength(1), v.maxLength(128)),
  lifetime_days: v.nullable(
    v.pipe(v.number(), v.integer(), v.minValue(1), v.maxValue(365)),
  ),
  space_ids: v.pipe(
    v.array(v.pipe(v.string(), v.uuid())),
    v.minLength(1),
    v.maxLength(100),
  ),
})
export function keyRequest(
  form: {
    name: string
    days: string
    write: boolean
    selected: Record<string, boolean>
  },
  spaces: { id: string; role: string }[],
) {
  const result = v.safeParse(schema, {
    name: form.name,
    lifetime_days: form.days.trim() ? Number(form.days) : null,
    space_ids: Object.keys(form.selected).filter((id) => form.selected[id]),
  })
  if (!result.success) throw new ApiError(422)
  if (
    result.output.space_ids.some(
      (id) =>
        !spaces.some(
          (space) =>
            space.id === id &&
            (!form.write || ['editor', 'admin'].includes(space.role)),
        ),
    )
  )
    throw new ApiError(422, 'key_permissions')
  return {
    ...result.output,
    scopes: form.write ? ['c0:read', 'c0:write'] : ['c0:read'],
  }
}
