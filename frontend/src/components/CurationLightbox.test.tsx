import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as motifsApi from '../api/motifs'
import * as photosApi from '../api/photos'
import type { PhotoOut } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { CurationLightbox } from './CurationLightbox'

vi.mock('../api/photos')
vi.mock('../api/motifs')

/*
 * specs/features/0531-kuratierung-grossansicht.md - die Grossansicht als Konsument von
 * `useModalDialog`. Fokusfalle, Scroll-Sperre und die Absprache zwischen Esc und `cancel` gehoeren
 * dem Grundelement und sind in `ui/dialog.test.tsx` belegt; hier stehen die ABWEICHUNGEN dieses
 * Konsumenten - vor allem die vollstaendige Aufteilung der Klickziele in schliessend und nicht
 * schliessend.
 */

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 42,
    relative_path: '2024/07/IMG_0042.jpg',
    taken_at: '2024-07-20T10:00:00',
    taken_at_original: '2024-07-20T09:00:00',
    time_offset_minutes: 60,
    camera: { id: 1, label: 'Pixel 8' },
    aspect_ratio: 1.5,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [
      {
        criterion_key: 'schaerfe',
        display_name: 'Schärfe',
        value: 0.8,
        source: 'local_heuristic',
        has_presence_threshold: false,
      },
    ],
    fine_labels: [
      {
        canonical_key: 'leuchtturm',
        display_name: 'Leuchtturm',
        raw_label: 'lighthouse',
        provider: 'anthropic',
      },
    ],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    event: {
      id: 3,
      position: 1,
      started_at: '2024-07-20T09:00:00',
      ended_at: '2024-07-20T12:00:00',
      place: null,
      place_name: 'Kap Arkona',
    },
    motif_assessment: {
      source: 'cloud',
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2024-07-21T09:00:00',
    },
    motifs: [],
    album_suitability: null,
    ...overrides,
  }
}

function renderLightbox(overrides: Partial<PhotoOut> = {}) {
  const onClose = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <QueryClientProvider client={client}>
      <CurationLightbox photo={photo(overrides)} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { ...view, onClose }
}

function dialog(): HTMLElement {
  return screen.getByRole('dialog')
}

function stage(): HTMLElement {
  return screen.getByTestId('lightbox-stage')
}

function buttonNames(): string[] {
  return within(dialog())
    .getAllByRole('button')
    .map((button) => button.textContent ?? '')
}

/** Ein Klick samt vorausgehendem `pointerdown` auf demselben Ziel - wie im Browser. */
function clickOn(element: Element): void {
  fireEvent.pointerDown(element)
  fireEvent.click(element)
}

