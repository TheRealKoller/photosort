import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import {
  createProject,
  getProject,
  listProjects,
  triggerScan,
  triggerScore,
  triggerSelectTop,
} from './projects'
import type { ProjectOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const PROJECT: ProjectOut = {
  id: 1,
  name: 'Costa Rica',
  opencloud_drive_id: 'drive-1',
  opencloud_path: 'CostaRica',
  created_at: '2026-07-20T10:00:00Z',
  last_scan: null,
  last_scoring_run: null,
  last_top_selection_run: null,
}

describe('api/projects', () => {
  it('fetches the project list from GET /projects', async () => {
    vi.mocked(apiFetch).mockResolvedValue([PROJECT])

    const result = await listProjects()

    expect(apiFetch).toHaveBeenCalledWith('/projects')
    expect(result).toEqual([PROJECT])
  })

  it('posts name/opencloud_path to POST /projects and returns the created project', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PROJECT)

    const result = await createProject({ name: 'Costa Rica', opencloud_path: 'CostaRica' })

    expect(apiFetch).toHaveBeenCalledWith('/projects', {
      method: 'POST',
      body: { name: 'Costa Rica', opencloud_path: 'CostaRica' },
    })
    expect(result).toEqual(PROJECT)
  })

  it('fetches a single project from GET /projects/{id}', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PROJECT)

    const result = await getProject(1)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1')
    expect(result).toEqual(PROJECT)
  })

  it('triggers a scan via POST /projects/{id}/scan', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ status: 'queued' })

    const result = await triggerScan(1)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/scan', { method: 'POST' })
    expect(result).toEqual({ status: 'queued' })
  })

  it('triggers scoring via POST /projects/{id}/score', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ status: 'queued' })

    const result = await triggerScore(1)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/score', { method: 'POST' })
    expect(result).toEqual({ status: 'queued' })
  })

  it('triggers the top-photo selection via POST /projects/{id}/select-top with top_n_per_cluster', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ status: 'queued' })

    const result = await triggerSelectTop(1, 5)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/select-top', {
      method: 'POST',
      body: { top_n_per_cluster: 5 },
    })
    expect(result).toEqual({ status: 'queued' })
  })
})
