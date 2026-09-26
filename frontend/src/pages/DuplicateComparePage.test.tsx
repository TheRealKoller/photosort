import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as duplicatesApi from '../api/duplicates'
import type { DuplicateDecision, DuplicateGroupOut, PhotoOut } from '../api/types'
import {
  DUPLICATE_CONSEQUENCE_TEXT,
  DUPLICATE_EMPTY_TEXT,
  DUPLICATE_HINT_TEXT,
  DuplicateComparePage,
} from './DuplicateComparePage'

vi.mock('../api/duplicates')
vi.mock('../components/PhotoImage', () => ({
  PhotoImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}))

function photo(id: number): PhotoOut {
  return {
    id,
    relative_path: `Reise/serie-${id}.jpg`,
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
  }
}

function group(
  ids: number[],
  overrides: {
    position?: number
    total?: number
    decisions?: DuplicateDecision[]
    keepPossible?: boolean[]
    sharpness?: (number | null)[]
    previousPhotoId?: number | null
    nextPhotoId?: number | null
    spanSeconds?: number
  } = {},
): DuplicateGroupOut {
  return {
    items: ids.map((id, index) => ({
      photo: photo(id),
      effective_decision: overrides.decisions?.[index] ?? 'keep',
      keep_possible: overrides.keepPossible?.[index] ?? true,
      sharpness: overrides.sharpness?.[index] ?? null,
      exposure: null,
    })),
    position: overrides.position ?? 1,
    total: overrides.total ?? 1,
    previous_photo_id: overrides.previousPhotoId ?? null,
    next_photo_id: overrides.nextPhotoId ?? null,
    span_seconds: overrides.spanSeconds ?? 0,
  }
}

/** Die tatsächlich besuchte Adresse — die Seite bleibt beim Gruppenwechsel montiert, nur der
 * Parameter ändert sich, und genau das muss prüfbar sein. */
function Pfadspiegel() {
  const ort = useLocation()
  return <span data-testid="pfad">{`${ort.pathname}${ort.search}`}</span>
}

function renderPage(url = '/projects/1/photos/10/duplicates') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={[url]}>
      <Pfadspiegel />
      <Routes>
        <Route
          path="/projects/:projectId/photos/:photoId/duplicates"
          element={<DuplicateComparePage />}
        />
        <Route path="/projects/:projectId/pipeline/:step" element={<p>Ausschuss-Schritt</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

function pfad(): string {
  return screen.getByTestId('pfad').textContent ?? ''
}

/** Die Karten des Rasters - der Streifen der Grossansicht zaehlt nicht mit. */
function tiles(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('li[data-duplicate-decision]'))
}

function confirmButton(): HTMLElement {
  return screen.getByRole('button', { name: /^Gruppe abschließen|^Wird abgeschlossen/ })
}

beforeEach(() => {
  vi.mocked(duplicatesApi.getDuplicateGroup).mockReset()
  vi.mocked(duplicatesApi.setDuplicateDecision).mockReset()
  vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockReset()
  vi.mocked(duplicatesApi.confirmDuplicateGroup).mockReset()
})

