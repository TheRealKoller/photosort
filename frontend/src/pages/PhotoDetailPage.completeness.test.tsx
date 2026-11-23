/*
 * Foto-Detailseite - Teil: Maximal-Fixture (AK4) und Ort (S2) (Spec 0651; gemeinsamer Unterbau in src/test/photoDetailPage.tsx).
 */
import { screen } from '@testing-library/react'
import * as photosApi from '../api/photos'
import type { PhotoOut } from '../api/types'
import { MOTIF_KEYS, MOTIF_SET } from '../test/motifSetFixture'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  photo,
  criterionScore,
  motifStrengths,
  cloudVisionStatusEntry,
  renderPage,
  motifSection,
  CLOUD_ASSESSMENT,
  resetPersonsMock,
  resetPhotoDetailMocks,
} from '../test/photoDetailPage'

vi.mock('../api/motifs')
vi.mock('../api/persons')
vi.mock('../api/photos')
vi.mock('../api/ratings')

// Der Personenabschnitt und der Personenfilter laden `GET /persons` in JEDEM Block
// dieser Datei. Die Vorgabe "keine Person festgelegt" gilt dateiweit; ein Block, der Personen
// braucht, setzt sie selbst.
beforeEach(() => {
  resetPersonsMock()
  resetPhotoDetailMocks()
})

/* specs/features/0497-bilddetail-urteil-zuerst.md — AK4 (keine Angabe geht verloren), der Ort als
   Neuzugang auf dieser Route (S2) und die mit der Renderstelle mitgewanderten XSS-Nachweise (S5).

   VOLLABDECKUNG STATT STICHPROBE: Bei einem Umbau, dessen einziger ernster Fehlermodus der STILLE
   VERLUST einer Angabe ist, wäre eine Stichprobe die teurere Wahl. Die Sollmenge steht deshalb
   literal als Sondenliste und wird als MENGE verglichen - nicht als Reihenfolge, die AK8 prüft. */
