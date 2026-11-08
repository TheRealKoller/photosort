import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { CloudModelOut, ModelChoiceOut } from '../api/types'
import { ModelChoiceSection } from './ModelChoiceSection'

/**
 * Spec 0383, Abschnitt „Modellwahl": zwei Gruppen über `name`, eine Karte je Katalogeintrag, die
 * fünf Werte, „Preis unbekannt", die Eye-Karte samt Nennung und #621-Hinweis, gesperrte Marken mit
 * Grund, Laden/Fehler/Speicherfehler und die Atomarität des einen `PUT`.
 */

vi.mock('../api/projects')

const MISTRAL: CloudModelOut = {
  provider: 'mistral',
  model: 'ministral-3b-2512',
  estimate_usd_per_image: 0.000305,
  input_usd_per_mtok: 0.1,
  output_usd_per_mtok: 0.3,
  requests_per_minute: 60,
  available: true,
  unavailable_reasons: [],
}

const ANTHROPIC: CloudModelOut = {
  provider: 'anthropic',
  model: 'claude-haiku-4-5',
  estimate_usd_per_image: 0.0052,
  input_usd_per_mtok: 1,
  output_usd_per_mtok: 5,
  requests_per_minute: 50,
  available: false,
  unavailable_reasons: ['no_api_key'],
}

function choice(overrides: Partial<ModelChoiceOut> = {}): ModelChoiceOut {
  return {
    current: {
      category_method: 'cloud',
      category_model: MISTRAL.model,
      category_provider: 'mistral',
      category_is_default: false,
      landmark_model: MISTRAL.model,
      landmark_provider: 'mistral',
      landmark_is_default: false,
    },
    cloud_models: [MISTRAL, ANTHROPIC],
    eye: { available: true, unavailable_reasons: [] },
    ...overrides,
  }
}

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(<ModelChoiceSection projectId={1} />, { wrapper })
}

beforeEach(() => {
  vi.mocked(projectsApi.getModelChoice).mockReset()
  vi.mocked(projectsApi.putModelChoice).mockReset()
  vi.mocked(projectsApi.getModelChoice).mockResolvedValue(choice())
})

describe('ModelChoiceSection: der Katalog', () => {
  it('zeigt eine Karte je Eintrag in Serverreihenfolge, Eye als letzte', async () => {
    renderSection()

    const cards = await screen.findAllByTestId(/^model-card-/)
    expect(cards.map((card) => card.dataset.testid)).toEqual([
      `model-card-${MISTRAL.model}`,
      `model-card-${ANTHROPIC.model}`,
      'model-card-eye',
    ])
  })

  it('nennt je Karte die fünf Werte', async () => {
    renderSection()

    const card = await screen.findByTestId(`model-card-${MISTRAL.model}`)
    expect(card).toHaveTextContent('Mistral')
    expect(card).toHaveTextContent('ministral-3b-2512')
    expect(card).toHaveTextContent('0,000305 USD je Bild')
    expect(card).toHaveTextContent(/je Million Eingabe-Token/)
    expect(card).toHaveTextContent(/60 Anfragen pro Minute — gilt für alle Projekte gemeinsam/)
  })

  it('schreibt bei fehlendem Preis "Preis unbekannt", nie eine Null', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        cloud_models: [
          {
            ...MISTRAL,
            estimate_usd_per_image: null,
            input_usd_per_mtok: null,
            output_usd_per_mtok: null,
          },
        ],
      }),
    )
    renderSection()

    const card = await screen.findByTestId(`model-card-${MISTRAL.model}`)
    expect(card).toHaveTextContent('Preis unbekannt')
    expect(card).not.toHaveTextContent('0,00 USD')
    expect(card).toHaveTextContent('unbekannt je Million Eingabe-Token')
  })

  it('sagt am Kopf der Gruppe, wenn kein Modell für die Sehenswürdigkeits-Erkennung wählbar ist', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        cloud_models: [
          { ...MISTRAL, available: false, unavailable_reasons: ['no_api_key'] },
          ANTHROPIC,
        ],
      }),
    )
    renderSection()

    expect(await screen.findByTestId('model-choice-no-landmark-model')).toHaveTextContent(
      'Für die Sehenswürdigkeits-Erkennung ist derzeit kein Modell wählbar',
    )
  })

  it('sagt diesen Satz nicht, solange ein Modell wählbar ist', async () => {
    renderSection()

    await screen.findByTestId('model-card-eye')
    expect(screen.queryByTestId('model-choice-no-landmark-model')).not.toBeInTheDocument()
  })

  it('setzt die Wahl auf die Installationsvorgabe, wenn sie von dort kommt', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'cloud',
          category_model: MISTRAL.model,
          category_provider: 'mistral',
          category_is_default: true,
          landmark_model: MISTRAL.model,
          landmark_provider: 'mistral',
          landmark_is_default: true,
        },
      }),
    )
    renderSection()

    const card = await screen.findByTestId(`model-card-${MISTRAL.model}`)
    expect(card).toHaveTextContent('Installationsvorgabe')
  })
})