/* ------------------------------------------------------------------------------------------
 * Die Gruppe, Zustaende und Bewertung (A4, A5, A7)
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Gruppe', () => {
  it('rendert jedes Mitglied in der gelieferten Reihenfolge', async () => {
    // DIE REIHENFOLGE KOMMT VOM SERVER. Die Seite sortiert nicht nach.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12, 13]))
    renderPage()

    await waitFor(() => expect(tiles()).toHaveLength(3))
    expect(tiles().map((kachel) => within(kachel).getByRole('img').getAttribute('alt'))).toEqual([
      'Reise/serie-11.jpg',
      'Reise/serie-12.jpg',
      'Reise/serie-13.jpg',
    ])
  })

  it('zeichnet kein Mitglied als Gewinner, Original oder Vorgeschlagenen aus', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12, 13]))
    renderPage()

    await waitFor(() => expect(tiles()).toHaveLength(3))
    const bauformen = tiles().map((kachel) =>
      within(kachel)
        .getAllByRole('button')
        .map((knopf) => (knopf.getAttribute('aria-label') ?? '').replace(/serie-\d+\.jpg/, 'X'))
        .join('|'),
    )

    expect(new Set(bauformen).size).toBe(1)
  })

  it('kennt je Aufnahme nur Behalten oder Ausschuss, mit genau einer gedrueckten Wahl', async () => {
    // A5: kein dritter Zustand, weder als Wert noch als Wort.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12, 13], { decisions: ['keep', 'discard', 'discard'] }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))

    for (const kachel of tiles()) {
      expect(['keep', 'discard']).toContain(kachel.dataset.duplicateDecision)
      const wahl = within(kachel).getByRole('group')
      expect(within(wahl).getAllByRole('button', { pressed: true })).toHaveLength(1)
    }
    expect(screen.queryByText(/noch offen/i)).toBeNull()
  })

  it('liest die Messwerte aus der Gruppenantwort, nie aus PhotoOut.suggestion', async () => {
    const antwort = group([11, 12], { sharpness: [412.7, 88] })
    const erste = antwort.items[0]
    if (erste === undefined) {
      throw new Error('Fixture ohne Mitglied')
    }
    erste.photo.suggestion = {
      status: 'rejected',
      reason: 'duplicate',
      duplicate_of: 12,
      sharpness: 7,
      exposure: 0.9,
      cluster_key: null,
      computed_at: '2026-07-20T10:00:00',
    }
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(antwort)
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    const [kachel] = tiles()
    expect(kachel).toBeDefined()
    const wert = within(kachel as HTMLElement).getByText('Schärfe', {
      selector: 'dt',
    }).nextElementSibling
    expect(wert).toHaveTextContent('413 — schärfste')
    expect(within(kachel as HTMLElement).queryByText(/^7$/)).toBeNull()
  })

  it('bildet die Auszeichnung ueber den ANGEZEIGTEN Werten der ganzen Gruppe', async () => {
    // Rohwerte verschieden, angezeigt beide "413" - beide tragen die Auszeichnung.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12, 13], { sharpness: [412.7, 413.2, 100] }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))

    expect(
      tiles().map((kachel) => within(kachel).queryByText('— schärfste', { exact: false }) !== null),
    ).toEqual([true, true, false])
  })

  it('aendert mit der Auszeichnung weder Zustand, Wahl noch Bedienelemente', async () => {
    // Die schaerfste Aufnahme steht auf "Ausschuss", eine andere auf "Behalten" - widerspruchsfrei.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { decisions: ['keep', 'discard'], sharpness: [10, 500] }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    const ausgezeichnet = tiles()[1] as HTMLElement
    expect(within(ausgezeichnet).getByText('— schärfste', { exact: false })).toBeTruthy()
    expect(ausgezeichnet.dataset.duplicateDecision).toBe('discard')
    expect(
      within(ausgezeichnet).getByRole('button', { name: 'Ausschuss: Reise/serie-12.jpg' }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(tiles().map((kachel) => within(kachel).getAllByRole('button').length)).toEqual([3, 3])
  })
})

/* ------------------------------------------------------------------------------------------
 * A1/A2 - der Kopf
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - der Kopf', () => {
  it('nennt Stelle, Gesamtzahl, Mitgliederzahl und Serienspanne in der Ueberschrift', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12, 13], { position: 2, total: 5, spanSeconds: 9 }),
    )
    renderPage()

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Gruppe 2 von 5 · 3 Aufnahmen in 9 Sekunden',
      }),
    ).toBeTruthy()
  })

  it('zeigt daneben eine versteckte Fortschrittsanzeige mit denselben Zahlen', async () => {
    // A2: nie die einzige Quelle der Zahl - beide Zahlen stehen als Text im h1.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 5 }),
    )
    renderPage()
    await screen.findByRole('heading', { level: 1, name: /^Gruppe 2 von 5/ })

    const fortschritt = screen.getByRole('progressbar', { hidden: true })
    expect(fortschritt.getAttribute('value')).toBe('2')
    expect(fortschritt.getAttribute('max')).toBe('5')
    expect(fortschritt.getAttribute('aria-hidden')).toBe('true')
  })
})

/* ------------------------------------------------------------------------------------------
 * A3 - die beiden Hinweise, immer sichtbar
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Hinweise', () => {
  function pruefeHinweise() {
    const gruppe = screen.getByRole('group', { name: 'Ganze Gruppe' })
    for (const hinweis of [
      screen.getByText(DUPLICATE_HINT_TEXT),
      screen.getByTestId('duplicate-consequence'),
    ]) {
      expect(
        hinweis.compareDocumentPosition(gruppe) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy()
      expect(hinweis.closest('details, [role="alert"]')).toBeNull()
    }
  }

  it('stehen im Raster und in der Grossansicht vor den Gruppenaktionen, nie eingeklappt', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    pruefeHinweise()
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-11.jpg vergrößern' }))
    expect(screen.getByRole('heading', { level: 2, name: 'Aufnahme 1 von 2' })).toBeTruthy()
    pruefeHinweise()
  })

  it('bindet die Zusage an den ANGEZEIGTEN Zustand und sagt ueber nicht Angetipptes nichts zu', () => {
    // Waechter gegen eine falsche Zusage: "erhalten" haengt am angezeigten Zustand, nie an einem
    // "nicht angetippt" oder "unentschieden" - der unentschiedene Duplikat-Verlierer zeigt bereits
    // "Ausschuss" und scheidet ohne Zutun aus.
    expect(DUPLICATE_HINT_TEXT).toMatch(/angezeigt/i)
    expect(DUPLICATE_HINT_TEXT).toMatch(/sofort gespeichert/i)
    expect(DUPLICATE_HINT_TEXT).not.toMatch(
      /nicht (angetippt|markiert)|unentschieden|noch offen|noch nicht|offen/i,
    )
  })

  it('benennt an der Handlung, was "behalten" nach sich zieht - in beiden Modi', async () => {
    // SICHERHEIT (S12): Die Folge steht an der Handlung, im Raster wie in der Grossansicht.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage()

    const hinweis = await screen.findByTestId('duplicate-consequence')
    expect(hinweis.textContent).toBe(DUPLICATE_CONSEQUENCE_TEXT)
    expect(hinweis.textContent).toMatch(/Cloud/i)
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-11.jpg vergrößern' }))
    expect(screen.getByTestId('duplicate-consequence').textContent).toBe(DUPLICATE_CONSEQUENCE_TEXT)
  })
})

/* ------------------------------------------------------------------------------------------
 * A12 - die Gruppennavigation
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Gruppennavigation', () => {
  it('steht im Raster und in der Grossansicht', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()

    expect(await screen.findByRole('button', { name: 'Vorherige Gruppe' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Nächste Gruppe' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-12.jpg vergrößern' }))
    expect(screen.getByRole('button', { name: 'Vorherige Gruppe' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Nächste Gruppe' })).toBeTruthy()
  })

  it('traegt Namen, die sich nicht mit dem Blaettern INNERHALB der Gruppe ueberschneiden', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12, 13], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-12.jpg vergrößern' }))

    for (const name of [
      'Vorherige Gruppe',
      'Nächste Gruppe',
      'Vorherige Aufnahme',
      'Nächste Aufnahme',
    ]) {
      expect(screen.getAllByRole('button', { name })).toHaveLength(1)
    }
  })

  it('traegt als zugaenglichen Namen genau den sichtbaren Text (WCAG 2.5.3)', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()

    const navigation = await screen.findByRole('group', { name: 'Duplikat-Gruppen' })
    const knoepfe = within(navigation).getAllByRole('button')

    expect(knoepfe.map((knopf) => knopf.textContent)).toEqual([
      'Vorherige Gruppe',
      'Nächste Gruppe',
    ])
    for (const knopf of knoepfe) {
      expect(knopf.hasAttribute('aria-label')).toBe(false)
    }
  })

  it.each([
    ['am Anfang', { previousPhotoId: null, nextPhotoId: 20 }, true, false],
    ['am Ende', { previousPhotoId: 5, nextPhotoId: null }, false, true],
    ['in der Mitte', { previousPhotoId: 5, nextPhotoId: 20 }, false, false],
  ])(
    'ist %s genau dort disabled, wo der Nachbarwert null ist',
    async (_fall, nachbarn, zurueckGesperrt, vorGesperrt) => {
      vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12], nachbarn))
      renderPage()

      const zurueck = await screen.findByRole('button', { name: 'Vorherige Gruppe' })
      expect(zurueck).toHaveProperty('disabled', zurueckGesperrt)
      expect(screen.getByRole('button', { name: 'Nächste Gruppe' })).toHaveProperty(
        'disabled',
        vorGesperrt,
      )
    },
  )

  it('gibt den Fokus am Rand an die Gegenschaltflaeche ab', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      Promise.resolve(
        photoId === 10
          ? group([11, 12], { position: 1, total: 2, nextPhotoId: 20 })
          : group([21, 22], { position: 2, total: 2, previousPhotoId: 10 }),
      ),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Nächste Gruppe' })).toBeDisabled(),
    )
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Vorherige Gruppe' }))
  })

  it('bleibt WAEHREND DES LADENS der Nachbargruppe stehen', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      photoId === 10
        ? Promise.resolve(group([11, 12], { position: 1, total: 2, nextPhotoId: 20 }))
        : new Promise(() => {}),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))

    await waitFor(() => expect(pfad()).toContain('/photos/20/'))
    expect(screen.getByRole('button', { name: 'Nächste Gruppe' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Vorherige Gruppe' })).toBeTruthy()
  })

  it.each([
    ['ohne Rueckweg', '/projects/1/photos/10/duplicates', '/projects/1/photos/20/duplicates'],
    [
      'mit Rueckweg',
      '/projects/1/photos/10/duplicates?from=ausschuss',
      '/projects/1/photos/20/duplicates?from=ausschuss',
    ],
  ])('navigiert per Push auf den Anker der Nachbargruppe (%s)', async (_fall, start, ziel) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 1, total: 2, nextPhotoId: 20 }),
    )
    renderPage(start)
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))

    expect(pfad()).toBe(ziel)
  })

  it('laesst eine fertig entschiedene Gruppe erreichbar, statt sie zu ueberspringen', async () => {
    // A12: Die Gruppennavigation folgt allein den Nachbar-Ids des Servers.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      Promise.resolve(
        photoId === 10
          ? group([11, 12], { position: 1, total: 3, nextPhotoId: 20 })
          : group([21, 22], {
              position: 2,
              total: 3,
              previousPhotoId: 10,
              nextPhotoId: 30,
              decisions: ['discard', 'discard'],
            }),
      ),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))

    expect(pfad()).toBe('/projects/1/photos/20/duplicates')
    expect(await screen.findByRole('heading', { level: 1, name: /^Gruppe 2 von 3/ })).toBeTruthy()
  })
})

/* ------------------------------------------------------------------------------------------
 * Der Ankerwechsel hebt Vergroesserung, Entscheidungen und Meldung auf
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - der Ankerwechsel', () => {
  function zweiGruppen() {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      Promise.resolve(
        photoId === 10
          ? group([11, 12], { position: 1, total: 2, nextPhotoId: 20 })
          : group([21, 22], { position: 2, total: 2, previousPhotoId: 10 }),
      ),
    )
  }

  it('nimmt die Vergroesserung zurueck', async () => {
    zweiGruppen()
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-11.jpg vergrößern' }))
    expect(screen.getByRole('heading', { level: 2, name: /^Aufnahme / })).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))
    await waitFor(() => expect(screen.queryByRole('heading', { level: 2 })).toBeNull())
    await userEvent.click(screen.getByRole('button', { name: 'Vorherige Gruppe' }))

    await waitFor(() => expect(tiles()).toHaveLength(2))
    expect(screen.queryByRole('heading', { level: 2, name: /^Aufnahme / })).toBeNull()
  })

  it('nimmt die laufende Entscheidung zurueck', async () => {
    // Ueber einen HIN- UND RUECKWEG: Zwei Gruppen sind disjunkt, eine stehen gebliebene Id der
    // alten traefe in der neuen keine Kachel - erst bei der Rueckkehr sperrte sie dauerhaft.
    zweiGruppen()
    vi.mocked(duplicatesApi.setDuplicateDecision).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' })).toBeDisabled(),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Gruppe' }))
    await waitFor(() => expect(pfad()).toContain('/photos/20/'))
    await userEvent.click(screen.getByRole('button', { name: 'Vorherige Gruppe' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' })).toBeEnabled(),
    )
    expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' })).toBeEnabled()
  })
})

/* ------------------------------------------------------------------------------------------
 * A9 - Gruppenaktionen
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Abkuerzungen', () => {
  it('setzt alle Mitglieder in GENAU EINEM Aufruf', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12, 13, 14]))
    vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockResolvedValue(
      group([11, 12, 13, 14], { decisions: ['keep', 'keep', 'keep', 'keep'] }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(4))

    await userEvent.click(screen.getByRole('button', { name: 'Alle behalten' }))

    await waitFor(() => expect(duplicatesApi.setDuplicateGroupDecision).toHaveBeenCalledTimes(1))
    expect(duplicatesApi.setDuplicateGroupDecision).toHaveBeenCalledWith(1, 10, 'keep')
    expect(duplicatesApi.setDuplicateDecision).not.toHaveBeenCalled()
  })

  it('bietet beide Richtungen an', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockResolvedValue(group([11, 12]))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Alle in den Ausschuss' }))

    expect(duplicatesApi.setDuplicateGroupDecision).toHaveBeenCalledWith(1, 10, 'discard')
  })
})

/* ------------------------------------------------------------------------------------------
 * A5 - Einzelentscheidung
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Einzelentscheidung', () => {
  it('entscheidet ueber GENAU DAS Mitglied, dessen Schaltflaeche gedrueckt wurde', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12, 13]))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group([11, 12, 13]))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))

    await userEvent.click(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-12.jpg' }))

    expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalledWith(1, 12, 'discard')
  })

  it('sperrt waehrend einer laufenden Entscheidung nur die betroffene Kachel', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' })).toBeDisabled(),
    )
    expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-12.jpg' })).toBeEnabled()
  })
})

/* ------------------------------------------------------------------------------------------
 * A11 - die Grossansicht in der Seite
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Grossansicht', () => {
  async function oeffne(index: number, ids = [11, 12, 13, 14]) {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group(ids))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group(ids))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(ids.length))
    await userEvent.click(
      screen.getByRole('button', { name: `Reise/serie-${ids[index]}.jpg vergrößern` }),
    )
  }

  it('ersetzt das Raster an derselben Stelle, der Streifen fuehrt alle Mitglieder', async () => {
    await oeffne(1)

    expect(screen.getByRole('heading', { level: 2, name: 'Aufnahme 2 von 4' })).toBeTruthy()
    expect(tiles()).toHaveLength(0)
    expect(
      within(screen.getByRole('list', { name: 'Alle Aufnahmen der Gruppe' })).getAllByRole(
        'button',
      ),
    ).toHaveLength(4)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('kehrt per Esc ins Raster zurueck, mit dem Fokus auf der zuletzt GEZEIGTEN Aufnahme', async () => {
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Aufnahme' }))
    await userEvent.keyboard('{Escape}')

    expect(tiles()).toHaveLength(4)
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Reise/serie-13.jpg vergrößern' }),
    )
  })

  it('kehrt ueber "Vergroesserung schliessen" ins Raster zurueck', async () => {
    await oeffne(0)

    await userEvent.click(screen.getByRole('button', { name: 'Vergrößerung schließen' }))

    expect(tiles()).toHaveLength(4)
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Reise/serie-11.jpg vergrößern' }),
    )
  })

  it('haelt bei einer Entscheidung dieselbe Aufnahme, auch wenn die Antwort umsortiert ist', async () => {
    // `enlargedId` ist eine FOTO-ID: Ein Index zeigte nach der Antwort auf eine andere Aufnahme.
    // Die breite Invalidierung laedt die Gruppe danach neu - auch der Lesepfad liefert dann den
    // neuen Stand.
    const nachher = group([13, 11, 12], { decisions: ['keep', 'keep', 'discard'] })
    vi.mocked(duplicatesApi.getDuplicateGroup)
      .mockResolvedValueOnce(group([11, 12, 13]))
      .mockResolvedValue(nachher)
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(nachher)
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-12.jpg vergrößern' }))

    await userEvent.click(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-12.jpg' }))

    expect(await screen.findByRole('heading', { level: 2, name: 'Aufnahme 3 von 3' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-12.jpg' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('faellt aufs Raster zurueck, wenn die Aufnahme in der neuen Antwort fehlt', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup)
      .mockResolvedValueOnce(group([11, 12, 13]))
      .mockResolvedValue(group([11, 13]))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group([11, 13]))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-12.jpg vergrößern' }))

    await userEvent.click(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-12.jpg' }))

    await waitFor(() => expect(tiles()).toHaveLength(2))
    expect(screen.queryByRole('heading', { level: 2 })).toBeNull()
  })

  it('laesst die Pfeiltasten im Raster wirkungslos', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 1, total: 2, nextPhotoId: 20 }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.keyboard('{ArrowRight}')

    expect(screen.queryByRole('heading', { level: 2 })).toBeNull()
    expect(pfad()).toBe('/projects/1/photos/10/duplicates')
  })

  it('aendert bei einer Entscheidung in der Seitenspalte nur den Zustand', async () => {
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: 'Behalten: Reise/serie-12.jpg' }))

    await waitFor(() => expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalled())
    expect(screen.getByRole('heading', { level: 2, name: 'Aufnahme 2 von 4' })).toBeTruthy()
  })
})

/* ------------------------------------------------------------------------------------------
 * A9 - der Gruppenabschluss
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - der Abschluss', () => {
  it.each([
    ['naechste Gruppe', { nextPhotoId: 20 }, '', 'Gruppe abschließen, nächste'],
    [
      'letzte Gruppe mit Rueckweg',
      { nextPhotoId: null },
      '?from=ausschuss',
      'Gruppe abschließen, zum Ausschuss',
    ],
    ['letzte Gruppe ohne Rueckweg', { nextPhotoId: null }, '', 'Gruppe abschließen'],
  ])('beschriftet sich nach der Lage (%s)', async (_fall, nachbarn, suche, beschriftung) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12], nachbarn))
    renderPage(`/projects/1/photos/10/duplicates${suche}`)
    await waitFor(() => expect(tiles()).toHaveLength(2))

    expect(confirmButton().textContent).toBe(beschriftung)
  })

  it('ruft GENAU EINMAL den Abschluss und keinen der beiden Entscheidungswege', async () => {
    // SICHERHEIT (S4): Das Festschreiben des angezeigten Werts aus dem Client ist untersagt - es
    // schriebe "behalten" auf den Gewinner ohne Vorschlag. Auch ein Doppelklick bleibt EIN Aufruf.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.confirmDuplicateGroup).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.dblClick(confirmButton())

    expect(duplicatesApi.confirmDuplicateGroup).toHaveBeenCalledTimes(1)
    expect(duplicatesApi.confirmDuplicateGroup).toHaveBeenCalledWith(1, 10)
    expect(duplicatesApi.setDuplicateDecision).not.toHaveBeenCalled()
    expect(duplicatesApi.setDuplicateGroupDecision).not.toHaveBeenCalled()
    expect(confirmButton().textContent).toBe('Wird abgeschlossen…')
    expect(confirmButton()).toBeDisabled()
  })

  it.each([
    ['mit Rueckweg', '?from=ausschuss', '/projects/1/photos/20/duplicates?from=ausschuss'],
    ['ohne Rueckweg', '', '/projects/1/photos/20/duplicates'],
  ])('wechselt nach dem Erfolg auf die naechste Gruppe (%s)', async (_fall, suche, ziel) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { nextPhotoId: 20 }),
    )
    vi.mocked(duplicatesApi.confirmDuplicateGroup).mockResolvedValue(
      group([11, 12], { nextPhotoId: 20 }),
    )
    renderPage(`/projects/1/photos/10/duplicates${suche}`)
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(confirmButton())

    await waitFor(() => expect(pfad()).toBe(ziel))
  })

  it('fuehrt an der letzten Gruppe mit Rueckweg auf den festen Pfad des Ausschusses', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.confirmDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage('/projects/1/photos/10/duplicates?from=ausschuss')
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(confirmButton())

    await waitFor(() => expect(pfad()).toBe('/projects/1/pipeline/ausschuss'))
  })

  it('bleibt an der letzten Gruppe ohne Rueckweg stehen und meldet das - bis zum Ankerwechsel', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      Promise.resolve(
        photoId === 10
          ? group([11, 12], { position: 2, total: 2, previousPhotoId: 5 })
          : group([6, 7], { position: 1, total: 2, nextPhotoId: 10 }),
      ),
    )
    vi.mocked(duplicatesApi.confirmDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 2, previousPhotoId: 5 }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(confirmButton())

    const meldung = await screen.findByText('Gespeichert — das war die letzte Gruppe.')
    expect(meldung.getAttribute('aria-live')).toBe('polite')
    expect(pfad()).toBe('/projects/1/photos/10/duplicates')

    await userEvent.click(screen.getByRole('button', { name: 'Vorherige Gruppe' }))
    await waitFor(() => expect(pfad()).toBe('/projects/1/photos/5/duplicates'))
    expect(screen.queryByText('Gespeichert — das war die letzte Gruppe.')).toBeNull()
  })

  it('zeigt einen Fehler ohne Navigation und laesst die Schaltflaeche wieder zu', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { nextPhotoId: 20 }),
    )
    vi.mocked(duplicatesApi.confirmDuplicateGroup).mockRejectedValue(
      new ApiError(409, 'Die Entscheidung wurde gerade verändert. Bitte erneut versuchen.'),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(confirmButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Entscheidung wurde gerade verändert. Bitte erneut versuchen.',
    )
    expect(pfad()).toBe('/projects/1/photos/10/duplicates')
    expect(confirmButton()).toBeEnabled()
  })

  it.each([
    ['Einzelentscheidung', 'Behalten: Reise/serie-11.jpg'],
    ['Gruppenentscheidung', 'Alle behalten'],
  ])('ist gesperrt, solange eine %s laeuft', async (_fall, name) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockReturnValue(new Promise(() => {}))
    vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name }))

    await waitFor(() => expect(confirmButton()).toBeDisabled())
  })
})

/* ------------------------------------------------------------------------------------------
 * A10/S11 - der Rueckweg waehlt eine Variante und nennt kein Ziel
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - der Rueckweg', () => {
  it('fuehrt bei from=ausschuss fest in den Ausschuss-Schritt des Projekts', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage('/projects/1/photos/10/duplicates?from=ausschuss')

    const link = await screen.findByRole('link', { name: 'Zurück zum Ausschuss' })
    expect(link.getAttribute('href')).toBe('/projects/1/pipeline/ausschuss')
  })

  it.each([
    ['ohne from', ''],
    ['leeres from', '?from='],
    ['andere Schreibung', '?from=Ausschuss'],
    ['Suffix', '?from=ausschuss2'],
    ['absolute URL', '?from=https%3A%2F%2Fexample.org'],
    ['interner Pfad', '?from=%2Fprojects%2F2%2Fpipeline%2Fausschuss'],
    ['doppelter Parameter', '?from=x&from=ausschuss'],
  ])('bietet keinen Rueckweg an (%s)', async (_fall, suche) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage(`/projects/1/photos/10/duplicates${suche}`)
    await waitFor(() => expect(tiles()).toHaveLength(2))

    expect(screen.queryByRole('link', { name: /Ausschuss/ })).toBeNull()
  })

  it.each([
    ['ladend', () => new Promise<DuplicateGroupOut>(() => {})],
    ['leer', () => Promise.reject(new ApiError(404, 'Keine Duplikat-Gruppe zu diesem Foto.'))],
    ['fehlerhaft', () => Promise.reject(new ApiError(500, 'Interner Fehler.'))],
  ])('steht auch im Zustand "%s"', async (_fall, antwort) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation(antwort)
    renderPage('/projects/1/photos/10/duplicates?from=ausschuss')

    expect(await screen.findByRole('link', { name: 'Zurück zum Ausschuss' })).toHaveAttribute(
      'href',
      '/projects/1/pipeline/ausschuss',
    )
  })
})

/* ------------------------------------------------------------------------------------------
 * A13 - die vier Zustaende der Seite
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Zustaende', () => {
  function nurImGefuellten() {
    expect(screen.queryByText(DUPLICATE_HINT_TEXT)).toBeNull()
    expect(screen.queryByRole('group', { name: 'Ganze Gruppe' })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Gruppe abschließen/ })).toBeNull()
  }

  it('zeigt waehrend des Ladens Kartenplatzhalter unter der allgemeinen Ueberschrift', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(
      await screen.findByRole('status', { name: 'Duplikat-Gruppe wird geladen…' }),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'Duplikate vergleichen' })).toBeTruthy()
    nurImGefuellten()
  })

  it.each([
    ['HTTP 404', () => Promise.reject(new ApiError(404, 'Keine Duplikat-Gruppe zu diesem Foto.'))],
    ['200 ohne Mitglieder', () => Promise.resolve(group([]))],
  ])('zeigt bei %s den LEEREN Zustand, nicht den Fehler-Alert', async (_fall, antwort) => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation(antwort)
    renderPage()

    expect(await screen.findByText(DUPLICATE_EMPTY_TEXT)).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('heading', { level: 1, name: 'Duplikate vergleichen' })).toBeTruthy()
    nurImGefuellten()
  })

  it('zeigt bei jedem anderen Fehler den Alert samt Wiederholung', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockRejectedValue(
      new ApiError(500, 'Interner Fehler.'),
    )
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Interner Fehler.')
    expect(screen.getByRole('button', { name: 'Erneut versuchen' })).toBeTruthy()
    expect(screen.queryByText(DUPLICATE_EMPTY_TEXT)).toBeNull()
    nurImGefuellten()
  })
})
