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
    previousPhotoId?: number | null
    nextPhotoId?: number | null
  } = {},
): DuplicateGroupOut {
  return {
    items: ids.map((id, index) => ({
      photo: photo(id),
      effective_decision: overrides.decisions?.[index] ?? 'keep',
      keep_possible: overrides.keepPossible?.[index] ?? true,
    })),
    position: overrides.position ?? 1,
    total: overrides.total ?? 1,
    previous_photo_id: overrides.previousPhotoId ?? null,
    next_photo_id: overrides.nextPhotoId ?? null,
  }
}

/** Die tatsächlich besuchte Route — die Seite bleibt beim Gruppenwechsel montiert, nur der
 * Parameter ändert sich, und genau das muss prüfbar sein. */
function Pfadspiegel() {
  const ort = useLocation()
  return <span data-testid="pfad">{ort.pathname}</span>
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={['/projects/1/photos/10/duplicates']}>
      <Pfadspiegel />
      <Routes>
        <Route
          path="/projects/:projectId/photos/:photoId/duplicates"
          element={<DuplicateComparePage />}
        />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

function tiles(): HTMLElement[] {
  return screen.getAllByRole('listitem')
}

beforeEach(() => {
  vi.mocked(duplicatesApi.getDuplicateGroup).mockReset()
  vi.mocked(duplicatesApi.setDuplicateDecision).mockReset()
  vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockReset()
})

/* ------------------------------------------------------------------------------------------
 * AK1/AK2 - Gruppe und Gleichrangigkeit
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Gruppe', () => {
  it('rendert jedes Mitglied in der gelieferten Reihenfolge', async () => {
    // DIE REIHENFOLGE KOMMT VOM SERVER. Die Seite sortiert nicht nach - eine zweite
    // Sortierregel liefe mit der ersten auseinander, und die Kacheln spraengen beim Neuladen.
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
    // AK2: Alle Mitglieder werden von DERSELBEN Kachelkomponente gerendert. Geprueft als
    // Gleichheit der Kachelstruktur - eine Sonderrolle brauchte ein zusaetzliches Element und
    // faellt hier auf.
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
})

/* ------------------------------------------------------------------------------------------
 * AK10/AK11 - Zaehler und Hinweiszeile
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - Zaehler und Hinweis', () => {
  it('nennt Position und Gesamtzahl in der Seitenueberschrift', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 5 }),
    )
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Duplikat-Gruppe 2 von 5' })).toBeTruthy()
  })

  it('traegt eine unveraenderliche Hinweiszeile ueber den DARGESTELLTEN Zustand', async () => {
    // AK4: Die Zeile sagt, dass der angezeigte Zustand gilt, wenn man ihn nicht ändert. Sie darf
    // weder behaupten, es liege noch keine Entscheidung vor, noch zusichern, dass "unentschiedene"
    // Aufnahmen erhalten bleiben - ein unentschiedener Duplikat-Verlierer fällt am Gate heraus.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage()

    expect(await screen.findByText(DUPLICATE_HINT_TEXT)).toBeTruthy()
    expect(DUPLICATE_HINT_TEXT).not.toMatch(/bleib|erhalten|noch nicht|offen/i)
    expect(DUPLICATE_HINT_TEXT).toMatch(/änder/i)
  })

  it('benennt an der Handlung, was "behalten" nach sich zieht', async () => {
    // SICHERHEIT (S4): "Behalten" ist keine ansichtsinterne Buchfuehrung - die Aufnahme laeuft in
    // die Kriterien-Bewertung und, bei erteilter Einwilligung, in die Cloud-Klassifizierung.
    // Steht das nicht an der Handlung, entscheidet der Nutzer ueber einen Datenabfluss, von dem
    // er nichts weiss.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage()

    const hinweis = await screen.findByTestId('duplicate-consequence')
    expect(hinweis.textContent).toMatch(/Cloud/i)
    expect(hinweis.textContent).toMatch(/behalten/i)
  })
})

/* ------------------------------------------------------------------------------------------
 * AK5 - vor und zurueck zwischen den Gruppen
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Gruppennavigation', () => {
  it('steht ohne jede Vergroesserung im Seitenkopf', async () => {
    // AK5: Aus der Ansicht heraus erreichbar, also unabhaengig davon, ob gerade eine Aufnahme
    // vergroessert ist. An die Vergroesserungssteuerung gehaengt waere sie ohne Vergroesserung
    // unerreichbar - und der Durchgang damit gar nicht.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()

    expect(await screen.findByRole('button', { name: 'Zurück zur vorherigen Gruppe' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull()
  })

  it('traegt Namen, die sich nicht mit dem Blaettern INNERHALB der Gruppe ueberschneiden', async () => {
    // AK7: Die bestehenden `Vorherige/Nächste Aufnahme der Gruppe` der Vergroesserung stehen
    // gleichzeitig im Dokument. Ueberschnitten sich die Namen, waeren sechs bestehende
    // `getByRole`-Abfragen mehrdeutig - und zwar still, als Testfehler statt als Produktfehler.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12, 13], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(3))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-12.jpg vergrößern' }))

    for (const name of [
      'Zurück zur vorherigen Gruppe',
      'Vor zur nächsten Gruppe',
      'Vorherige Aufnahme der Gruppe',
      'Nächste Aufnahme der Gruppe',
    ]) {
      expect(screen.getAllByRole('button', { name })).toHaveLength(1)
    }
  })

  it('beginnt den zugaenglichen Namen mit der sichtbaren Beschriftung (WCAG 2.5.3)', async () => {
    // Zugesichert in specs/architecture/0004-design-system.md. Enthaelt der zugaengliche Name den
    // sichtbaren Text nicht als ZUSAMMENHAENGENDE Kette, ist das Element per Spracheingabe nicht
    // ansprechbar - "Klick Zurueck" findet dann nichts.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 2, total: 3, previousPhotoId: 5, nextPhotoId: 20 }),
    )
    renderPage()

    const navigation = await screen.findByRole('group', { name: 'Duplikat-Gruppen' })
    const knoepfe = within(navigation).getAllByRole('button')

    expect(knoepfe.map((knopf) => knopf.textContent)).toEqual(['Zurück', 'Vor'])
    for (const knopf of knoepfe) {
      expect(knopf.getAttribute('aria-label')).toMatch(new RegExp(`^${knopf.textContent}\\b`, 'iu'))
    }
  })

  it.each([
    ['am Anfang', { previousPhotoId: null, nextPhotoId: 20 }, true, false],
    ['am Ende', { previousPhotoId: 5, nextPhotoId: null }, false, true],
    ['in der Mitte', { previousPhotoId: 5, nextPhotoId: 20 }, false, false],
  ])(
    'ist %s genau dort disabled, wo der Nachbarwert null ist',
    async (_fall, nachbarn, zurueckGesperrt, vorGesperrt) => {
      // `disabled`, nicht "fehlt": Ein verschwindender Knopf verschöbe die übrigen unter dem
      // Finger, und am Rand bliebe unklar, ob es dort nichts gibt oder die Ansicht etwas
      // vergessen hat.
      vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12], nachbarn))
      renderPage()

      const zurueck = await screen.findByRole('button', { name: 'Zurück zur vorherigen Gruppe' })
      expect(zurueck).toHaveProperty('disabled', zurueckGesperrt)
      expect(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' })).toHaveProperty(
        'disabled',
        vorGesperrt,
      )
    },
  )

  it('bleibt WAEHREND DES LADENS der Nachbargruppe stehen', async () => {
    // Der Query-Schluessel traegt den Anker - beim Blaettern gibt es fuer den neuen keine Daten.
    // Ohne Vorhalten faellt die Seite in den Ladezustand, die Navigation verschwindet mitsamt dem
    // gerade gedrueckten Knopf, und beim Durchgang durch viele Gruppen springt sie bei JEDEM
    // Schritt weg. Das bricht zugleich die Begruendung fuer `disabled` statt abwesend.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      photoId === 10
        ? Promise.resolve(group([11, 12], { position: 1, total: 2, nextPhotoId: 20 }))
        : // Loest NIE auf: der Ladezustand der Nachbargruppe bleibt stehen und ist messbar.
          new Promise(() => {}),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' }))

    await waitFor(() => expect(screen.getByTestId('pfad').textContent).toContain('/photos/20/'))
    expect(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Zurück zur vorherigen Gruppe' })).toBeTruthy()
  })

  it('navigiert auf den Anker der Nachbargruppe - als Push, nicht als Ersetzung', async () => {
    // Der Pfadwert bleibt ein ANKER-Foto, es gibt keinen Gruppenindex in der Route. Push statt
    // `replace`: Der Zurueck-Knopf des Browsers ist dann "vorherige Gruppe".
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(
      group([11, 12], { position: 1, total: 2, nextPhotoId: 20 }),
    )
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' }))

    expect(screen.getByTestId('pfad').textContent).toBe('/projects/1/photos/20/duplicates')
  })
})

/* ------------------------------------------------------------------------------------------
 * AK5 - die Seite bleibt beim Gruppenwechsel montiert
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - der Ankerwechsel', () => {
  /** Zwei Gruppen hinter einem Anker - der Hin- und Rueckweg ist die einzige Form, in der ein
   * stehen gebliebener Zustand sichtbar wird: Zwei Gruppen sind disjunkt, eine Id der alten
   * traefe in der neuen ohnehin keine Kachel. */
  function zweiGruppen() {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockImplementation((_projectId, photoId) =>
      Promise.resolve(
        photoId === 10
          ? group([11, 12], { position: 1, total: 2, nextPhotoId: 20 })
          : group([21, 22], { position: 2, total: 2, previousPhotoId: 10 }),
      ),
    )
  }

  async function wechsleGruppe() {
    await userEvent.click(screen.getByRole('button', { name: 'Vor zur nächsten Gruppe' }))
  }

  it('nimmt die Vergroesserung zurueck', async () => {
    // Gleiche Route, anderer Parameter - die Seite wird NICHT neu montiert. `enlargedId` zeigte
    // sonst weiter auf ein Foto der alten Gruppe und vergroesserte es beim Zurueckblaettern
    // erneut, ohne dass jemand darum gebeten haette.
    zweiGruppen()
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: 'Reise/serie-11.jpg vergrößern' }))
    expect(screen.getByRole('button', { name: /verkleinern$/ })).toBeTruthy()

    await wechsleGruppe()
    await waitFor(() => expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull())
    await userEvent.click(screen.getByRole('button', { name: 'Zurück zur vorherigen Gruppe' }))

    await waitFor(() => expect(tiles()).toHaveLength(2))
    expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull()
  })

  it('nimmt die laufende Entscheidung zurueck', async () => {
    // GETRENNT vom Fall darueber: Eine Ruecksetzung erfasst leicht nur einen der beiden Zustaende.
    //
    // Gemessen ueber einen HIN- UND RUECKWEG, nicht ueber einen einzelnen Wechsel: Zwei Gruppen
    // sind disjunkt, eine stehen gebliebene Id der alten Gruppe traefe in der neuen also ohnehin
    // keine Kachel. Erst bei der Rueckkehr sperrt sie wieder - und zwar dauerhaft, weil die
    // Entscheidung nie auffloest.
    zweiGruppen()
    vi.mocked(duplicatesApi.setDuplicateDecision).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))
    await userEvent.click(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' })).toHaveProperty(
        'disabled',
        true,
      ),
    )

    await wechsleGruppe()
    await waitFor(() => expect(screen.getByTestId('pfad').textContent).toContain('/photos/20/'))
    await userEvent.click(screen.getByRole('button', { name: 'Zurück zur vorherigen Gruppe' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Ausschuss: Reise/serie-11.jpg' })).toHaveProperty(
        'disabled',
        false,
      ),
    )
    expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' })).toHaveProperty(
      'disabled',
      false,
    )
  })
})