describe('PhotoDetailPage: die Maximal-Fixture (AK4)', () => {
  const ACHT_QUALITAETSWERTE = [
    'Schärfe',
    'Belichtung',
    'Kontrast',
    'Farbigkeit',
    'Rauschen',
    'Bildaufbau',
    'Augen offen',
    'Gesichtsschärfe',
  ]

  const SIEBEN_BILDINHALT_WERTE = [
    'Menschen erkannt',
    'Tier erkannt',
    'Gebäude erkannt',
    'Landschaft erkannt',
    'Essen erkannt',
    'Fahrzeug erkannt',
    'Text erkannt',
  ]

  function maximalPhoto(overrides: Partial<PhotoOut> = {}): PhotoOut {
    return photo({
      id: 1,
      taken_at: '2026-07-20T12:30:00',
      taken_at_original: '2026-07-20T10:00:00',
      time_offset_minutes: 150,
      camera: { id: 3, label: 'Canon EOS R6' },
      criterion_scores: [
        ...ACHT_QUALITAETSWERTE.map((name, i) =>
          criterionScore({
            criterion_key: `quality_${i}`,
            display_name: name,
            value: (i + 1) / 20,
          }),
        ),
        ...SIEBEN_BILDINHALT_WERTE.map((name, i) =>
          criterionScore({
            criterion_key: `content_${i}`,
            display_name: name,
            value: (i + 1) / 20,
            has_presence_threshold: true,
          }),
        ),
      ],
      ranking: {
        event_id: 1,
        rank_score: 0.8,
        rank_position: 2,
        proposed: true,
        partition_size: 5,
        curation_position: null,
      },
      fine_labels: [
        {
          canonical_key: 'urlaub',
          display_name: 'Urlaub',
          raw_label: 'urlaub',
          provider: 'anthropic',
        },
        {
          canonical_key: 'strand',
          display_name: 'Strand',
          raw_label: 'strand',
          provider: 'anthropic',
        },
      ],
      album_suitability: { level: 4, reason: 'Alle schauen in die Kamera.', source: 'cloud' },
      cloud_vision_status: [
        cloudVisionStatusEntry({ phase: 'landmark', status: 'result' }),
        cloudVisionStatusEntry({ phase: 'remote_category', status: 'result' }),
      ],
      motif_assessment: CLOUD_ASSESSMENT,
      motifs: motifStrengths(),
      event: {
        id: 9,
        position: 3,
        started_at: '2026-07-20T10:30:00',
        ended_at: '2026-07-20T11:45:00',
        place: { kind: 'landmark', landmark_name: 'Eiffelturm', lat: null, lon: null },
        place_name: 'Paris, 7. Arrondissement',
      },
      ...overrides,
    })
  }

  /** Was OHNE jede Bedienhandlung im Dokument steht. Als MENGE verglichen. */
  function sichtbareAngaben(): string[] {
    const gefunden: string[] = []
    const text = document.body.textContent ?? ''
    // Die Motivstaerken stehen im zugaenglichen NAMEN der Symbole - eine Zusage, die nur
    // `textContent` liest, erfasst sie nicht.
    const namen = [...document.querySelectorAll('[data-motif-key]')].map(
      (node) => node.getAttribute('aria-label') ?? '',
    )
    const haystack = [text, ...namen].join(' ')

    const sonden: Record<string, string> = {
      Albumtauglichkeitsstufe: 'Stufe 4 von 5',
      'Begründung des Modells': 'Alle schauen in die Kamera.',
      'Rang im Ereignis': '2 von 5',
      'Feinlabel Urlaub': 'Urlaub',
      'Feinlabel Strand': 'Strand',
      ...Object.fromEntries(ACHT_QUALITAETSWERTE.map((name) => [`Qualitätswert ${name}`, name])),
      ...Object.fromEntries(
        SIEBEN_BILDINHALT_WERTE.map((name) => [`Bildinhalt-Wert ${name}`, name]),
      ),
      Grundlagenzeile: 'Grundlage: Cloud-Klassifizierung',
      ...Object.fromEntries(
        MOTIF_SET.items.map((item) => [`Motivstärke ${item.key}`, `${item.display_name}:`]),
      ),
      'wirksame Aufnahmezeit': '20.07.2026, 12:30',
      Originalzeit: '20.07.2026, 10:00',
      Korrekturmarke: 'korrigiert',
      Kamera: 'Canon EOS R6',
      Ort: 'Eiffelturm',
      'Cloud-Phase Landmark': 'Landmark-Erkennung',
      'Cloud-Phase Remote-Kategorie': 'Remote-Kategorie',
    }

    for (const [name, nadel] of Object.entries(sonden)) {
      if (haystack.includes(nadel)) {
        gefunden.push(name)
      }
    }
    return gefunden.sort()
  }

  function sollmenge(): string[] {
    return [
      'Albumtauglichkeitsstufe',
      'Begründung des Modells',
      'Rang im Ereignis',
      'Feinlabel Urlaub',
      'Feinlabel Strand',
      ...ACHT_QUALITAETSWERTE.map((name) => `Qualitätswert ${name}`),
      ...SIEBEN_BILDINHALT_WERTE.map((name) => `Bildinhalt-Wert ${name}`),
      'Grundlagenzeile',
      ...MOTIF_SET.items.map((item) => `Motivstärke ${item.key}`),
      'wirksame Aufnahmezeit',
      'Originalzeit',
      'Korrekturmarke',
      'Kamera',
      'Ort',
      'Cloud-Phase Landmark',
      'Cloud-Phase Remote-Kategorie',
    ].sort()
  }

  it('zeigt jede Angabe ohne eine einzige Bedienhandlung', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [maximalPhoto()], total: 1 })

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')
    await screen.findByRole('list', { name: 'Motive' })

    expect(sichtbareAngaben()).toEqual(sollmenge())
  })

  /* Hinter GENAU EINER Aufklapphandlung stehen NUR das Motiv-Glossar, die Detailzeile eines
     Motivs samt Korrekturschaltern und die Gesichterwahl des Personenabschnitts.
     Alles andere steht offen da. */
  it('hält nur Glossar, Motiv-Detailzeile und Gesichterwahl hinter einer Aufklapphandlung', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [maximalPhoto()], total: 1 })

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')
    await screen.findByRole('list', { name: 'Motive' })

    // Das einzige <details> der Seite ist das Motiv-Glossar, und es steht in der Motivsektion.
    const alleDetails = [...document.querySelectorAll('details')]
    expect(alleDetails).toHaveLength(1)
    expect(motifSection().contains(alleDetails[0])).toBe(true)

    // Die einzigen aufklappbaren Bedienelemente sind die acht Motivsymbole und "Gesicht zeigen".
    const gesichtZeigen = await screen.findByRole('button', { name: 'Gesicht zeigen' })
    const aufklappbar = [...document.querySelectorAll('[aria-expanded]')]
    expect(aufklappbar).toHaveLength(MOTIF_KEYS.length + 1)
    for (const node of aufklappbar.filter((node) => node !== gesichtZeigen)) {
      expect(node.getAttribute('data-motif-key')).not.toBeNull()
    }

    /* Weder das Urteil selbst noch das Einzelwerte-Raster tragen einen Auslöser. Geprüft wird das
       URTEIL (`photo-verdict`), nicht die ganze Urteilsfläche: In der steht der Motivbereich mit
       seinem Glossar, und das ist der eine erlaubte Fall. */
    for (const testId of ['photo-verdict', 'criterion-score-grid']) {
      const bereich = screen.getByTestId(testId)
      expect(bereich.querySelector('details')).toBeNull()
      expect(bereich.querySelector('[aria-haspopup]')).toBeNull()
    }
  })
})

