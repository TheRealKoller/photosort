/*
 * Foto-Detailseite - Teil: Motive und Eye-Auswertung (Spec 0651; gemeinsamer Unterbau in src/test/photoDetailPage.tsx).
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as photosApi from '../api/photos'
import { MOTIF_KEYS } from '../test/motifSetFixture'
import {
  ALBUM_SUITABILITY_NOT_RATED_TEXT,
  ALBUM_SUITABILITY_ORIGIN_LABEL,
  formatAlbumSuitabilityLevel,
} from '../utils/albumSuitability'
import { formatDateTime } from '../utils/formatStats'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  photo,
  criterionScore,
  suggestion,
  motifStrengths,
  renderPage,
  motifSection,
  CLOUD_ASSESSMENT,
  resetPhotoDetailMocks,
  resetPersonsMock,
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
})

describe('PhotoDetailPage', () => {
  beforeEach(() => {
    resetPhotoDetailMocks()
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  // specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt "Einzelbildansicht": die
  // permanente Sektion "Motive", nach dem Vorschlagskasten und VOR der Trennlinie. Seit PR 3 ist
  // sie der EINZIGE Bedienblock der Bewertungsdetails.
  // specs/features/0609-eye-dritte-wahl.md: die Herkunft von Albumtauglichkeit und Feinlabels
  // steht zwischen Urteil und Motivbereich - an der Stelle, deren Angaben sie erklaert.
  describe('Die Eye-Auswertung (Spec 0609)', () => {
    const EYE_ASSESSMENT_LOCAL = {
      source: 'eye' as const,
      provider: null,
      excluded_document: false,
      computed_at: '2026-09-12T10:00:00Z',
    }
    const EYE_RESULT = {
      album_level: 3,
      model_revision: 'v1.0.0',
      mapping_version: 'eye-4.2.3/v2',
      computed_at: '2026-09-12T10:00:00Z',
      fine_labels: ['urlaub', 'strand'],
    }

    it('nennt Herkunft, Modellrevision und Zeitpunkt zwischen Urteil und Motiven', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: EYE_ASSESSMENT_LOCAL,
            motifs: motifStrengths(),
            // Die zaehlende Stufe kommt aus Eye - nur dann nennt das Band auch die
            // Albumtauglichkeit (0621).
            album_suitability: { level: 3, reason: null, source: 'eye' },
            eye_result: EYE_RESULT,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      const band = await screen.findByTestId('eye-band')
      expect(band).toHaveTextContent(
        /Albumtauglichkeit und Feinlabels stammen aus der Eye-Auswertung/,
      )
      expect(band).toHaveTextContent('v1.0.0')
      const link = within(band).getByRole('link', { name: /desert ant labs/i })
      expect(link).toHaveAttribute('href', 'https://desertant.com')

      // Die Reihenfolge ist die Aussage: nach dem Urteil, vor den Motiven.
      const verdict = screen.getByTestId('verdict-section')
      expect(verdict.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(
        band.compareDocumentPosition(screen.getByTestId('motifs-section')) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy()
    })

    // Die Fassung der Uebersetzung steht als Rohwert zwischen Modellrevision und Zeitpunkt - fuer
    // jede Fassung, die die Zeile traegt.
    it.each(['eye-4.2.3/v2', 'eye-4.2.3/v1'])(
      'nennt Modellrevision, Übersetzung %s und Zeitpunkt in dieser Reihenfolge',
      async (mappingVersion) => {
        vi.mocked(photosApi.listPhotos).mockResolvedValue({
          items: [
            photo({
              id: 1,
              motif_assessment: EYE_ASSESSMENT_LOCAL,
              motifs: motifStrengths(),
              eye_result: { ...EYE_RESULT, mapping_version: mappingVersion },
            }),
          ],
          total: 1,
        })

        renderPage('/projects/1/photos/1')

        const band = await screen.findByTestId('eye-band')
        const text = band.textContent ?? ''
        const revision = text.indexOf('Modellrevision v1.0.0,')
        const mapping = text.indexOf(`Übersetzung ${mappingVersion},`)
        const timestamp = text.indexOf(formatDateTime(EYE_RESULT.computed_at))
        expect(revision).toBeGreaterThanOrEqual(0)
        expect(mapping).toBeGreaterThan(revision)
        expect(timestamp).toBeGreaterThan(mapping)
      },
    )

    it('zeigt kein Band ohne Eye-Ergebnis', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: CLOUD_ASSESSMENT, motifs: motifStrengths() })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByTestId('verdict-section')

      // Cloud-Kopfzeile: kein Eye-Band, keine Eye-Namensnennung im Urteilsblock.
      expect(screen.queryByTestId('eye-band')).not.toBeInTheDocument()
    })

    it('zeigt im Urteil Eyes Stufe und Feinlabels statt der leeren Cloud-Werte', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: EYE_ASSESSMENT_LOCAL,
            motifs: motifStrengths(),
            // Die Stufe reist seit 0621 mit ihrer Herkunft in `album_suitability`; die
            // Eye-Kopfzeile traegt nur noch die Feinlabels.
            album_suitability: { level: 4, reason: null, source: 'eye' },
            fine_labels: [],
            eye_result: { ...EYE_RESULT, album_level: 4, fine_labels: ['beach', 'sunset'] },
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      const verdict = await screen.findByTestId('photo-verdict')
      expect(within(verdict).getByText(formatAlbumSuitabilityLevel(4))).toBeInTheDocument()
      expect(within(verdict).queryByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeNull()
      expect(verdict.querySelector('[data-album-suitability-reason]')).toBeNull()
      expect(within(verdict).getByText(ALBUM_SUITABILITY_ORIGIN_LABEL)).toBeInTheDocument()
      const labels = within(verdict).getByRole('list', { name: 'Feinlabels' })
      expect(within(labels).getByText('beach')).toBeInTheDocument()
      expect(within(labels).getByText('sunset')).toBeInTheDocument()

      // Bandtext: die Stufe zaehlt aus Eye, also erklaert das Band beide Angaben.
      const band = screen.getByTestId('eye-band')
      expect(band).toHaveTextContent(
        /Albumtauglichkeit und Feinlabels stammen aus der Eye-Auswertung/,
      )
    })

    it('nennt ohne zaehlende Eye-Stufe nur die Feinlabels als Eye-Auswertung', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: EYE_ASSESSMENT_LOCAL,
            motifs: motifStrengths(),
            // Eye lief, aber diesem Foto fehlt die zaehlende Stufe (z. B. Eye-Lauf mit
            // gescheitertem Aufruf): kein Rueckfall auf die Eye-Kopfzeile.
            album_suitability: null,
            eye_result: EYE_RESULT,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      const verdict = await screen.findByTestId('photo-verdict')
      expect(within(verdict).getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
      expect(
        within(verdict).queryByText(formatAlbumSuitabilityLevel(EYE_RESULT.album_level)),
      ).toBeNull()

      const band = await screen.findByTestId('eye-band')
      expect(band).toHaveTextContent(/^Feinlabels stammen aus der Eye-Auswertung/)
      expect(band).not.toHaveTextContent(/Albumtauglichkeit und Feinlabels stammen/)
    })

    it('zeigt ohne Eye-Ergebnis weiter die Cloud-Werte im Urteil', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths(),
            album_suitability: { level: 2, reason: 'Unscharf.', source: 'cloud' },
            fine_labels: [
              {
                canonical_key: 'urlaub',
                display_name: 'Urlaub',
                raw_label: 'Urlaub',
                provider: 'anthropic',
              },
            ],
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      const verdict = await screen.findByTestId('photo-verdict')
      expect(within(verdict).getByText(formatAlbumSuitabilityLevel(2))).toBeInTheDocument()
      expect(within(verdict).getByText('Unscharf.')).toBeInTheDocument()
      expect(within(verdict).getByText('Urlaub')).toBeInTheDocument()
    })
  })

  describe('Sektion "Motive"', () => {
    it('zeigt die Sektion permanent, auch ohne Kopfzeile', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(motifSection()).getByRole('heading', { name: 'Motive' })).toBeInTheDocument()
    })

    it('zeigt den Satz statt der Reihe, solange das Foto keinen Lauf gesehen hat', async () => {
      // Die KARDINALITAET Null, nicht eine Textsuche: der Satz kann ueber acht leeren Symbolen
      // stehen.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: null, motifs: [] })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(motifSection().querySelectorAll('[data-motif-key]')).toHaveLength(0)
      expect(within(motifSection()).getByText(/Noch nicht klassifiziert/)).toBeInTheDocument()
    })

    it('zeigt die acht Symbole in Registry-Reihenfolge, sobald eine Kopfzeile vorliegt', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: CLOUD_ASSESSMENT, motifs: motifStrengths() })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const keys = [...motifSection().querySelectorAll('[data-motif-key]')].map((node) =>
        node.getAttribute('data-motif-key'),
      )
      expect(keys).toEqual(MOTIF_KEYS)
    })

    it('steht nach dem Vorschlagskasten und vor der Trennlinie', async () => {
      // Letzter Bedienblock vor dem Informationsteil - damit Bewertungsleiste und Zurueck/Weiter
      // ohne Scrollen erreichbar bleiben.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            suggestion: suggestion(),
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths(),
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const suggestionBox = screen.getByText(/Automatischer Vorschlag/)
      const takenAt = screen.getByTestId('taken-at-section')
      const section = motifSection()
      expect(suggestionBox.compareDocumentPosition(section)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
      expect(section.compareDocumentPosition(takenAt)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    })

    it('ist bedienbar: eine Korrektur geht an den Endpunkt', async () => {
      const user = userEvent.setup()
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: CLOUD_ASSESSMENT, motifs: motifStrengths() })],
        total: 1,
      })
      vi.mocked(photosApi.setMotifCorrection).mockResolvedValue({
        photo_id: 1,
        motif_key: 'menschen',
        applies: false,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByAltText('a.jpg')
      // ERST aufklappen: die Korrekturschalter stehen seit Spec 0490 in der Detailzeile unter der
      // Symbolreihe, nicht mehr an acht Listenzeilen.
      await user.click(within(motifSection()).getByRole('button', { name: /^Menschen:/ }))
      await user.click(
        within(motifSection()).getByRole('button', { name: 'Trifft nicht zu: Menschen' }),
      )

      await waitFor(() =>
        expect(photosApi.setMotifCorrection).toHaveBeenCalledWith(1, 'menschen', false),
      )
    })

    it('nimmt eine bestehende Korrektur zurueck', async () => {
      const user = userEvent.setup()
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths({ menschen: { strength: 0, correction: false } }),
          }),
        ],
        total: 1,
      })
      vi.mocked(photosApi.deleteMotifCorrection).mockResolvedValue(undefined)

      renderPage('/projects/1/photos/1')
      await screen.findByAltText('a.jpg')
      await user.click(within(motifSection()).getByRole('button', { name: /^Menschen:/ }))
      await user.click(
        within(motifSection()).getByRole('button', { name: 'Zurücknehmen: Menschen' }),
      )

      await waitFor(() =>
        expect(photosApi.deleteMotifCorrection).toHaveBeenCalledWith(1, 'menschen'),
      )
    })

    it('bietet fuer ein ausgeschlossenes Foto keinen Korrekturschalter an', async () => {
      // DER KLICK AUF EIN SYMBOL STEHT VOR DER NEGATIVEN ASSERTION: seit Spec 0490 erscheinen die
      // Schalter erst nach dem Aufklappen, und ohne ihn bestuende die Zusage auch dann, wenn sie
      // dort sehr wohl erschienen.
      const user = userEvent.setup()
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
            motifs: motifStrengths(),
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(
        within(motifSection()).getByText(/Als Dokument oder Bildschirmabbildung erkannt/),
      ).toBeInTheDocument()

      await user.click(within(motifSection()).getByRole('button', { name: /^Menschen:/ }))

      expect(within(motifSection()).queryByRole('button', { name: /^Trifft/ })).toBeNull()
      expect(within(motifSection()).queryByRole('button', { name: /^Zurücknehmen:/ })).toBeNull()
    })

    it('ist der EINZIGE Bedienblock der Bewertungsdetails', async () => {
      const user = userEvent.setup()
      /* specs/features/0427-motive-mit-staerke.md, PR 3: mit den Kategorien sind die
       * Bedienelemente aus der Aufschlüsselung verschwunden. Als eigener Fall samt NEGATIVER
       * Assertion, weil ein stehengebliebener Bedienteil ohne Datengrundlage still leer bliebe
       * und damit von jedem Positivtest der Motivsektion unbemerkt. */
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths(),
            criterion_scores: [
              criterionScore({ criterion_key: 'landschaft', has_presence_threshold: true }),
            ],
            ranking: {
              event_id: 1,
              rank_score: 0.8,
              rank_position: 1,
              proposed: true,
              partition_size: 3,
              curation_position: null,
            },
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(screen.queryByTestId('category-controls-section')).toBeNull()
      expect(motifSection()).toBeInTheDocument()

      await user.click(within(motifSection()).getByRole('button', { name: /^Menschen:/ }))

      // Die Korrekturschalter der aufgeklappten Detailzeile sind die einzigen Bedienelemente der
      // Bewertungsdetails, die einen Datenwert schreiben.
      expect(
        within(motifSection()).getAllByRole('button', { name: /^Trifft zu:/ }).length,
      ).toBeGreaterThan(0)
    })
  })
})
