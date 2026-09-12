import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as camerasApi from '../api/cameras'
import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import type { PhotoOut, ProjectCameraOut } from '../api/types'
import { applyOffsetToIsoTime } from '../utils/timeOffset'
import { CameraTimeOffsetDialog } from './CameraTimeOffsetDialog'

vi.mock('../api/cameras')
vi.mock('../api/photos')
vi.mock('./PhotoImage', () => ({
  // Das echte PhotoImage laedt einen Blob ueber fetch - hier irrelevant und in jsdom nur Rauschen.
  PhotoImage: ({ photoId }: { photoId: number }) => <span data-photo-image={photoId} />,
}))

/*
 * specs/features/0426-zeitversatz-je-kamera.md, Teststrategie Abschnitt 9.
 *
 * Fokusfalle, Erstfokus und Scroll-Sperre werden hier NICHT wiederholt (sie liegen in
 * `ui/dialog.test.tsx`).
 */

const CAMERA: ProjectCameraOut = {
  id: 7,
  label: 'Canon EOS 5D',
  photo_count: 3,
  offset_minutes: 0,
}

const REFERENCE_CAMERA: ProjectCameraOut = {
  id: 9,
  label: 'Apple iPhone 15',
  photo_count: 5,
  offset_minutes: 0,
}

const RECORDED = '2026-08-12T14:32:00'

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 11,
    relative_path: 'a.jpg',
    taken_at: RECORDED,
    taken_at_original: RECORDED,
    time_offset_minutes: 0,
    camera: { id: CAMERA.id, label: CAMERA.label },
    ratings: [],
    suggestion: null,
    rankings: [],
    criterion_scores: [],
    fine_labels: [],
    remote_category: null,
    category_confidence: null,
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

function renderDialog(camera: ProjectCameraOut = CAMERA) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const onClose = vi.fn()

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  render(
    <CameraTimeOffsetDialog
      open
      onClose={onClose}
      projectId={3}
      camera={camera}
      cameras={[camera, REFERENCE_CAMERA]}
    />,
    { wrapper: Wrapper },
  )
  return { onClose }
}

async function fillFields(
  user: ReturnType<typeof userEvent.setup>,
  { days = '0', hours = '0', minutes = '0' }: { days?: string; hours?: string; minutes?: string },
) {
  for (const [label, value] of [
    ['Tage', days],
    ['Stunden', hours],
    ['Minuten', minutes],
  ] as const) {
    const field = screen.getByLabelText(label)
    await user.clear(field)
    if (value !== '') {
      await user.type(field, value)
    }
  }
}