describe('PhotoDetailPage: der Ort (S2)', () => {
  function photoMitOrt(place: PhotoOut['event']): PhotoOut {
    return photo({ id: 1, event: place })
  }

  it('zeigt den Namen der Sehenswürdigkeit ohne Zeitspanne', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photoMitOrt({
          id: 9,
          position: 3,
          started_at: '2026-07-20T10:30:00',
          ended_at: '2026-07-20T11:45:00',
          place: { kind: 'landmark', landmark_name: 'Eiffelturm', lat: null, lon: null },
          place_name: 'Paris, 7. Arrondissement',
        }),
      ],
      total: 1,
    })

    renderPage('/projects/1/photos/1')

    const zeile = await screen.findByTestId('place-line')
    // OHNE Zeitspanne: die Aufnahmezeit steht direkt darüber, eine zweite Zeitangabe daneben wäre
    // eine Wiederholung.
    expect(zeile).toHaveTextContent('Eiffelturm')
    expect(zeile.textContent).not.toMatch(/Uhr/)
    expect(zeile.textContent).not.toMatch(/10:30/)
  })

  it('fällt auf den aufgelösten Ortsnamen zurück', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photoMitOrt({
          id: 9,
          position: 3,
          started_at: '2026-07-20T10:30:00',
          ended_at: '2026-07-20T11:45:00',
          place: null,
          place_name: 'Berlin, Kreuzberg',
        }),
      ],
      total: 1,
    })

    renderPage('/projects/1/photos/1')

    expect(await screen.findByTestId('place-line')).toHaveTextContent('Berlin, Kreuzberg')
  })

  it('zeigt ohne Ortsangabe den Satz statt einer Lücke', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })

    renderPage('/projects/1/photos/1')

    expect(await screen.findByTestId('place-line')).toHaveTextContent('nicht bestimmbar')
  })

  /* Eine Koordinate erscheint AUSDRÜCKLICH NICHT als Name - sie bleibt in `place`. */
  it('zeigt eine Koordinate nicht als Namen', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photoMitOrt({
          id: 9,
          position: 3,
          started_at: '2026-07-20T10:30:00',
          ended_at: '2026-07-20T11:45:00',
          place: { kind: 'coordinate', landmark_name: null, lat: 48.86, lon: 2.29 },
          place_name: null,
        }),
      ],
      total: 1,
    })

    renderPage('/projects/1/photos/1')

    const zeile = await screen.findByTestId('place-line')
    expect(zeile).toHaveTextContent('nicht bestimmbar')
    expect(zeile.textContent).not.toMatch(/48\.86|2\.29/)
  })

  /* S5 — DER NACHWEIS GEHÖRT AN DIE RENDERSTELLE, nicht in den Test der Funktion: Dass
     `eventPlaceName` nichts interpretiert, sagt nichts darüber, was das Markup daraus macht.
     Beide Felder tragen S1, und der Ort ist auf dieser Route ERSTKONTAKT - der bestehende Nachweis
     in `AlbumDraftPage.*.test.tsx` trägt hier nicht. */
  it.each([
    {
      name: 'landmark_name',
      place: {
        kind: 'landmark' as const,
        landmark_name: '<img src=x onerror="window.__pwned = true">',
        lat: null,
        lon: null,
      },
      placeName: null,
    },
    {
      name: 'place_name',
      place: null,
      placeName: '<img src=x onerror="window.__pwned = true">',
    },
  ])(
    'rendert einen feindlich belegten Ortsnamen aus $name als reinen Textknoten',
    async ({ place, placeName }) => {
      const payload = '<img src=x onerror="window.__pwned = true">'
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photoMitOrt({
            id: 9,
            position: 3,
            started_at: '2026-07-20T10:30:00',
            ended_at: '2026-07-20T11:45:00',
            place,
            place_name: placeName,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      const zeile = await screen.findByTestId('place-line')
      expect(zeile).toHaveTextContent(payload)
      expect(document.querySelector('img[src="x"]')).toBeNull()
      expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
      delete (window as unknown as Record<string, unknown>).__pwned
    },
  )
})
