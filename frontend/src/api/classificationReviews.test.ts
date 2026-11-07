import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, apiFetchBlob } from './client'
import {
  createClassificationReview,
  exportClassificationReview,
  getClassificationReview,
  getClassificationReviewEstimate,
  getClassificationReviewOptions,
  listClassificationReviewCases,
  listClassificationReviews,
  setClassificationReviewVerdict,
} from './classificationReviews'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  apiFetchBlob: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

/*
 * Der Client spiegelt die Backend-Routen der Pruefung (Spec 0616): Basis ist der ENGLISCHE
 * Kebab-Pfad, waehrend die Oberflaeche den deutschen Pfad traegt. Kein Koerper traegt einen
 * Betrag, einen Anbieter oder eine Id-Liste - die kommen serverseitig.
 */

const BASE = '/projects/7/classification-reviews'

describe('api/classificationReviews - Lesepfad', () => {
  it('liest die Liste der Pruefungen eines Projekts', async () => {
    vi.mocked(apiFetch).mockResolvedValue([])

    await expect(listClassificationReviews(7)).resolves.toEqual([])

    expect(apiFetch).toHaveBeenCalledWith(BASE)
  })

  it('liest die waehlbaren Verfahren samt Sperrgruenden', async () => {
    const options = {
      sample_size: { default: 30, min: 1, max: 200 },
      kinds: [],
      cloud_models: [],
      eye_mappings: [],
    }
    vi.mocked(apiFetch).mockResolvedValue(options)

    await expect(getClassificationReviewOptions(7)).resolves.toEqual(options)

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/options`)
  })

  it('liest eine Pruefung samt Zaehlungen', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ id: 3 })

    await getClassificationReview(7, 3)

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/3`)
  })

  it('liest die vorgelegten Faelle einer Pruefung', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ cases: [] })

    await expect(listClassificationReviewCases(7, 3)).resolves.toEqual({ cases: [] })

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/3/cases`)
  })
})

describe('api/classificationReviews - Kostenvorschau', () => {
  it('fragt beide Seiten ueber ihre Art und das Modell ab - ohne Betrag im Aufruf', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ photo_count: 0, a: {}, b: {} })

    await getClassificationReviewEstimate(7, {
      a: { kind: 'cloud', model: 'gpt-4o-mini' },
      b: { kind: 'eye' },
    })

    const path = vi.mocked(apiFetch).mock.calls[0]![0]
    const query = new URLSearchParams(path.split('?')[1])
    expect(path.startsWith(`${BASE}/estimate?`)).toBe(true)
    expect(Object.fromEntries(query)).toEqual({
      a_kind: 'cloud',
      a_model: 'gpt-4o-mini',
      b_kind: 'eye',
    })
  })

  // Ein Modell an einer Eye-Seite ist wirkungslos und wird deshalb gar nicht erst gesendet.
  it('sendet kein Modell fuer eine Seite ohne Modell', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ photo_count: 0, a: {}, b: {} })

    await getClassificationReviewEstimate(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', model: 'modell-der-falschen-seite' },
    })

    const query = new URLSearchParams(vi.mocked(apiFetch).mock.calls[0]![0].split('?')[1])
    expect(query.get('a_model')).toBeNull()
    expect(query.get('b_model')).toBeNull()
    expect(query.get('b_kind')).toBe('eye')
  })
})

describe('api/classificationReviews - Anlegen und Urteil', () => {
  it('legt eine Pruefung mit beiden Seiten und der Pruefgraesse an', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ id: 3, status: 'running' })

    await expect(
      createClassificationReview(7, {
        a: { kind: 'cloud', model: 'gpt-4o-mini' },
        b: { kind: 'eye', eye_mapping_version: 'eye-4.2.3/v1' },
        sample_size: 30,
      }),
    ).resolves.toEqual({ id: 3, status: 'running' })

    expect(apiFetch).toHaveBeenCalledWith(BASE, {
      method: 'POST',
      body: {
        a: { kind: 'cloud', model: 'gpt-4o-mini' },
        b: { kind: 'eye', eye_mapping_version: 'eye-4.2.3/v1' },
        sample_size: 30,
      },
    })
  })

  // Der Koerper traegt KEINEN Betrag und keinen Anbieter: beides entsteht serverseitig (S8).
  it('sendet weder Kosten noch Anbieter im Anlegen-Koerper', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ id: 3, status: 'running' })

    await createClassificationReview(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', eye_mapping_version: 'eye-4.2.3/v1' },
      sample_size: 12,
    })

    const body = vi.mocked(apiFetch).mock.calls[0]![1]!.body as Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual(['a', 'b', 'sample_size'])
    expect(body.a).toEqual({ kind: 'local' })
  })

  it('schreibt ein Urteil als einziges Feld des Koerpers', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ case_id: 11, verdict: 'both_ok' })

    await setClassificationReviewVerdict(7, 3, 11, 'both_ok')

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/3/cases/11/verdict`, {
      method: 'PUT',
      body: { verdict: 'both_ok' },
    })
  })
})

describe('api/classificationReviews - Export', () => {
  it('laedt die Datei ueber den authentifizierten Blob-Weg', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    vi.mocked(apiFetchBlob).mockResolvedValue(blob)

    await expect(exportClassificationReview(7, 3)).resolves.toBe(blob)

    expect(apiFetchBlob).toHaveBeenCalledWith(`${BASE}/3/export`)
  })
})
