/*
 * Foto-Detailseite - Teil: Bewertung, Cloud-Vision-Status, Reihenfolge, Aufnahmezeit - gemeinsamer Unterbau: src/test/photoDetailPage.tsx.
 */
import { screen, within } from '@testing-library/react'
import * as photosApi from '../api/photos'
import type { PhotoListOut, PhotoOut } from '../api/types'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  photo,
  criterionScore,
  suggestion,
  motifStrengths,
  cloudVisionStatusEntry,
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

  // Spec 0041 (Bewertungsdetails permanent in der Detailansicht), Akzeptanzkriterien 1-4, 12.
  describe('permanent Bewertungsdetails section', () => {
    it('shows criteria and the rank directly under the photo when the photo has criterion_scores', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore({ display_name: 'Schärfe', value: 0.734 })],
            ranking: {
              event_id: 1,
              rank_score: 0.8,
              rank_position: 2,
              proposed: true,
              partition_size: 5,
              curation_position: null,
            },
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Schärfe')).toBeInTheDocument()
      expect(screen.getByText('73%')).toBeInTheDocument()
      /* Spec 0497, AK5: Der Rang steht GENAU EINMAL, und zwar im Urteil - er ist keiner der
         fünfzehn Einzelwerte. Beide Stellen werden einzeln geprüft: Eine seitenweite Textsuche
         bestünde auch dann, wenn er zusätzlich im Raster stünde, und genau diese Dublette wäre
         der Fehler. Eine Mengenprüfung wie die AK4-Sondenliste sieht eine Doppelung
         grundsätzlich nicht - deshalb steht die Abwesenheitszusage hier. */
      expect(within(screen.getByTestId('verdict-section')).getByText('2 von 5')).toBeInTheDocument()
      expect(
        within(screen.getByTestId('criterion-score-grid')).queryByText(/von 5$/),
      ).not.toBeInTheDocument()
    })

    // specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md, Akzeptanzkriterium 1:
    // genau EIN Oberflaechennachweis, dass die beiden beschrifteten Bloecke in der permanenten
    // Sektion ankommen.
    it('shows both block headings in the permanent section', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [
              criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
              criterionScore({
                criterion_key: 'content_people',
                display_name: 'Menschen erkannt',
                has_presence_threshold: true,
              }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      const section = await screen.findByTestId('criterion-score-grid')
      /* Die Kopfzeilen tragen im Raster den Wortlaut des Entwurfs und damit einen anderen als
         im Popover - das Raster ist eine eigene Darstellung, keine Variante davon. Die geprueften
         Verhaltensweise ("beide beschrifteten Bloecke kommen auf der Seite an") bleibt
         unveraendert. */
      expect(
        within(section).getByRole('heading', { name: 'Qualität — Einzelwerte', level: 3 }),
      ).toBeInTheDocument()
      expect(
        within(section).getByRole('heading', { name: 'Bildinhalt — Einzelwerte', level: 3 }),
      ).toBeInTheDocument()
    })

    // Akzeptanzkriterium 2: kein leerer Bereich, wenn criterion_scores leer ist. Die
    // Cloud-Vision-Status-Sektion (specs/features/0058) bleibt davon unberuehrt - sie ist IMMER
    // sichtbar (eigener describe-Block unten) und rendert deshalb weiterhin ein eigenes <dl>.
    it('renders no criterion-details dl when criterion_scores is empty', async () => {
      const list: PhotoListOut = { items: [photo({ id: 1, criterion_scores: [] })], total: 1 }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('1/1')
      expect(screen.queryByTestId('criterion-score-grid')).not.toBeInTheDocument()
    })

    // Akzeptanzkriterium 3: das Info-Icon/Popover entfaellt in der Detailansicht vollstaendig.
    it('does not render the info-icon trigger/popover anymore', async () => {
      const list: PhotoListOut = {
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('Schärfe')
      expect(
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' }),
      ).not.toBeInTheDocument()
    })

    // Akzeptanzkriterium 6: die permanente Sektion zeigt keine Ausschuss-Gruppe
    // ("Ausschuss-Vorschlag"/"Grund"), auch wenn eine Suggestion vorhanden ist - unabhaengig vom
    // separaten "Automatischer Vorschlag"-Kasten weiter unten auf der Seite.
    it('does not pass suggestion into the permanent section, even when a suggestion exists', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            ratings: [],
            suggestion: suggestion({ reason: 'low_quality' }),
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('Schärfe')
      expect(screen.queryByText('Ausschuss-Vorschlag')).not.toBeInTheDocument()
    })
  })

  // specs/features/0058-cloud-vision-status-transparenz.md: neue, permanente Sektion, immer
  // sichtbar (bewusste Stakeholder-Entscheidung, kein Ausblenden bei not_candidate/not_run).
  describe('permanent Cloud-Vision-Status section', () => {
    it('is visible even when criterion_scores is empty', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [],
            cloud_vision_status: [
              cloudVisionStatusEntry({ phase: 'landmark', status: 'not_candidate' }),
              cloudVisionStatusEntry({ phase: 'remote_category', status: 'consent_disabled' }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Nicht als Kandidat qualifiziert')).toBeInTheDocument()
      expect(screen.getByText('Cloud-Erkennung deaktiviert')).toBeInTheDocument()
    })

    it('shows a mixed state for both phases simultaneously', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            cloud_vision_status: [
              cloudVisionStatusEntry({
                phase: 'landmark',
                status: 'result',
                attempted_at: '2026-08-24T10:00:00Z',
              }),
              cloudVisionStatusEntry({
                phase: 'remote_category',
                status: 'error',
                error_message: 'Fehler beim Klassifizieren',
                attempted_at: '2026-08-24T10:00:00Z',
              }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Ergebnis vorhanden')).toBeInTheDocument()
      expect(screen.getByText('Fehler beim Versuch')).toBeInTheDocument()
      expect(screen.getByText('Fehler beim Klassifizieren')).toBeInTheDocument()
    })
  })

  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt.
  describe('Reihenfolge: Bedienelemente zuerst', () => {
    /** Foto mit JEDEM Bereich der Seite gleichzeitig - ein fehlender Bereich koennte in der
     * Soll-Folge nicht auffallen. */
    function fullPhoto(overrides: Partial<PhotoOut> = {}): PhotoOut {
      return photo({
        id: 1,
        criterion_scores: [
          criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
          criterionScore({
            criterion_key: 'content_people',
            display_name: 'Menschen erkannt',
            has_presence_threshold: true,
          }),
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
            raw_label: 'Urlaub',
            provider: 'anthropic',
          },
        ],
        cloud_vision_status: [cloudVisionStatusEntry({ phase: 'landmark', status: 'not_run' })],
        suggestion: suggestion({ reason: 'low_quality' }),
        // Mit Kopfzeile UND Staerkevektor: sonst zeigte die Motivsektion nur den Satz "noch
        // nicht klassifiziert", und der Abschnitt waere nicht vollstaendig.
        motif_assessment: CLOUD_ASSESSMENT,
        motifs: motifStrengths(),
        ...overrides,
      })
    }

    /** Dokumentreihenfolge der uebergebenen Handles. `compareDocumentPosition` wird gegen die
     * BITMASKE geprueft, nie per Gleichheit: liegen zwei Elemente ineinander, liefert der Aufruf
     * `20` (CONTAINED_BY | FOLLOWING), und ein Gleichheitsvergleich waere falsch-rot. */
    function inDocumentOrder(handles: { name: string; element: HTMLElement }[]): string[] {
      return [...handles]
        .sort((a, b) =>
          (a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
            ? -1
            : 1,
        )
        .map((handle) => handle.name)
    }

    /* AK8 (Spec 0497): EINE Liste in EINEM `toEqual`, um die neuen Abschnitts-Handles erweitert.
       Die Folge ist auf beiden Prüfbreiten dieselbe (AK9a) - sie entsteht aus der
       Dokumentreihenfolge, nicht aus einer breitenabhängigen Verzweigung. */
    async function collectSectionHandles(): Promise<{ name: string; element: HTMLElement }[]> {
      return [
        { name: 'Shortcut-Zeile', element: screen.getByText(/^Shortcuts:/) },
        { name: 'Zähler', element: screen.getByText('1/1') },
        { name: 'Foto', element: await screen.findByAltText('a.jpg') },
        { name: 'Bewertungsleiste', element: screen.getByRole('group', { name: 'Bewertung' }) },
        { name: 'Navigation', element: screen.getByRole('button', { name: 'Vorheriges Foto' }) },
        { name: 'Urteilsfläche', element: screen.getByTestId('verdict-section') },
        { name: 'Motive', element: screen.getByTestId('motifs-section') },
        // Nach der Urteilsfläche, vor dem Einzelwerte-Raster - und NICHT in ihr.
        { name: 'Personen', element: await screen.findByRole('region', { name: 'Personen' }) },
        { name: 'Einzelwerte-Raster', element: screen.getByTestId('criterion-score-grid') },
        { name: 'Aufnahmezeit', element: screen.getByTestId('taken-at-section') },
        { name: 'Ort', element: screen.getByTestId('place-line') },
        { name: 'Cloud-Vision-Status', element: screen.getByTestId('cloud-vision-status-section') },
        { name: 'Zurück zum Grid', element: screen.getByRole('link', { name: 'Zurück zum Grid' }) },
      ]
    }

    it('stellt alle Bedienelemente vor jede reine Informationsanzeige (mit Vorschlag)', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      const handles = await collectSectionHandles()
      handles.push({
        name: 'Automatischer Vorschlag',
        element: screen.getByText(/^Automatischer Vorschlag/),
      })

      expect(inDocumentOrder(handles)).toEqual([
        'Shortcut-Zeile',
        'Zähler',
        'Foto',
        'Bewertungsleiste',
        'Navigation',
        'Automatischer Vorschlag',
        'Urteilsfläche',
        'Motive',
        'Personen',
        'Einzelwerte-Raster',
        'Aufnahmezeit',
        'Ort',
        'Cloud-Vision-Status',
        'Zurück zum Grid',
      ])
    })

    /* Zweite Variante ohne den optionalen Vorschlagskasten, damit die Zusage nicht an einem
     * Bereich haengt, den es nicht immer gibt. */
    it('hält dieselbe Reihenfolge ohne Vorschlagskasten', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [fullPhoto({ suggestion: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByText(/^Automatischer Vorschlag/)).not.toBeInTheDocument()
      expect(inDocumentOrder(await collectSectionHandles())).toEqual([
        'Shortcut-Zeile',
        'Zähler',
        'Foto',
        'Bewertungsleiste',
        'Navigation',
        'Urteilsfläche',
        'Motive',
        'Personen',
        'Einzelwerte-Raster',
        'Aufnahmezeit',
        'Ort',
        'Cloud-Vision-Status',
        'Zurück zum Grid',
      ])
    })

    /* Akzeptanzkriterium 3: die Informationsanzeigen sind ohne jede Bedienhandlung vollstaendig
     * sichtbar. Abwesenheitszusage INNERHALB des Abschnitts - seitenweit waere sie falsch, weil
     * das Glossar der Motivliste bewusst ein <details> in ihrem eigenen Abschnitt bleibt. */
    it('lässt die Aufschlüsselung ohne aufklappbares Element und ohne Trigger', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')

      const info = await screen.findByTestId('criterion-score-grid')
      expect(info.querySelector('details')).toBeNull()
      expect(info.querySelector('summary')).toBeNull()
      expect(info.querySelector('[aria-expanded]')).toBeNull()
      expect(info.querySelector('[aria-haspopup]')).toBeNull()
      expect(within(info).queryByRole('button')).not.toBeInTheDocument()
      // Gegenprobe: das <details> der Motivsektion steht unveraendert weiter.
      expect(motifSection().querySelector('details')).not.toBeNull()
    })

    it('zeigt die Feinlabel-Chips in der Aufschlüsselung, nicht in der Motivsektion', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')

      /* Spec 0497: Die Feinlabel-Chips sind mit dem Urteil in die Urteilsfläche gewandert - sie
         sind eine Aussage ÜBER das Foto, kein Einzelwert zum Nachschlagen. Die geprüfte
         Verhaltensweise („die Chips stehen nicht in der Motivsektion") bleibt unverändert. */
      await screen.findByTestId('verdict-section')
      const urteil = screen.getByTestId('verdict-section')
      expect(within(urteil).getByRole('list', { name: 'Feinlabels' })).toBeInTheDocument()
      expect(within(urteil).getByText('Urlaub')).toBeInTheDocument()
      expect(within(motifSection()).queryByText('Urlaub')).not.toBeInTheDocument()
      expect(
        within(screen.getByTestId('criterion-score-grid')).queryByText('Urlaub'),
      ).not.toBeInTheDocument()
    })

    /* Akzeptanzkriterium 6: kein leerer Platzhalter. Ohne Kriterien erscheint KEINER der beiden
     * Bereiche, der Cloud-Vision-Status bleibt unveraendert immer sichtbar. */
    it('rendert ohne criterion_scores gar keine Aufschlüsselung', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [] })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByTestId('criterion-score-grid')).not.toBeInTheDocument()
      expect(screen.getByTestId('cloud-vision-status-section')).toBeInTheDocument()
    })

    it('rendert ohne Ranking keinen Bedienteil, den Informationsteil aber schon', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()], ranking: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByTestId('category-controls-section')).not.toBeInTheDocument()
      expect(screen.getByTestId('criterion-score-grid')).toBeInTheDocument()
    })
  })

  // specs/features/0426-zeitversatz-je-kamera.md, UI/UX Punkt 3: eine NEUE Anzeigestelle - eine
  // Aufnahmezeit je Foto wurde zuvor nirgends gezeigt.
  describe('Abschnitt "Aufnahmezeit"', () => {
    const RECORDED = '2026-08-12T14:32:00'
    const EFFECTIVE = '2026-08-12T12:32:00'

    function takenAtSection(): HTMLElement {
      return screen.getByTestId('taken-at-section')
    }

    it('zeigt die WIRKSAME Zeit', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, taken_at: EFFECTIVE, taken_at_original: RECORDED })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(takenAtSection()).toHaveTextContent('12.08.2026, 12:32')
    })

    it('traegt die Marke "korrigiert" nur im Korrekturfall', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            taken_at: EFFECTIVE,
            taken_at_original: RECORDED,
            time_offset_minutes: -120,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).getByText('korrigiert')).toBeInTheDocument()
    })

    it('traegt die Marke NICHT bei Versatz null', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, time_offset_minutes: 0 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).queryByText('korrigiert')).toBeNull()
    })

    it('zeigt die aufgezeichnete Zeile samt Versatz nur im Korrekturfall', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            taken_at: EFFECTIVE,
            taken_at_original: RECORDED,
            time_offset_minutes: -120,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const section = takenAtSection()
      expect(section).toHaveTextContent(/aufgezeichnet/)
      expect(section).toHaveTextContent('14:32')
      expect(section).toHaveTextContent('−2:00')
    })

    it('zeigt die aufgezeichnete Zeile NICHT bei Versatz null', async () => {
      // Bei gleichem Wert waere sie eine Wiederholung derselben Zeit - eine Aussage ohne Inhalt.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, time_offset_minutes: 0 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(takenAtSection()).not.toHaveTextContent(/aufgezeichnet/)
    })

    it('nennt die Kamera, wenn sie bestimmbar ist', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, camera: { id: 7, label: 'Canon EOS 5D' } })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).getByText('Canon EOS 5D')).toBeInTheDocument()
    })

    it('sagt als RUHIGER Satz, wenn keine Kamera bestimmbar ist', async () => {
      // Kein Fehlerton: `camera = null` ist ein regulaerer Zustand, kein Fehlen.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, camera: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(
        within(takenAtSection()).getByText('Die Kamera dieses Fotos ist nicht bestimmbar.'),
      ).toBeInTheDocument()
      expect(within(takenAtSection()).queryByRole('alert')).toBeNull()
    })
  })
})
