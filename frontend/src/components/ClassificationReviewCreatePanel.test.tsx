import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as reviewApi from '../api/classificationReviews'
import type { ClassificationReviewEstimateOut, ClassificationReviewOptionsOut } from '../api/types'
import { ClassificationReviewCreatePanel } from './ClassificationReviewCreatePanel'

vi.mock('../api/classificationReviews')

/*
 * Seite 1 der Pruefung (Spec 0616, UI/UX): das Anlegen-Panel. Geprueft werden die Aussagen, die
 * die Spec an dieses Panel bindet - keine Vorauswahl, Kostenvorschau erst nach zwei Seiten,
 * Pruefgraesse aus den Servergrenzen, Ausloeser erst mit beiden Seiten - sowie der Fehlerpfad.
 */

const OPTIONS: ClassificationReviewOptionsOut = {
  sample_size: { default: 30, min: 1, max: 200 },
  kinds: [
    { kind: 'cloud', available: true, unavailable_reasons: [] },
    { kind: 'eye', available: true, unavailable_reasons: [] },
    { kind: 'local', available: true, unavailable_reasons: [] },
  ],
  cloud_models: [
    { provider: 'anthropic', model: 'claude-sonnet-4-5', available: true, unavailable_reasons: [] },
    {
      provider: 'mistral',
      model: 'pixtral-large-latest',
      available: false,
      unavailable_reasons: ['no_api_key'],
    },
  ],
  eye_mappings: [
    {
      eye_model_revision: 'eye-4.2.3',
      eye_mapping_version: 'v1',
      available: true,
      unavailable_reasons: [],
    },
    {
      eye_model_revision: 'eye-4.2.3',
      eye_mapping_version: 'v2',
      available: true,
      unavailable_reasons: [],
    },
  ],
}

const ESTIMATE: ClassificationReviewEstimateOut = {
  photo_count: 412,
  a: {
    kind: 'cloud',
    provider: 'anthropic',
    model: 'claude-sonnet-4-5',
    photo_count: 412,
    price_per_image_usd: 0.003,
    estimated_cost_usd: 1.234,
  },
  b: {
    kind: 'local',
    provider: null,
    model: null,
    photo_count: 412,
    price_per_image_usd: 0,
    estimated_cost_usd: 0,
  },
}

function renderPanel(onCreated = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(<ClassificationReviewCreatePanel projectId={7} id="create" onCreated={onCreated} />, {
    wrapper,
  })
  return { onCreated }
}

async function side(name: 'Seite A' | 'Seite B') {
  return within(await screen.findByRole('group', { name }))
}

function startButton() {
  return screen.getByRole('button', { name: 'Prüfung starten' })
}

async function chooseCloudAAndLocalB() {
  const user = userEvent.setup()
  const a = await side('Seite A')
  await user.click(await a.findByRole('radio', { name: /Cloud · Anthropic/ }))
  await user.click((await side('Seite B')).getByRole('radio', { name: /Lokal/ }))
  return user
}

async function chooseLocalAAndEyeB() {
  const user = userEvent.setup()
  const a = await side('Seite A')
  await user.click(await a.findByRole('radio', { name: /Lokal/ }))
  await user.click((await side('Seite B')).getByRole('radio', { name: /Übersetzung v1/ }))
  return user
}

