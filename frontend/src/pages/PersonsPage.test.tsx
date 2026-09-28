import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import type { PersonOut } from '../api/types'
import { PersonsPage } from './PersonsPage'

vi.mock('../api/persons')

/*
 * Erstfokus, Fokusfalle und Fokusrueckgabe des Dialog-Grundelements liegen in
 * `ui/dialog.test.tsx` und werden hier nicht wiederholt.
 */

const ANNA: PersonOut = { id: 1, name: 'Anna', reference_count: 1 }
const BEN: PersonOut = { id: 2, name: 'Ben', reference_count: 3 }

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={['/persons']}>
      <Routes>
        <Route path="/persons" element={<PersonsPage />} />
        <Route path="/" element={<p>Projektliste</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
  return { queryClient }
}

async function openRemoveDialog(name: string) {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: `${name} entfernen` }))
  return { user, dialog: screen.getByRole('dialog', { name: 'Person entfernen?' }) }
}

describe('PersonsPage', () => {
  beforeEach(() => {
    vi.mocked(personsApi.listPersons).mockReset()
    vi.mocked(personsApi.deletePerson).mockReset()
  })

  describe('die Zustaende', () => {
    it('zeigt waehrend des Ladens einen benannten Ladezustand und keine Gefahrenzone', async () => {
      vi.mocked(personsApi.listPersons).mockReturnValue(new Promise(() => {}))

      renderPage()

      expect(
        await screen.findByRole('status', { name: 'Personen werden geladen…' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Person entfernen' })).not.toBeInTheDocument()
    })

    it('zeigt einen Fehler mit "Erneut versuchen", der die Liste neu laedt', async () => {
      vi.mocked(personsApi.listPersons)
        .mockRejectedValueOnce(new ApiError(500, 'Serverfehler'))
        .mockResolvedValueOnce([ANNA])
      const user = userEvent.setup()

      renderPage()

      const alert = await screen.findByRole('alert')
      expect(screen.queryByRole('heading', { name: 'Person entfernen' })).not.toBeInTheDocument()
      await user.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))
      expect(await screen.findByRole('heading', { name: 'Anna', level: 2 })).toBeInTheDocument()
    })

    it('erklaert im Leerzustand ohne Alert, wo eine Person festgelegt wird', async () => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([])
      const user = userEvent.setup()

      renderPage()

      expect(
        await screen.findByText(
          'Noch keine Person festgelegt. Eine Person legst du in der Personenübersicht eines ' +
            'Projekts fest oder in der Detailansicht eines Fotos im Abschnitt „Personen“ mit ' +
            '„Gesicht zeigen“.',
        ),
      ).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Person entfernen' })).not.toBeInTheDocument()
      await user.click(screen.getByRole('link', { name: 'Zu den Projekten' }))
      expect(await screen.findByText('Projektliste')).toBeInTheDocument()
    })

    it('zeigt je Person eine Karte mit dem Namen als Ueberschrift und die Gefahrenzone', async () => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])

      renderPage()

      const cards = await screen.findAllByRole('listitem')
      expect(
        cards.map((card) => within(card).getByRole('heading', { level: 2 }).textContent),
      ).toEqual(['Anna', 'Ben'])
      expect(screen.getByRole('heading', { name: 'Person entfernen' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Anna entfernen' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Ben entfernen' })).toBeInTheDocument()
      // Auf der Karte selbst gibt es keine Aktion.
      expect(within(cards[0]).queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('der Zaehltext', () => {
    it.each([
      [1, 'einmal gezeigt'],
      [3, '3-mal gezeigt'],
      [0, 'Noch kein Gesicht gezeigt – ohne gezeigtes Gesicht wird die Person nicht erkannt.'],
    ])('nennt bei %i gezeigten Gesichtern "%s"', async (count, text) => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([{ ...ANNA, reference_count: count }])

      renderPage()

      const card = await screen.findByRole('listitem')
      expect(within(card).getByText(text)).toBeInTheDocument()
    })
  })

  describe('der Entfernen-Dialog', () => {
    beforeEach(() => {
      vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    })

    it('nennt die Folgen und den zu tippenden Namen', async () => {
      renderPage()

      const { dialog } = await openRemoveDialog('Anna')

      expect(
        within(dialog).getByText(
          'Anna wird auf allen Fotos in allen Projekten entfernt, samt der von Hand ' +
            'vorgenommenen Zuordnungen und aller gezeigten Gesichter. Das lässt sich nicht ' +
            'rückgängig machen.',
        ),
      ).toBeInTheDocument()
      expect(within(dialog).getByText('Zur Bestätigung den Namen eingeben:')).toBeInTheDocument()
      expect(within(dialog).getByText('Anna', { selector: '.font-mono' })).toBeInTheDocument()
    })

    it('schaltet "Entfernen" erst bei exakter Uebereinstimmung frei', async () => {
      renderPage()
      const { user, dialog } = await openRemoveDialog('Anna')
      const input = within(dialog).getByRole('textbox')
      const remove = within(dialog).getByRole('button', { name: 'Entfernen' })

      expect(remove).toBeDisabled()
      await user.type(input, 'anna')
      expect(remove).toBeDisabled()
      await user.clear(input)
      await user.type(input, 'Anna ')
      expect(remove).toBeDisabled()
      await user.clear(input)
      await user.type(input, 'Anna')
      expect(remove).toBeEnabled()
      expect(personsApi.deletePerson).not.toHaveBeenCalled()
    })

    it('sperrt waehrend der Anfrage Abbrechen und Esc', async () => {
      vi.mocked(personsApi.deletePerson).mockReturnValue(new Promise(() => {}))
      renderPage()
      const { user, dialog } = await openRemoveDialog('Anna')
      await user.type(within(dialog).getByRole('textbox'), 'Anna')

      await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

      expect(await within(dialog).findByRole('button', { name: 'Wird entfernt…' })).toBeDisabled()
      expect(within(dialog).getByRole('button', { name: 'Abbrechen' })).toBeDisabled()
      await user.keyboard('{Escape}')
      expect(screen.getByRole('dialog', { name: 'Person entfernen?' })).toBeInTheDocument()
    })

    it('behaelt bei einem Fehler den getippten Namen und laesst die Schaltflaeche wiederholen', async () => {
      vi.mocked(personsApi.deletePerson)
        .mockRejectedValueOnce(new ApiError(500, 'Datenbank nicht erreichbar.'))
        .mockResolvedValueOnce(undefined)
      renderPage()
      const { user, dialog } = await openRemoveDialog('Anna')
      await user.type(within(dialog).getByRole('textbox'), 'Anna')

      await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Datenbank nicht erreichbar.',
      )
      expect(within(dialog).getByRole('textbox')).toHaveValue('Anna')
      await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(personsApi.deletePerson).toHaveBeenCalledTimes(2)
    })

    it('beginnt nach Abbrechen wieder mit leerem Feld', async () => {
      renderPage()
      const { user, dialog } = await openRemoveDialog('Anna')
      await user.type(within(dialog).getByRole('textbox'), 'Anna')
      await user.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))

      const reopened = (await openRemoveDialog('Anna')).dialog

      expect(within(reopened).getByRole('textbox')).toHaveValue('')
      expect(within(reopened).getByRole('button', { name: 'Entfernen' })).toBeDisabled()
    })

    it.each([
      ['Erfolg', () => vi.mocked(personsApi.deletePerson).mockResolvedValue(undefined)],
      [
        '404',
        () =>
          vi
            .mocked(personsApi.deletePerson)
            .mockRejectedValue(new ApiError(404, 'Person nicht gefunden.')),
      ],
    ])(
      'schliesst bei %s, laedt neu, fokussiert h1, meldet und entwertet alle Fotolisten',
      async (_name, arrange) => {
        arrange()
        const { queryClient } = renderPage()
        queryClient.setQueryData(['photos', 1, 'grid'], { items: [], total: 0 })
        queryClient.setQueryData(['photos', 2, 'draft'], { items: [] })
        const { user, dialog } = await openRemoveDialog('Anna')
        vi.mocked(personsApi.listPersons).mockResolvedValue([BEN])
        await user.type(within(dialog).getByRole('textbox'), 'Anna')

        await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
        expect(personsApi.deletePerson).toHaveBeenCalledWith(1)
        await waitFor(() =>
          expect(screen.queryByRole('heading', { name: 'Anna' })).not.toBeInTheDocument(),
        )
        expect(screen.getByRole('heading', { name: 'Personen', level: 1 })).toHaveFocus()
        expect(screen.getByText('Anna ist entfernt.')).toHaveAttribute('role', 'status')
        expect(queryClient.getQueryState(['photos', 1, 'grid'])?.isInvalidated).toBe(true)
        expect(queryClient.getQueryState(['photos', 2, 'draft'])?.isInvalidated).toBe(true)
      },
    )
  })

  /* Namen sind Fremdtext: An jeder Renderstelle der Seite - Karte,
     Gefahrenzone, Dialogtext, Tippvorlage, Statusmeldung - stehen sie nur als Textknoten. */
  it('rendert einen Namen mit Markup an jeder Stelle der Seite als reinen Text', async () => {
    const hostile = '<img src=x onerror="window.__pwned = true">'
    vi.mocked(personsApi.listPersons).mockResolvedValue([{ ...ANNA, name: hostile }])
    vi.mocked(personsApi.deletePerson).mockResolvedValue(undefined)
    renderPage()

    expect(await screen.findByRole('heading', { name: hostile, level: 2 })).toBeInTheDocument()
    const { user, dialog } = await openRemoveDialog(hostile)
    expect(
      within(dialog).getByText(`${hostile} wird auf allen Fotos`, { exact: false }),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(hostile, { selector: '.font-mono' })).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()

    vi.mocked(personsApi.listPersons).mockResolvedValue([])
    await user.type(within(dialog).getByRole('textbox'), hostile)
    await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

    expect(await screen.findByText(`${hostile} ist entfernt.`)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })
})