describe('CameraTimeOffsetDialog', () => {
  beforeEach(() => {
    vi.mocked(camerasApi.setCameraTimeOffset).mockReset()
    vi.mocked(camerasApi.setCameraTimeOffset).mockResolvedValue(CAMERA)
    vi.mocked(camerasApi.getCameraTimeOffsetSuggestion).mockReset()
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo()], total: 1 })
  })

  it('nennt die Kamera im Titel', () => {
    renderDialog()

    expect(screen.getByRole('dialog')).toHaveAccessibleName(expect.stringContaining('Canon EOS 5D'))
  })

  // DAS Vorzeichen ist der Kern: eine Fehlbedienung hier verdoppelt den Fehler statt ihn zu
  // beheben. Geprueft wird der an die Mutation uebergebene WERT, je Richtung einmal.
  it('sendet einen NEGATIVEN Versatz, wenn die Kamerauhr vorging', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging vor/ }))
    await fillFields(user, { hours: '2' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(camerasApi.setCameraTimeOffset).toHaveBeenCalledWith(3, 7, -120)
    })
  })

  it('sendet einen POSITIVEN Versatz, wenn die Kamerauhr nachging', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging nach/ }))
    await fillFields(user, { hours: '2' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(camerasApi.setCameraTimeOffset).toHaveBeenCalledWith(3, 7, 120)
    })
  })

  it('rechnet Tage in den gesendeten Wert mit', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging nach/ }))
    await fillFields(user, { days: '1', hours: '1', minutes: '1' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(camerasApi.setCameraTimeOffset).toHaveBeenCalledWith(3, 7, 24 * 60 + 61)
    })
  })

  it('zeigt die Vorschau gegen die reine Funktion, nicht gegen einen abgeschriebenen String', async () => {
    // Gegen `applyOffsetToIsoTime` geprueft: ein abgeschriebener Erwartungsstring wuerde beim
    // naechsten Formatwechsel falsch-gruen oder falsch-rot, und die Vorschau ist die tragende
    // Massnahme gegen ein falsches Vorzeichen.
    const user = userEvent.setup()
    renderDialog()
    await waitFor(() => {
      expect(screen.getByText(/aufgezeichnet/)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('radio', { name: /ging vor/ }))
    await fillFields(user, { hours: '2' })

    const expected = applyOffsetToIsoTime(RECORDED, -120)
    expect(expected).not.toBeNull()
    const effective = new Date(expected as string).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    expect(screen.getByText(effective)).toBeInTheDocument()
  })

  it('sperrt das Speichern bei ungueltiger Eingabe und meldet es am Feld', async () => {
    const user = userEvent.setup()
    renderDialog()

    await fillFields(user, { hours: '24' })

    expect(screen.getByRole('button', { name: 'Versatz speichern' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent(/Stunden/)
    expect(screen.getByLabelText('Stunden')).toHaveAttribute('aria-invalid', 'true')
  })

  it('sperrt das Speichern bei einem leeren Feld', async () => {
    // Ein geleertes Feld ist eine Zwischenstufe des Tippens - es darf nicht still als `0` gelten.
    const user = userEvent.setup()
    renderDialog()

    await fillFields(user, { minutes: '' })

    expect(screen.getByRole('button', { name: 'Versatz speichern' })).toBeDisabled()
  })

  it('schreibt nichts, solange die Eingabe ungueltig ist', async () => {
    const user = userEvent.setup()
    renderDialog()

    await fillFields(user, { minutes: '60' })
    const save = screen.getByRole('button', { name: 'Versatz speichern' })
    await user.click(save).catch(() => undefined)

    expect(camerasApi.setCameraTimeOffset).not.toHaveBeenCalled()
  })

  it('schliesst den Dialog nach dem Speichern', async () => {
    const user = userEvent.setup()
    const { onClose } = renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging nach/ }))
    await fillFields(user, { hours: '1' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('zeigt einen 409 als Klartext und laesst den Dialog offen', async () => {
    vi.mocked(camerasApi.setCameraTimeOffset).mockRejectedValue(
      new ApiError(409, 'Fuer dieses Projekt laeuft gerade ein Vorgang.'),
    )
    const user = userEvent.setup()
    const { onClose } = renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging nach/ }))
    await fillFields(user, { hours: '1' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(screen.getByText(/Vorgang dieses Projekts läuft gerade/)).toBeInTheDocument()
    })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('zeigt einen 422 mit dem ausdruecklichen Hinweis, dass nichts gespeichert wurde', async () => {
    vi.mocked(camerasApi.setCameraTimeOffset).mockRejectedValue(
      new ApiError(422, 'Ausserhalb des darstellbaren Bereichs.'),
    )
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('radio', { name: /ging nach/ }))
    await fillFields(user, { hours: '1' })
    await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

    await waitFor(() => {
      expect(screen.getByText(/nichts gespeichert/)).toBeInTheDocument()
    })
  })

  describe('Vorschlagsfluss', () => {
    beforeEach(() => {
      vi.mocked(camerasApi.getCameraTimeOffsetSuggestion).mockResolvedValue({
        camera_id: CAMERA.id,
        camera_label: CAMERA.label,
        offset_minutes: -120,
        photo_taken_at_original: RECORDED,
        reference_taken_at: '2026-08-12T12:32:00',
      })
    })

    async function computeSuggestion(user: ReturnType<typeof userEvent.setup>) {
      await user.selectOptions(screen.getByLabelText('Referenzkamera'), String(REFERENCE_CAMERA.id))
      const strips = await screen.findAllByRole('list')
      const [ownStrip, referenceStrip] = strips
      await user.click(ownStrip.querySelectorAll('button')[0] as HTMLElement)
      await user.click(referenceStrip.querySelectorAll('button')[0] as HTMLElement)
      await user.click(screen.getByRole('button', { name: 'Vorschlag ausrechnen' }))
      await waitFor(() => {
        expect(screen.getByText('Vorschlag')).toBeInTheDocument()
      })
    }

    it('sagt ausdruecklich, dass der Vorschlag noch nicht gilt', async () => {
      const user = userEvent.setup()
      renderDialog()

      await computeSuggestion(user)

      expect(screen.getByText(/gilt noch nicht/)).toBeInTheDocument()
    })

    it('schreibt beim Ausrechnen nichts', async () => {
      const user = userEvent.setup()
      renderDialog()

      await computeSuggestion(user)

      expect(camerasApi.setCameraTimeOffset).not.toHaveBeenCalled()
    })

    it('"Vorschlag uebernehmen" fuellt nur die Felder und schreibt nicht', async () => {
      const user = userEvent.setup()
      renderDialog()
      await computeSuggestion(user)

      await user.click(screen.getByRole('button', { name: 'Vorschlag übernehmen' }))

      // -120 Minuten = vorgehende Uhr, 0 Tage, 2 Stunden, 0 Minuten.
      expect(screen.getByRole('radio', { name: /ging vor/ })).toBeChecked()
      expect(screen.getByLabelText('Stunden')).toHaveValue(2)
      expect(camerasApi.setCameraTimeOffset).not.toHaveBeenCalled()
    })

    it('laesst die uebernommenen Felder von Hand aenderbar', async () => {
      const user = userEvent.setup()
      renderDialog()
      await computeSuggestion(user)
      await user.click(screen.getByRole('button', { name: 'Vorschlag übernehmen' }))

      await fillFields(user, { hours: '3' })
      await user.click(screen.getByRole('button', { name: 'Versatz speichern' }))

      await waitFor(() => {
        expect(camerasApi.setCameraTimeOffset).toHaveBeenCalledWith(3, 7, -180)
      })
    })

    it('bietet die eigene Kamera nicht als Referenz an', async () => {
      // Die Differenz zweier Fotos DERSELBEN Kamera ist keine Uhrenabweichung.
      renderDialog()

      const select = screen.getByLabelText('Referenzkamera')

      expect(select).toHaveTextContent(REFERENCE_CAMERA.label)
      expect(select).not.toHaveTextContent(CAMERA.label)
    })

    it('erklaert den fehlenden Vorschlag, wenn es keine zweite Kamera gibt', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      })
      render(
        <QueryClientProvider client={queryClient}>
          <CameraTimeOffsetDialog
            open
            onClose={vi.fn()}
            projectId={3}
            camera={CAMERA}
            cameras={[CAMERA]}
          />
        </QueryClientProvider>,
      )

      expect(screen.getByText(/braucht das Projekt eine zweite Kamera/)).toBeInTheDocument()
      expect(screen.queryByLabelText('Referenzkamera')).not.toBeInTheDocument()
    })
  })
})
