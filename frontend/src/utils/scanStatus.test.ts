import { describe, expect, it } from 'vitest'

import { deriveScanStatus } from './scanStatus'
import type { ProjectOut } from '../api/types'

function projectWith(lastScan: ProjectOut['last_scan']): Pick<ProjectOut, 'last_scan'> {
  return { last_scan: lastScan }
}

describe('deriveScanStatus', () => {
  it('returns "never" when the project has never been scanned', () => {
    expect(deriveScanStatus(projectWith(null))).toBe('never')
  })

  it.each(['running', 'success', 'failed'] as const)(
    'returns "%s" when the last scan has that status',
    (status) => {
      const project = projectWith({
        status,
        started_at: '2026-07-20T10:00:00Z',
        finished_at: null,
        files_found: 0,
        total_files: null,
        photos_added: 0,
        photos_updated: 0,
        photos_removed: 0,
        files_skipped: 0,
        error_message: null,
      })

      expect(deriveScanStatus(project)).toBe(status)
    }
  )
})