/* ------------------------------------------------------------------------------------------
 * AK9 - gruppenweite Abkuerzungen
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
 * AK4 - Einzelentscheidung
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
    // Eine Seiten-weite Sperre blockierte den zuegigen Durchlauf, den die Ansicht gerade
    // ermoeglichen soll.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(2))

    await userEvent.click(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-11.jpg' })).toHaveProperty(
        'disabled',
        true,
      ),
    )
    expect(screen.getByRole('button', { name: 'Behalten: Reise/serie-12.jpg' })).toHaveProperty(
      'disabled',
      false,
    )
  })
})

/* ------------------------------------------------------------------------------------------
 * AK7/AK8 - Vergroessern, Blaettern, Verkleinern
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Vergroesserung', () => {
  async function oeffne(index: number, ids = [11, 12, 13, 14]) {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group(ids))
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group(ids))
    renderPage()
    await waitFor(() => expect(tiles()).toHaveLength(ids.length))
    await userEvent.click(
      screen.getByRole('button', { name: `Reise/serie-${ids[index]}.jpg vergrößern` }),
    )
  }

  it('vergroessert hoechstens EIN Mitglied und laesst alle uebrigen im Dokument', async () => {
    await oeffne(1)

    expect(screen.getAllByRole('button', { name: /verkleinern$/ })).toHaveLength(1)
    expect(tiles()).toHaveLength(4)
  })

  it('verkleinert beim erneuten Antippen derselben Kachel', async () => {
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: /verkleinern$/ }))

    expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull()
  })

  it('verkleinert per Esc', async () => {
    await oeffne(1)

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull()
  })

  it('bietet ein sichtbares Schliessen-Element mit eigenem zugaenglichen Namen', async () => {
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: 'Vergrößerung schließen' }))

    expect(screen.queryByRole('button', { name: /verkleinern$/ })).toBeNull()
  })

  it('blaettert mit Vor/Zurueck, ohne zu verkleinern', async () => {
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Aufnahme der Gruppe' }))

    expect(screen.getByRole('button', { name: /verkleinern$/ }).getAttribute('aria-label')).toBe(
      'Reise/serie-13.jpg verkleinern',
    )
  })

  it('blaettert auch mit den Pfeiltasten', async () => {
    await oeffne(1)

    await userEvent.keyboard('{ArrowLeft}')

    expect(screen.getByRole('button', { name: /verkleinern$/ }).getAttribute('aria-label')).toBe(
      'Reise/serie-11.jpg verkleinern',
    )
  })

  it('bleibt am ersten und letzten Mitglied stehen und weist das aus', async () => {
    // KEIN Rundlauf: Ein Sprung vom letzten zum ersten Bild waere in einer Vergleichsansicht ein
    // verlorener Ueberblick, kein Komfort.
    await oeffne(0)
    expect(screen.getByRole('button', { name: 'Vorherige Aufnahme der Gruppe' })).toHaveProperty(
      'disabled',
      true,
    )

    await userEvent.keyboard('{ArrowLeft}')
    expect(screen.getByRole('button', { name: /verkleinern$/ }).getAttribute('aria-label')).toBe(
      'Reise/serie-11.jpg verkleinern',
    )
  })

  it('haelt die Vergroesserung bei einer Entscheidung und blaettert nicht weiter', async () => {
    // AK8: Eine Entscheidung in der Vergroesserung aendert den Zustand - sonst nichts.
    await oeffne(1)

    await userEvent.click(screen.getByRole('button', { name: 'Behalten: Reise/serie-12.jpg' }))

    await waitFor(() => expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /verkleinern$/ }).getAttribute('aria-label')).toBe(
      'Reise/serie-12.jpg verkleinern',
    )
  })
})

/* ------------------------------------------------------------------------------------------
 * AK15 - die vier Zustaende der Seite
 * ---------------------------------------------------------------------------------------- */

