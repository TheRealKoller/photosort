import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CloudVisionStatusList } from '../components/CloudVisionStatusList'
import { CriterionScoreGrid } from '../components/CriterionScoreGrid'
import { MotifStrengthSection } from '../components/MotifStrengthSection'
import { PhotoCaptureFacts } from '../components/PhotoCaptureFacts'
import { PhotoDetailStage } from '../components/PhotoDetailStage'
import { PhotoVerdict } from '../components/PhotoVerdict'
import { Button } from '../components/ui/button'
import { useMotifCorrectionControls } from '../hooks/useMotifCorrection'
import { useMotifsQuery } from '../hooks/useMotifs'
import {
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetFavoriteMutation,
  useSetRatingMutation,
} from '../hooks/usePhotos'
import { ownFavorite, ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'

// Bounded so a broken/degenerate filter can never spin forever fetching pages while searching for
// the next unrated photo - 80 * PHOTOS_PAGE_SIZE(60) covers well beyond any realistic project size
// for this two-person MVP.
const MAX_AUTO_ADVANCE_PAGE_FETCHES = 80

const SWIPE_THRESHOLD_PX = 50

// Der Text der Meldung bei fehlgeschlagenem `GET /motifs`. Er steht HIER und nicht in der
// Staerkeliste: der Baustein bekommt den Text durchgereicht und entscheidet nicht selbst, wie ein
// Ladefehler heisst - so kann das Info-Popover der Kachel (PR 3) denselben Baustein mit einem
// eigenen Text verwenden.
const MOTIF_SET_ERROR_TEXT = 'Die Motive konnten nicht geladen werden.'

function isTextInputFocused(): boolean {
  const active = document.activeElement
  if (active === null) {
    return false
  }
  if (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') {
    return true
  }
  return (active as HTMLElement).isContentEditable
}

export function PhotoDetailPage() {
  const { projectId, photoId } = useParams()
  const id = Number(projectId)
  const currentPhotoId = Number(photoId)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam
  const filterQuery = filterParam ? `?filter=${filterParam}` : ''

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  const setMutation = useSetRatingMutation(id)
  const deleteMutation = useDeleteRatingMutation(id)
  const favoriteMutation = useSetFavoriteMutation(id)
  // Das feste Motivset kommt vom Server (langlebiger Cache) - Anzeigenamen,
  // Reihenfolge und Erklaertexte der Staerkeliste stammen ausschliesslich daraus.
  const motifsQuery = useMotifsQuery()
  // EIN Mutation-Paar fuer diese Seite - `pendingMotifKeyFor` sperrt nur die Zeile, deren
  // Korrektur laeuft.
  const motifCorrectionControls = useMotifCorrectionControls(id)

  const [completed, setCompleted] = useState(false)

  const photos = query.data?.pages.flatMap((page) => page.items) ?? []
  const total = query.data?.pages[0]?.total ?? 0
  const index = photos.findIndex((photo) => photo.id === currentPhotoId)
  const currentPhoto = index >= 0 ? photos[index] : undefined

  function goTo(targetPhotoId: number): void {
    navigate(`/projects/${id}/photos/${targetPhotoId}${filterQuery}`)
  }

  function handlePrev(): void {
    if (index > 0) {
      goTo(photos[index - 1].id)
    }
  }

  async function handleNext(): Promise<void> {
    if (index < 0) {
      return
    }
    let currentPhotos = photos
    let fetches = 0
    while (
      index + 1 >= currentPhotos.length &&
      query.hasNextPage &&
      fetches < MAX_AUTO_ADVANCE_PAGE_FETCHES
    ) {
      const result = await query.fetchNextPage()
      currentPhotos = result.data?.pages.flatMap((page) => page.items) ?? currentPhotos
      fetches += 1
    }
    if (index + 1 < currentPhotos.length) {
      goTo(currentPhotos[index + 1].id)
    }
  }

  /**
   * Sucht ab fromIndex vorwaerts in der zum Klick-Zeitpunkt geladenen Foto-Sequenz nach dem
   * naechsten unbewerteten Foto (Auto-Advance). Arbeitet bewusst auf dieser VOR der durch die
   * Mutation ausgeloesten Invalidierung erfassten Momentaufnahme statt auf einem Refetch zu warten:
   * da sich nur das gerade bewertete Foto aendert, bleibt der Bewertungsstatus aller anderen Fotos
   * in der Momentaufnahme weiterhin korrekt - unabhaengig davon, ob/wann die Invalidierung neu
   * laedt.
   */
  async function advanceToNextUnrated(fromIndex: number): Promise<void> {
    let currentPhotos = photos
    let i = fromIndex
    let fetches = 0
    for (;;) {
      while (i < currentPhotos.length) {
        const candidate = currentPhotos[i]
        // "Noch offen" ist die fehlende ALBUMENTSCHEIDUNG, nicht die fehlende Zeile: ein nur als
        // Favorit markiertes Foto ist unentschieden und darf nicht uebersprungen werden.
        if (ownRatingStatus(candidate.ratings, username) === null) {
          goTo(candidate.id)
          return
        }
        i += 1
      }
      if (!query.hasNextPage || fetches >= MAX_AUTO_ADVANCE_PAGE_FETCHES) {
        break
      }
      const result = await query.fetchNextPage()
      currentPhotos = result.data?.pages.flatMap((page) => page.items) ?? currentPhotos
      fetches += 1
    }
    setCompleted(true)
  }

  const currentOwnStatus = ownRatingStatus(currentPhoto?.ratings ?? [], username)
  const currentOwnFavorite = ownFavorite(currentPhoto?.ratings ?? [], username)
  // Anzeigeregel (Akzeptanzkriterium der Spec): eigene Bewertung hat immer Vorrang - der Server
  // liefert suggestion in diesem Fall ohnehin bereits als null, currentOwnStatus wird hier
  // trotzdem zusaetzlich geprueft (defensiv, gleiche Regel wie im Raster).
  const suggestion = currentOwnStatus === null ? (currentPhoto?.suggestion ?? null) : null

  function handleToggleRating(status: RatingStatus): void {
    if (
      !currentPhoto ||
      setMutation.isPending ||
      deleteMutation.isPending ||
      favoriteMutation.isPending
    ) {
      return
    }
    // Auto-Advance gilt laut Spec nur "nach dem Setzen einer Bewertung" - ein Toggle zurueck auf
    // unbewertet ist eine Korrektur (Nutzer macht einen Fehlklick rueckgaengig), kein "fertig mit
    // diesem Foto"; automatisches Weiterspringen waere hier ueberraschend statt hilfreich.
    if (currentOwnStatus === status) {
      deleteMutation.mutate(currentPhoto.id)
    } else {
      const fromIndex = index + 1
      setMutation.mutate(
        { photoId: currentPhoto.id, status },
        { onSuccess: () => void advanceToNextUnrated(fromIndex) },
      )
    }
  }

  /**
   * Das Favoriten-Kennzeichen umschalten - eigener Handler auf einem eigenen Endpunkt.
   *
   * KEIN Auto-Advance: Die Auszeichnung ist keine Entscheidung über dieses Foto ("fertig damit"),
   * sondern eine Notiz daneben; weiterzuspringen nähme dem Nutzer die Möglichkeit, im selben
   * Atemzug noch die Albumentscheidung zu treffen.
   */
  function handleToggleFavorite(): void {
    if (
      !currentPhoto ||
      setMutation.isPending ||
      deleteMutation.isPending ||
      favoriteMutation.isPending
    ) {
      return
    }
    favoriteMutation.mutate({ photoId: currentPhoto.id, favorite: !currentOwnFavorite })
  }

  // Ref-Indirektion (wie ProjectDetailPage.tsx::refetchRef): der Listener wird nur EINMAL
  // registriert, liest aber bei jedem Tastendruck die jeweils aktuellen Handler.
  const handlersRef = useRef({ handlePrev, handleNext, handleToggleRating, handleToggleFavorite })
  handlersRef.current = { handlePrev, handleNext, handleToggleRating, handleToggleFavorite }

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent): void {
      if (isTextInputFocused()) {
        return
      }
      switch (event.key) {
        case 'ArrowLeft':
          handlersRef.current.handlePrev()
          break
        case 'ArrowRight':
          void handlersRef.current.handleNext()
          break
        // Die Belegung 1 / 2 / 3 bleibt; Taste 1 schaltet seit ADR 0098 das UNABHAENGIGE
        // Favoriten-Kennzeichen und laesst die Albumentscheidung unberuehrt (und umgekehrt).
        case '1':
          handlersRef.current.handleToggleFavorite()
          break
        case '2':
          handlersRef.current.handleToggleRating('album_worthy')
          break
        case '3':
          handlersRef.current.handleToggleRating('rejected')
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])

  /**
   * DIE SEITE STEHT BEIM OEFFNEN OBEN (AK2) - die Vorbedingung der Buehnengeometrie.
   *
   * Die Buehne ist aus dem Sichtfenster gerechnet und steht ganz oben auf der Seite; sie liegt nur
   * dann vollstaendig im Bild, wenn die Seite auch oben steht. Ohne diese Ruecksetzung uebernimmt
   * die Detailansicht den Scrollstand des Rasters, aus dem sie geoeffnet wurde: Beim Klick auf eine
   * weiter unten liegende Kachel landet der Nutzer auf einer bereits gescrollten Detailseite, und
   * Bewertungsleiste und Navigation stehen unter dem Sichtrand.
   *
   * AN `currentPhotoId` GEBUNDEN, nicht an den Seitenaufbau: Jedes neue Foto ist erneut ein
   * "Oeffnen der Ansicht" - Pfeiltaste, Wischen und Auto-Advance fuehren alle hierher. Innerhalb
   * DESSELBEN Fotos laeuft der Effekt nicht und nimmt dem Nutzer sein Scrollen nicht weg.
   */
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [currentPhotoId])

  // Swipe navigiert, Bewertung erfolgt separat per Tap auf die Bewertungs-Buttons (nicht per Swipe,
  // um versehentliche Bewertungen zu vermeiden).
  const touchStartXRef = useRef<number | null>(null)

  function handleTouchStart(event: React.TouchEvent<HTMLDivElement>): void {
    touchStartXRef.current = event.touches[0]?.clientX ?? null
  }

  function handleTouchEnd(event: React.TouchEvent<HTMLDivElement>): void {
    const startX = touchStartXRef.current
    touchStartXRef.current = null
    if (startX === null) {
      return
    }
    const endX = event.changedTouches[0]?.clientX ?? startX
    const deltaX = endX - startX
    if (deltaX > SWIPE_THRESHOLD_PX) {
      handlePrev()
    } else if (deltaX < -SWIPE_THRESHOLD_PX) {
      void handleNext()
    }
  }

  /* Der Rahmen der Buehne steht in ALLEN DREI Zustaenden - ladend und fehler zeigen ihn mit
     Platzhalter bzw. `Alert` in der Fotoflaeche statt eines vorgezogenen Satzes. Sonst springt die
     Seite beim Eintreffen der Daten. Die Handler zeigen in diesen beiden Zustaenden ins Leere und
     sind deshalb leer: die Buehne sperrt Bewertung und Navigation ohnehin selbst. */
  function stageOnlyFrame(status: 'loading' | 'error') {
    return (
      <div className="flex flex-col gap-4">
        <PhotoDetailStage
          status={status}
          counter={null}
          photoId={null}
          altText=""
          errorText={
            query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'
          }
          onRetry={() => void query.refetch()}
          currentStatus={null}
          favorite={false}
          onToggle={() => {}}
          onToggleFavorite={() => {}}
          ratingDisabled
          ratingBusy={false}
          onPrev={() => {}}
          onNext={() => {}}
          prevDisabled
          nextDisabled
        />
        <Button asChild variant="ghost" className="self-start">
          <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
        </Button>
      </div>
    )
  }

  if (query.isLoading) {
    return stageOnlyFrame('loading')
  }

  if (query.isError) {
    return stageOnlyFrame('error')
  }

  if (completed) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="status" className="text-text-h">
          Fertig! Keine weiteren unbewerteten Fotos.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="secondary">
            <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to={`/projects/${id}/selection`}>Zur Endauswahl</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (!currentPhoto) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Foto nicht in der aktuellen Auswahl gefunden.</p>
        <Button asChild variant="ghost">
          <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
        </Button>
      </div>
    )
  }

  const isMutating = setMutation.isPending || deleteMutation.isPending || favoriteMutation.isPending

  return (
    <div className="flex flex-col gap-4">
      {/* DIE BUEHNE steht als ERSTES und ohne irgendetwas darueber: Ihre Hoehe ist aus dem
          Sichtfenster gerechnet, und jedes Element darueber schoebe ihre Unterkante um die eigene
          Hoehe unter den Sichtrand (AK2). Der Shortcut-Hinweis ist deshalb in sie gewandert. */}
      <PhotoDetailStage
        status="ready"
        counter={`${index + 1}/${total}`}
        photoId={currentPhoto.id}
        altText={currentPhoto.relative_path}
        currentStatus={currentOwnStatus}
        favorite={currentOwnFavorite}
        onToggle={handleToggleRating}
        onToggleFavorite={handleToggleFavorite}
        ratingDisabled={isMutating}
        ratingBusy={isMutating}
        onPrev={handlePrev}
        onNext={() => void handleNext()}
        prevDisabled={index <= 0}
        nextDisabled={index + 1 >= photos.length && !query.hasNextPage}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      />

      {suggestion && (
        <div className="flex flex-col items-start gap-2 rounded-md border border-accent bg-elevated p-3 text-sm">
          <p className="text-text-h">
            Automatischer Vorschlag: {formatSuggestionStatusLabel(suggestion)}
          </p>
          {/* Formatierung aus utils/suggestionLabels.ts - dasselbe Muster wird auch von
              CriterionDetailsPopover.tsx verwendet, keine zweite Kopie derselben Logik. Der
              fruehere dritte Fall "top_pick" (Kategorie + Qualitaets-Einordnung) ist entfallen -
              dieser Kuratierungs-Kontext lebt in der
              eigenstaendigen /curate-Ansicht statt in diesem Ausschuss-Vorschlagskasten (siehe
              api/types.ts::SuggestionOut-Docstring). */}
          <p className="text-text">{formatSuggestionReason(suggestion)}</p>
          {/* Ruft denselben Mutation-Pfad wie ein manueller Klick auf die passende
              RatingButtons-Option auf (UI/UX-Abschnitt der Spec) - der bestehende Auto-Advance
              greift danach unveraendert. Kein eigener "Vorschlag verwerfen"-Zustand: normale
              Weiternavigation ist das implizite Ignorieren. */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            busy={isMutating}
            onClick={() => handleToggleRating(suggestion.status)}
          >
            Vorschlag übernehmen
          </Button>
        </div>
      )}

      {/* DIE URTEILSFLAECHE - das Urteil ueber dieses Foto, unmittelbar hinter der Buehne und VOR
          den Einzelwerten (AK5). Sie traegt die Albumtauglichkeit mit Begruendung, den Rang und
          die Feinlabel; darunter steht der Motivbereich, dessen Detailzeile den reservierten
          Platz haelt (AK6/AK7).

          Der Motivbereich steht PERMANENT, auch ohne Kopfzeile - dann zeigt er an Stelle der
          Reihe einen Satz. Er ist der einzige Bedienblock dieses Abschnitts. */}
      <section
        className="flex flex-col gap-4 rounded-md border border-border bg-surface p-4"
        aria-labelledby="verdict-heading"
        data-testid="verdict-section"
      >
        <h2 id="verdict-heading" className="sr-only">
          Urteil
        </h2>
        <PhotoVerdict
          // `?? null` heisst hier "noch nicht bewertet" und nicht "Feld nicht durchgereicht":
          // diese Ansicht zeigt die Zeile immer, mit Stufe oder mit dem Satz.
          albumSuitability={currentPhoto.album_suitability ?? null}
          ranking={currentPhoto.ranking ?? null}
          fineLabels={currentPhoto.fine_labels}
        />

        <section
          className="flex flex-col gap-2 text-base"
          aria-labelledby="motifs-heading"
          data-testid="motifs-section"
        >
          <h2
            id="motifs-heading"
            className="text-xs font-semibold tracking-wide text-text-h uppercase"
          >
            Motive
          </h2>
          <MotifStrengthSection
            motifSet={motifsQuery.data}
            motifSetLoading={motifsQuery.isPending}
            motifSetError={motifsQuery.isError ? MOTIF_SET_ERROR_TEXT : undefined}
            onMotifSetRetry={() => void motifsQuery.refetch()}
            assessment={currentPhoto.motif_assessment ?? null}
            motifs={currentPhoto.motifs ?? []}
            editable
            onCorrect={(motifKey, applies) =>
              motifCorrectionControls.correctMotif(currentPhoto.id, motifKey, applies)
            }
            onWithdraw={(motifKey) =>
              motifCorrectionControls.withdrawCorrection(currentPhoto.id, motifKey)
            }
            pendingMotifKey={motifCorrectionControls.pendingMotifKeyFor(currentPhoto.id)}
            error={motifCorrectionControls.error}
          />
        </section>
      </section>

      {/* DAS EINZELWERTE-RASTER - Nachschlagwerk hinter dem Urteil. Gleiche Sichtbarkeitsregel wie
          bisher: KEIN leerer Bereich bei leerer Liste. Ohne Wrapper-`div` eingebunden, damit auch
          kein leerer Behaelter stehenbleibt - der Baustein rendert dann gar nichts, und sein
          eigener Testhaken `criterion-score-grid` ist der Nachweis.

          OHNE `ranking`: Der Rang ist keiner der fuenfzehn Einzelwerte, sondern Teil des Urteils
          und steht allein in `PhotoVerdict` (AK5). */}
      <CriterionScoreGrid criterionScores={currentPhoto.criterion_scores} />

      {/* Trennlinie zwischen Urteil/Nachschlagwerk und den uebrigen Angaben: ohne sie stiessen
          die Bloecke unvermittelt aneinander, und der Wechsel von "wie dieses Foto beurteilt ist"
          zu "was das System sonst ueber dieses Foto weiss" waere nicht ablesbar. `--separator`
          ist die freistehende Linie auf dem Grund. */}
      <div className="border-t border-separator" />

      {/* AUFNAHMEZEIT - eine NEUE Anzeigestelle, keine Kennzeichnung an einer bestehenden: eine
          Aufnahmezeit je Foto wurde vor Spec 0426 nirgends gezeigt. Sie steht im
          Informationsteil, weil sie sagt, was das System über dieses Foto weiß. */}
      <PhotoCaptureFacts photo={currentPhoto} headingLevel="h2" />

      {/* Layout & Platzierung: unmittelbar vor der CriterionDetailsList UND nach den
          Bewertungs-Buttons - beides zusammen ist erst seit der Umordnung der Seite erfuellbar
          (die Bewertungsleiste stand zuvor weiter unten). IMMER sichtbar (bewusste
          Stakeholder-Entscheidung, kein Ausblenden bei not_candidate/not_run, siehe
          Spec-Abschnitt "Entscheidungen") - anders als die CriterionDetailsList darunter kein
          `.length > 0`-Sichtbarkeitsgate. */}
      <div className="text-sm text-text" data-testid="cloud-vision-status-section">
        <CloudVisionStatusList cloudVisionStatus={currentPhoto.cloud_vision_status} />
      </div>

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </Button>
    </div>
  )
}
