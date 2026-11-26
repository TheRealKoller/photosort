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

const BASE = '/projects/{project_id}/classification-reviews'

describe('api/classificationReviews - Lesepfad', () => {
  it('liest die Liste der Pruefungen eines Projekts', async () => {
    vi.mocked(apiFetch).mockResolvedValue([])

    await expect(listClassificationReviews(7)).resolves.toEqual([])

    expect(apiFetch).toHaveBeenCalledWith(BASE, { pathParams: { project_id: 7 } })
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

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/options`, { pathParams: { project_id: 7 } })
  })

  it('liest eine Pruefung samt Zaehlungen', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ id: 3 })

    await getClassificationReview(7, 3)

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/{review_id}`, {
      pathParams: { project_id: 7, review_id: 3 },
    })
  })

  it('liest die vorgelegten Faelle einer Pruefung', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ cases: [] })

    await expect(listClassificationReviewCases(7, 3)).resolves.toEqual({ cases: [] })

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/{review_id}/cases`, {
      pathParams: { project_id: 7, review_id: 3 },
    })
  })
})

describe('api/classificationReviews - Kostenvorschau', () => {
  it('fragt beide Seiten ueber ihre Art und das Modell ab - ohne Betrag im Aufruf', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ photo_count: 0, a: {}, b: {} })

    await getClassificationReviewEstimate(7, {
      a: { kind: 'cloud', model: 'gpt-4o-mini' },
      b: { kind: 'eye' },
    })

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/estimate`, {
      pathParams: { project_id: 7 },
      query: { a_kind: 'cloud', a_model: 'gpt-4o-mini', b_kind: 'eye' },
    })
  })

  // Ein Modell an einer Eye-Seite ist wirkungslos und wird deshalb gar nicht erst gesendet.
  it('sendet kein Modell fuer eine Seite ohne Modell', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ photo_count: 0, a: {}, b: {} })

    await getClassificationReviewEstimate(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', model: 'modell-der-falschen-seite' },
    })

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/estimate`, {
      pathParams: { project_id: 7 },
      query: { a_kind: 'local', b_kind: 'eye' },
    })
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
      pathParams: { project_id: 7 },
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

    // GLEICHHEIT der Schluesselmenge: `toHaveBeenCalledWith` vergleicht den Body vollstaendig -
    // ein zusaetzliches Feld machte den Aufruf ungleich.
    expect(apiFetch).toHaveBeenCalledWith(BASE, {
      method: 'POST',
      pathParams: { project_id: 7 },
      body: {
        a: { kind: 'local' },
        b: { kind: 'eye', eye_mapping_version: 'eye-4.2.3/v1' },
        sample_size: 12,
      },
    })
  })

  it('schreibt ein Urteil als einziges Feld des Koerpers', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ case_id: 11, verdict: 'both_ok' })

    await setClassificationReviewVerdict(7, 3, 11, 'both_ok')

    expect(apiFetch).toHaveBeenCalledWith(`${BASE}/{review_id}/cases/{case_id}/verdict`, {
      method: 'PUT',
      pathParams: { project_id: 7, review_id: 3, case_id: 11 },
      body: { verdict: 'both_ok' },
    })
  })
})

describe('api/classificationReviews - Export', () => {
  it('laedt die Datei ueber den authentifizierten Blob-Weg', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    vi.mocked(apiFetchBlob).mockResolvedValue(blob)

    await expect(exportClassificationReview(7, 3)).resolves.toBe(blob)

    expect(apiFetchBlob).toHaveBeenCalledWith(`${BASE}/{review_id}/export`, {
      pathParams: { project_id: 7, review_id: 3 },
    })
  })
})