describe('ClassificationReviewCreatePanel', () => {
  beforeEach(() => {
    vi.mocked(reviewApi.getClassificationReviewOptions).mockReset()
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockReset()
    vi.mocked(reviewApi.createClassificationReview).mockReset()
    vi.mocked(reviewApi.getClassificationReviewOptions).mockResolvedValue(OPTIONS)
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockResolvedValue(ESTIMATE)
  })

  it('laesst beide Seiten ohne Vorauswahl', async () => {
    renderPanel()

    await (await side('Seite A')).findByRole('radio', { name: /Lokal/ })

    for (const radio of screen.getAllByRole('radio')) {
      expect(radio).not.toBeChecked()
    }
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('gliedert Cloud-Modelle nach Anbieter und nennt den Sperrgrund beim Anbieter', async () => {
    renderPanel()

    const a = await side('Seite A')
    await a.findByRole('radio', { name: /Cloud · Anthropic/ })

    expect(a.getByText('Anthropic')).toBeInTheDocument()
    expect(a.getByText('Mistral')).toBeInTheDocument()
    expect(
      a.getByText('Nicht wählbar — für Mistral kein API-Schlüssel hinterlegt.'),
    ).toBeInTheDocument()
    expect(a.queryByRole('radio', { name: /Mistral/ })).not.toBeInTheDocument()
    // Eye: eine Zeile je Fassung, beide Fassungen unterscheidbar.
    expect(a.getByRole('radio', { name: /Übersetzung v1/ })).toBeInTheDocument()
    expect(a.getByRole('radio', { name: /Übersetzung v2/ })).toBeInTheDocument()
  })

  it('zeigt die Kostenvorschau erst, wenn beide Seiten gewaehlt sind', async () => {
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockResolvedValue({
      photo_count: 412,
      a: ESTIMATE.b,
      b: { ...ESTIMATE.b, kind: 'eye' },
    })
    renderPanel()

    const a = await side('Seite A')
    await userEvent.setup().click(await a.findByRole('radio', { name: /Lokal/ }))

    expect(screen.queryByText('Kostenvorschau')).not.toBeInTheDocument()
    expect(reviewApi.getClassificationReviewEstimate).not.toHaveBeenCalled()

    await userEvent
      .setup()
      .click((await side('Seite B')).getByRole('radio', { name: /Übersetzung v1/ }))

    expect(await screen.findByText('Kostenvorschau')).toBeInTheDocument()
    expect(reviewApi.getClassificationReviewEstimate).toHaveBeenCalledTimes(1)
    expect(reviewApi.getClassificationReviewEstimate).toHaveBeenCalledWith(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', eye_mapping_version: 'v1' },
    })
    expect(screen.getByText('Seite A: kostenfrei')).toBeInTheDocument()
  })

  it('zeigt je Seite Betrag und Fotozahl sowie eine Gesamtzeile', async () => {
    renderPanel()

    await chooseCloudAAndLocalB()

    expect(await screen.findByText('Seite A: 1,23 USD für 412 Fotos')).toBeInTheDocument()
    expect(screen.getByText('Seite B: kostenfrei')).toBeInTheDocument()
    expect(screen.getByText('Gesamtsumme')).toBeInTheDocument()
  })

  it('nennt bei unbekanntem Preis den bestehenden Hinweis statt eines Betrags', async () => {
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockResolvedValue({
      photo_count: 412,
      a: { ...ESTIMATE.a, estimated_cost_usd: null, price_per_image_usd: null },
      b: ESTIMATE.b,
    })
    renderPanel()

    await chooseCloudAAndLocalB()

    expect(await screen.findByText('Seite A: kein Preis hinterlegt')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Für dieses Modell ist kein Preis hinterlegt — die Kosten lassen sich nicht schätzen.',
      ),
    ).toBeInTheDocument()
  })

  it('belegt die Pruefgraesse aus den Servergrenzen vor und nennt den Zufallshinweis', async () => {
    renderPanel()

    const field = await screen.findByLabelText('Prüfgröße je Zweck')

    expect(field).toHaveValue(30)
    expect(field).toHaveAttribute('min', '1')
    expect(field).toHaveAttribute('max', '200')
    expect(screen.getByText('Weichen mehr Fotos ab, wird zufällig ausgewählt.')).toBeInTheDocument()
  })

  it('sperrt den Ausloeser ohne beide Seiten und waehrend des Sendens', async () => {
    vi.mocked(reviewApi.createClassificationReview).mockReturnValue(new Promise(() => {}))
    const { onCreated } = renderPanel()

    await (await side('Seite A')).findByRole('radio', { name: /Lokal/ })

    expect(startButton()).toBeDisabled()
    expect(
      screen.getByText('Wähle für beide Seiten ein Verfahren — ohne Wahl startet keine Prüfung.'),
    ).toBeInTheDocument()

    const user = await chooseLocalAAndEyeB()
    await waitFor(() => expect(startButton()).toBeEnabled())

    await user.click(startButton())

    await waitFor(() => expect(startButton()).toBeDisabled())
    expect(reviewApi.createClassificationReview).toHaveBeenCalledWith(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', eye_mapping_version: 'v1' },
      sample_size: 30,
    })
    expect(onCreated).not.toHaveBeenCalled()
  })

  it('meldet die Servermeldung eines abgelehnten Anlegens als Alert', async () => {
    vi.mocked(reviewApi.createClassificationReview).mockRejectedValue(
      new ApiError(409, 'Es läuft bereits eine Pruefung. Warte, bis sie beendet ist.'),
    )
    renderPanel()

    const user = await chooseLocalAAndEyeB()
    await waitFor(() => expect(startButton()).toBeEnabled())
    await user.click(startButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Es läuft bereits eine Pruefung. Warte, bis sie beendet ist.')
  })

  it('meldet eine erfolgreich angelegte Pruefung nach oben', async () => {
    vi.mocked(reviewApi.createClassificationReview).mockResolvedValue({ id: 12, status: 'running' })
    const { onCreated } = renderPanel()

    const user = await chooseLocalAAndEyeB()
    await waitFor(() => expect(startButton()).toBeEnabled())
    await user.click(startButton())

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ id: 12, status: 'running' }))
  })
})
