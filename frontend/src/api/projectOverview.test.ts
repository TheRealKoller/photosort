import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { getOverviewSeen, markOverviewSeen } from './projectOverview'

vi.mock('./client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./client')>()),
  apiFetch: vi.fn(),
}))

afterEach(() => {
  vi.mocked(apiFetch).mockReset()
})

describe('api/projectOverview', () => {
  it('liest den Merker der angemeldeten Person', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ seen: true })

    await expect(getOverviewSeen(5)).resolves.toEqual({ seen: true })
    expect(apiFetch).toHaveBeenCalledWith('/projects/5/overview-seen')
  })

  it('merkt "gesehen" per PUT ohne Körper - die Person kommt allein aus dem Token', async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined)

    await markOverviewSeen(5)

    expect(apiFetch).toHaveBeenCalledWith('/projects/5/overview-seen', { method: 'PUT' })
  })
})