describe('CurationLightbox', () => {
  beforeEach(() => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:display')
    vi.mocked(motifsApi.listMotifs).mockReset()
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
    vi.stubGlobal('URL', { ...URL, revokeObjectURL: vi.fn() })
  })

  it('shows exactly the clicked photo: base name as dialog name, full path as alt and footer', async () => {
    renderLightbox()

    expect(screen.getByRole('dialog', { name: 'IMG_0042.jpg' })).toHaveAttribute(
      'aria-modal',
      'true',
    )
    expect(await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })).toHaveAttribute(
      'src',
      'blob:display',
    )
    expect(screen.getByTestId('lightbox-footer')).toHaveTextContent('2024/07/IMG_0042.jpg')
    expect(screen.getByTestId('lightbox-place')).toHaveTextContent('Kap Arkona')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledTimes(1)
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(42, 'display')
  })

  it('puts the first focus on "Schließen"', () => {
    renderLightbox()

    expect(screen.getByRole('button', { name: 'Schließen' })).toHaveFocus()
  })

  it('offers exactly "Schließen" and "Details" and no link', async () => {
    renderLightbox()

    await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })
    expect(buttonNames()).toEqual(['Schließen', 'Details'])
    expect(screen.queryAllByRole('link')).toEqual([])
  })

  it('shows the motif row without any further action', async () => {
    renderLightbox()

    const row = await within(dialog()).findByRole('list', { name: 'Motive' })
    expect(within(row).getAllByRole('listitem')).toHaveLength(8)
  })

  it.each(['ArrowRight', 'ArrowLeft', 'PageDown', 'PageUp', 'Home', 'End'])(
    'does not switch to another photo on %s',
    async (key) => {
      const { onClose } = renderLightbox()
      await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })

      fireEvent.keyDown(screen.getByRole('button', { name: 'Schließen' }), { key })

      expect(screen.getByRole('dialog', { name: 'IMG_0042.jpg' })).toBeInTheDocument()
      expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledTimes(1)
      expect(onClose).not.toHaveBeenCalled()
    },
  )

  describe('Aufteilung der Klickziele', () => {
    it('closes on a click on the dialog element itself (backdrop)', () => {
      const { onClose } = renderLightbox()

      clickOn(dialog())

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('closes on a click on the free stage next to the image', () => {
      const { onClose } = renderLightbox()

      clickOn(stage())

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it.each([
      ['das Bild', () => screen.getByRole('img', { name: '2024/07/IMG_0042.jpg' })],
      ['den Bildkasten', () => screen.getByTestId('lightbox-image-box')],
      ['die Kopfzeile', () => screen.getByTestId('lightbox-header')],
      ['den Dateinamen', () => screen.getByRole('heading', { name: 'IMG_0042.jpg' })],
      ['die Fusszeile', () => screen.getByTestId('lightbox-footer')],
      ['den Innenabstand des Panels', () => screen.getByTestId('lightbox-panel')],
      ['den Detailbereich', () => screen.getByRole('region', { name: 'Bilddetails' })],
    ])('does not close on a click on %s', async (_, target) => {
      const { onClose } = renderLightbox()
      await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })
      fireEvent.click(screen.getByRole('button', { name: 'Details' }))

      clickOn(target())

      expect(onClose).not.toHaveBeenCalled()
    })

    it('does not close when a drag starts on the header and ends on the stage', () => {
      const { onClose } = renderLightbox()

      fireEvent.pointerDown(screen.getByRole('heading', { name: 'IMG_0042.jpg' }))
      fireEvent.click(stage())

      expect(onClose).not.toHaveBeenCalled()
    })

    it('closes via the "Schließen" button', () => {
      const { onClose } = renderLightbox()

      fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  it('closes on Escape also with the details open', () => {
    const { onClose } = renderLightbox()
    fireEvent.click(screen.getByRole('button', { name: 'Details' }))

    fireEvent.keyDown(screen.getByRole('region', { name: 'Bilddetails' }), { key: 'Escape' })

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('cycles Tab through Schließen, the open detail region and Details', async () => {
    const user = userEvent.setup()
    renderLightbox()
    await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })
    const close = screen.getByRole('button', { name: 'Schließen' })
    const details = screen.getByRole('button', { name: 'Details' })

    await user.tab()
    expect(details).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()

    await user.click(details)
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('region', { name: 'Bilddetails' })).toHaveFocus()
    await user.tab()
    expect(details).toHaveFocus()
  })

  describe('Bilddetails', () => {
    it('starts collapsed and controls an existing, hidden region', () => {
      renderLightbox()

      const toggle = screen.getByRole('button', { name: 'Details' })
      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      const controlled = document.getElementById(toggle.getAttribute('aria-controls') ?? '')
      expect(controlled).not.toBeNull()
      expect(controlled).not.toBeVisible()
    })

    it('shows criteria, fine labels and capture facts when expanded, and hides them again', () => {
      renderLightbox()
      const toggle = screen.getByRole('button', { name: 'Details' })

      fireEvent.click(toggle)

      expect(toggle).toHaveAttribute('aria-expanded', 'true')
      const region = screen.getByRole('region', { name: 'Bilddetails' })
      expect(within(region).getByRole('group', { name: 'Qualität' })).toHaveTextContent('Schärfe')
      expect(within(region).getByRole('heading', { level: 3, name: 'Feinlabels' })).toBeVisible()
      expect(within(region).getByText('Leuchtturm')).toBeInTheDocument()
      expect(within(region).getByRole('heading', { level: 3, name: 'Aufnahme' })).toBeVisible()
      expect(within(region).getByTestId('taken-at-section')).toHaveTextContent('Pixel 8')
      // Der Ort steht in der Fusszeile, nicht im Detailblock.
      expect(within(region).queryByText('Kap Arkona')).not.toBeInTheDocument()

      fireEvent.click(toggle)

      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByRole('region', { name: 'Bilddetails' })).not.toBeInTheDocument()
    })

    it('adds the rank in the event to the image content, and leaves it out without one', () => {
      const { unmount } = renderLightbox({
        ranking: {
          event_id: 3,
          rank_score: 0.7,
          rank_position: 2,
          proposed: true,
          partition_size: 9,
          curation_position: 2,
        },
      })
      fireEvent.click(screen.getByRole('button', { name: 'Details' }))
      expect(screen.getByRole('group', { name: 'Bildinhalt' })).toHaveTextContent(
        'Rang im Ereignis2 von 9',
      )
      unmount()

      renderLightbox({ ranking: null })
      fireEvent.click(screen.getByRole('button', { name: 'Details' }))
      expect(screen.queryByText('Rang im Ereignis')).not.toBeInTheDocument()
    })

    it('leaves out the fine-label heading when there are none', () => {
      renderLightbox({ fine_labels: [] })

      fireEvent.click(screen.getByRole('button', { name: 'Details' }))

      const region = screen.getByRole('region', { name: 'Bilddetails' })
      expect(within(region).queryByRole('heading', { name: 'Feinlabels' })).not.toBeInTheDocument()
    })
  })

  describe('Laden und Fehler', () => {
    it('shows header and footer at once and a named loading state on the image box', () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReturnValue(new Promise(() => {}))

      renderLightbox()

      expect(screen.getByRole('heading', { name: 'IMG_0042.jpg' })).toBeInTheDocument()
      expect(screen.getByTestId('lightbox-footer')).toHaveTextContent('Bild wird geladen …')
      expect(screen.getByTestId('lightbox-footer')).not.toHaveTextContent('2024/07/IMG_0042.jpg')
      expect(
        within(screen.getByTestId('lightbox-image-box')).getByRole('status', {
          name: '2024/07/IMG_0042.jpg wird geladen…',
        }),
      ).toBeInTheDocument()
    })

    it('shows an alert with the server detail; retry fetches again and focuses the stage', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl)
        .mockRejectedValueOnce(new ApiError(500, 'Speicher nicht erreichbar'))
        .mockResolvedValueOnce('blob:display')
      renderLightbox()

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Das Bild lässt sich nicht laden.')
      expect(alert).toHaveTextContent('Speicher nicht erreichbar')
      expect(screen.getByTestId('lightbox-footer')).toHaveTextContent(
        'Das Bild lässt sich nicht laden.',
      )
      expect(buttonNames()).toEqual(['Schließen', 'Erneut versuchen', 'Details'])
      fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

      expect(stage()).toHaveFocus()
      expect(await screen.findByRole('img', { name: '2024/07/IMG_0042.jpg' })).toBeInTheDocument()
      expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledTimes(2)
    })

    it('closes on Escape in the error state', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(new ApiError(500, 'x'))
      const { onClose } = renderLightbox()
      await screen.findByRole('alert')

      fireEvent.keyDown(dialog(), { key: 'Escape' })

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('shows "still processing" with a retry and without error semantics on a 404', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(new ApiError(404, 'fehlt'))
      renderLightbox()

      expect(await screen.findByText('Bild wird noch verarbeitet.')).toBeVisible()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(buttonNames()).toEqual(['Schließen', 'Erneut versuchen', 'Details'])
      expect(screen.queryAllByRole('link')).toEqual([])
    })
  })

  describe('Sicherheit', () => {
    /* S3: Der Pfad stammt aus dem WebDAV-Walk der OpenCloud - reiner Textknoten an allen drei
       Renderstellen. */
    it('renders a hostile relative_path only as text', async () => {
      const hostile = '<img src=x onerror="window.__pwned = true">'
      renderLightbox({ relative_path: `2024/${hostile}` })

      expect(await screen.findByRole('img', { name: `2024/${hostile}` })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: hostile })).toBeInTheDocument()
      expect(
        within(screen.getByTestId('lightbox-footer')).getByText(`2024/${hostile}`),
      ).toBeInTheDocument()
      expect(document.querySelector('img[src="x"]')).toBeNull()
      expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
    })

    /* Der Ortsname vereint Modellantwort und Ortsdatensatz Dritter (`eventPlaceName`) - an dieser
       Renderstelle ebenso reiner Textknoten wie auf der Detailseite. */
    const HOSTILE = '<img src=x onerror="window.__pwned = true">'
    it.each([
      ['place_name', { place: null, place_name: HOSTILE }],
      [
        'landmark_name',
        {
          place: { kind: 'landmark' as const, landmark_name: HOSTILE, lat: null, lon: null },
          place_name: null,
        },
      ],
    ])('renders a hostile place name from %s only as text', (_, place) => {
      renderLightbox({
        event: {
          id: 3,
          position: 1,
          started_at: '2024-07-20T09:00:00',
          ended_at: '2024-07-20T12:00:00',
          ...place,
        },
      })

      expect(screen.getByTestId('lightbox-place')).toHaveTextContent(HOSTILE)
      expect(document.querySelector('img[src="x"]')).toBeNull()
      expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
    })

    /* S4: Das Seitenverhaeltnis geht nur als gepruefte Zahl in den Stil - die Pruefung selbst
       steht in `utils/imageFit.test.ts`; hier nur, dass der Bildkasten sie benutzt. */
    it('fits the image box for a numeric aspect ratio', () => {
      renderLightbox({ aspect_ratio: 1.5 })

      expect(screen.getByTestId('lightbox-image-box').style.aspectRatio).not.toBe('')
    })

    it('falls back without any style for a hostile aspect ratio', () => {
      renderLightbox({ aspect_ratio: 'url(https://x.example/a);color:red' as unknown as number })

      expect(screen.getByTestId('lightbox-image-box')).not.toHaveAttribute('style')
    })
  })
})