describe('ModelChoiceSection: zwei Gruppen', () => {
  it('gibt jeder Tätigkeit ein eigenes Radio mit eigenem name', async () => {
    renderSection()

    const category = await screen.findByRole('radio', {
      name: `Kategorisierung: Mistral, ${MISTRAL.model}`,
    })
    const landmark = screen.getByRole('radio', {
      name: `Sehenswürdigkeits-Erkennung: Mistral, ${MISTRAL.model}`,
    })
    expect(category).toBeChecked()
    expect(landmark).toBeChecked()
    expect(category.getAttribute('name')).not.toBe(landmark.getAttribute('name'))
  })

  it('bietet Eye nur in der Kategorisierungsgruppe an', async () => {
    renderSection()

    const eyeCard = await screen.findByTestId('model-card-eye')
    expect(within(eyeCard).getByRole('radio', { name: 'Kategorisierung: Eye' })).toBeInTheDocument()
    expect(within(eyeCard).queryAllByRole('radio')).toHaveLength(1)
    expect(eyeCard).toHaveTextContent('kostenfrei')
    expect(eyeCard).toHaveTextContent(/desert ant labs/i)
    expect(eyeCard).toHaveTextContent(/lässt sich nicht abschalten/i)
    expect(eyeCard).toHaveTextContent(/solange #621 nicht umgesetzt ist/i)
    expect(eyeCard).toHaveTextContent(
      'Nicht möglich — Eye liefert keine Namen von Sehenswürdigkeiten.',
    )
  })
})

describe('ModelChoiceSection: nicht wählbar', () => {
  it('sperrt die Marke mit Grund, lässt aber die Fakten lesbar', async () => {
    renderSection()

    const card = await screen.findByTestId(`model-card-${ANTHROPIC.model}`)
    const radio = within(card).getByRole('radio', {
      name: `Kategorisierung: Anthropic, ${ANTHROPIC.model}`,
    })
    expect(radio).toBeDisabled()
    expect(card).toHaveTextContent(
      'Nicht wählbar — für Anthropic ist kein API-Schlüssel hinterlegt.',
    )
    expect(card).toHaveTextContent('0,0052 USD je Bild')
  })

  it('sperrt Eye, wenn die Installation ihn abgeschaltet hat', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({ eye: { available: false, unavailable_reasons: ['eye_disabled'] } }),
    )
    renderSection()

    const card = await screen.findByTestId('model-card-eye')
    const radio = within(card).getByRole('radio', { name: 'Kategorisierung: Eye' })
    expect(radio).toBeDisabled()
    expect(card).toHaveTextContent('Nicht wählbar — Eye ist in dieser Installation abgeschaltet.')
  })

  it('markiert eine gesperrte, aber gespeicherte Wahl als "So eingestellt"', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'cloud',
          category_model: MISTRAL.model,
          category_provider: 'mistral',
          category_is_default: false,
          landmark_model: ANTHROPIC.model,
          landmark_provider: 'anthropic',
          landmark_is_default: false,
        },
      }),
    )
    renderSection()

    const card = await screen.findByTestId(`model-card-${ANTHROPIC.model}`)
    const radio = within(card).getByRole('radio', {
      name: `Sehenswürdigkeits-Erkennung: Anthropic, ${ANTHROPIC.model}`,
    })
    expect(radio).toBeChecked()
    expect(radio).toBeDisabled()
    expect(card).toHaveTextContent('So eingestellt, derzeit nicht wählbar.')
  })

  it('nennt ein entferntes Modell über dem Raster', async () => {
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'cloud',
          category_model: 'ein-entferntes-modell',
          category_provider: null,
          category_is_default: false,
          landmark_model: MISTRAL.model,
          landmark_provider: 'mistral',
          landmark_is_default: false,
        },
      }),
    )
    renderSection()

    expect(await screen.findByTestId('model-choice-removed-category')).toHaveTextContent(
      'Kategorisierung: ein-entferntes-modell — dieses Modell ist nicht mehr wählbar. Wähle ein anderes.',
    )
    // Der Grund steht NEBEN dem gesperrten Knopf, nicht nur über dem Raster: ein ausgegrauter
    // Knopf ohne Begründung lässt raten, was fehlt (Muster 4 der Teststrategie).
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()
    expect(
      screen.getByText(
        'Ein Modell ist nicht mehr wählbar — wähle für die betroffene Tätigkeit ein anderes.',
      ),
    ).toBeInTheDocument()
  })

  it('bietet nirgends ein freies Textfeld für ein Modell an (S1)', async () => {
    // Der Katalog ist die GESCHLOSSENE Eingabe: eine getippte Modell-ID könnte einen Namen
    // behaupten, den diese Installation nicht wählen darf.
    renderSection()

    await screen.findByTestId('model-choice-section')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})

