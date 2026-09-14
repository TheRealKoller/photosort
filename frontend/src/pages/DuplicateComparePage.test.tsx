import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
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
  overrides: { position?: number; total?: number; decisions?: (DuplicateDecision | null)[] } = {},
): DuplicateGroupOut {
  return {
    items: ids.map((id, index) => ({
      photo: photo(id),
      decision: overrides.decisions?.[index] ?? null,
    })),
    position: overrides.position ?? 1,
    total: overrides.total ?? 1,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={['/projects/1/photos/10/duplicates']}>
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

  it('traegt eine unveraenderliche Hinweiszeile, die den Vorschlag des Systems nennt', async () => {
    // AK11: Die Zeile sagt NICHT zu, dass unentschiedene Aufnahmen erhalten bleiben - ein
    // unentschiedener Duplikat-Verlierer faellt am Gate heraus.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([11, 12]))
    renderPage()

    expect(await screen.findByText(DUPLICATE_HINT_TEXT)).toBeTruthy()
    expect(DUPLICATE_HINT_TEXT).not.toMatch(/bleib|erhalten/i)
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