describe('DuplicateComparePage - die Zustaende', () => {
  it('zeigt waehrend des Ladens Platzhalter, keinen Text', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(await screen.findByRole('status', { name: /geladen/i })).toBeTruthy()
  })

  it('zeigt bei HTTP 404 den LEEREN Zustand, nicht den Fehler-Alert', async () => {
    // Die vier 404-Faelle sind keine Stoerung: Zu dieser Aufnahme gibt es schlicht keine Gruppe.
    // Ein Fehler-Alert behauptete einen Vorfall und boete "Erneut versuchen" fuer etwas an, das
    // beim naechsten Versuch genauso ausgeht.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockRejectedValue(
      new ApiError(404, 'Keine Duplikat-Gruppe zu diesem Foto.'),
    )
    renderPage()

    expect(await screen.findByText(DUPLICATE_EMPTY_TEXT)).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('zeigt bei jedem anderen Fehler den Alert samt Wiederholung', async () => {
    vi.mocked(duplicatesApi.getDuplicateGroup).mockRejectedValue(
      new ApiError(500, 'Interner Fehler.'),
    )
    renderPage()

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByText('Interner Fehler.')).toBeTruthy()
    expect(screen.queryByText(DUPLICATE_EMPTY_TEXT)).toBeNull()
  })
})