describe('ModelChoiceSection: Zustände', () => {
  it('zeigt beim Laden zwei Platzhalter statt einer halb bedienbaren Ansicht', () => {
    vi.mocked(projectsApi.getModelChoice).mockReturnValue(new Promise(() => {}))
    renderSection()

    expect(screen.getByRole('status', { name: 'Modellwahl wird geladen' })).toBeInTheDocument()
    expect(screen.queryAllByRole('radio')).toHaveLength(0)
  })

  it('zeigt den Servertext als Fehler mit Wiederholung', async () => {
    vi.mocked(projectsApi.getModelChoice).mockRejectedValue(
      new ApiError(500, 'Datenbank nicht erreichbar.'),
    )
    renderSection()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Datenbank nicht erreichbar.')
    expect(within(alert).getByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
  })
})

describe('ModelChoiceSection: Speichern', () => {
  it('schickt die Installationsvorgabe als null, nicht als aufgeloestes Modell', async () => {
    // Der geseedete Bestand steht auf `NULL` (Installationsvorgabe). Wer nur die Methode umstellt,
    // darf die Modelle nicht festschreiben: sonst verlore das Projekt die Eigenschaft, der
    // Vorgabe zu folgen, und in einer Installation ohne Schluessel scheiterte der PUT mit 422.
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'cloud',
          category_model: MISTRAL.model,
          category_provider: 'mistral',
          category_is_default: true,
          landmark_model: ANTHROPIC.model,
          landmark_provider: 'anthropic',
          landmark_is_default: true,
        },
      }),
    )
    vi.mocked(projectsApi.putModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'eye',
          category_model: null,
          category_provider: null,
          category_is_default: false,
          landmark_model: ANTHROPIC.model,
          landmark_provider: 'anthropic',
          landmark_is_default: true,
        },
      }),
    )
    const user = userEvent.setup()
    renderSection()

    await user.click(await screen.findByRole('radio', { name: 'Kategorisierung: Eye' }))
    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() =>
      expect(projectsApi.putModelChoice).toHaveBeenCalledWith(1, {
        category_method: 'eye',
        category_model: null,
        landmark_model: null,
      }),
    )
  })


  it('schreibt alle drei Spalten in EINEM PUT und meldet den Erfolg', async () => {
    vi.mocked(projectsApi.putModelChoice).mockResolvedValue(
      choice({
        current: {
          category_method: 'eye',
          category_model: null,
          category_provider: null,
          category_is_default: false,
          landmark_model: MISTRAL.model,
          landmark_provider: 'mistral',
          landmark_is_default: false,
        },
      }),
    )
    const user = userEvent.setup()
    renderSection()

    await user.click(await screen.findByRole('radio', { name: 'Kategorisierung: Eye' }))
    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() =>
      expect(projectsApi.putModelChoice).toHaveBeenCalledWith(1, {
        category_method: 'eye',
        category_model: null,
        landmark_model: MISTRAL.model,
      }),
    )
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Gespeichert — gilt für künftige Läufe.',
    )
  })

  it('lässt den Knopf gesperrt, solange nichts geändert ist', async () => {
    renderSection()

    expect(await screen.findByRole('button', { name: 'Speichern' })).toBeDisabled()
    expect(screen.getByText('Keine Änderung offen.')).toBeInTheDocument()
  })

  it('meldet einen Fehlschlag mit "nichts geändert" und setzt die Marken zurück', async () => {
    vi.mocked(projectsApi.putModelChoice).mockRejectedValue(
      new ApiError(500, 'Speichern fehlgeschlagen.'),
    )
    const user = userEvent.setup()
    renderSection()

    await user.click(await screen.findByRole('radio', { name: 'Kategorisierung: Eye' }))
    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Speichern fehlgeschlagen.')
    expect(alert).toHaveTextContent('Es wurde nichts geändert; die bisherige Wahl gilt weiter.')
    expect(within(alert).getByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
    // Die Marke springt auf die Serverantwort zurück.
    expect(
      screen.getByRole('radio', { name: `Kategorisierung: Mistral, ${MISTRAL.model}` }),
    ).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Kategorisierung: Eye' })).not.toBeChecked()
  })

  it('ergänzt beim 409 den Satz zum laufenden Lauf und bietet keine Wiederholung', async () => {
    vi.mocked(projectsApi.putModelChoice).mockRejectedValue(
      new ApiError(409, 'Für dieses Projekt läuft gerade eine Klassifizierung.'),
    )
    const user = userEvent.setup()
    renderSection()

    await user.click(await screen.findByRole('radio', { name: 'Kategorisierung: Eye' }))
    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Die Wahl lässt sich ändern, sobald der Lauf beendet ist.')
    expect(within(alert).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
  })
})
