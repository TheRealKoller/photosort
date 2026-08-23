import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import {
  confirmAusschussGate,
  createProject,
  getProject,
  listProjects,
  setCloudVisionConsent,
  triggerScan,
  triggerScore,
  triggerScoreCriteria,
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
  last_criterion_scoring_run: null,
  last_remote_category_classification_run: null,
  category_selection_enabled: true,
  cloud_vision_detection_enabled: false,
  cloud_vision_consent_at: null,
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

  it('confirms the ausschuss gate via POST /projects/{id}/confirm-ausschuss-gate', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ status: 'confirmed' })

    const result = await confirmAusschussGate(1)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/confirm-ausschuss-gate', {
      method: 'POST',
    })
    expect(result).toEqual({ status: 'confirmed' })
  })

  it('triggers criterion scoring via POST /projects/{id}/score-criteria with scoring_run_id', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ status: 'queued' })

    const result = await triggerScoreCriteria(1, 5)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/score-criteria', {
      method: 'POST',
      body: { scoring_run_id: 5 },
    })
    expect(result).toEqual({ status: 'queued' })
  })

  it('sets the cloud landmark consent via PUT /projects/{id}/cloud-vision-consent', async () => {
    const response = {
      cloud_vision_detection_enabled: true,
      cloud_vision_consent_at: '2026-08-21T10:00:00Z',
    }
    vi.mocked(apiFetch).mockResolvedValue(response)

    const result = await setCloudVisionConsent(1, true)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/cloud-vision-consent', {
      method: 'PUT',
      body: { enabled: true },
    })
    expect(result).toEqual(response)
  })
})
