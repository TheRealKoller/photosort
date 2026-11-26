import { useEffect, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CloudVisionStatusList } from '../components/CloudVisionStatusList'
import { CriterionScoreGrid } from '../components/CriterionScoreGrid'
import { PhotoCaptureFacts } from '../components/PhotoCaptureFacts'
import { PhotoDetailStage } from '../components/PhotoDetailStage'
import { PhotoDetailStates } from '../components/PhotoDetailStates'
import { PhotoPersonsSection } from '../components/PhotoPersonsSection'
import { PhotoSuggestionNotice } from '../components/PhotoSuggestionNotice'
import { PhotoVerdictSection } from '../components/PhotoVerdictSection'
import { Button } from '../components/ui/button'
import { useMotifCorrectionControls } from '../hooks/useMotifCorrection'
import { useMotifsQuery } from '../hooks/useMotifs'
import { usePhotoDetailKeys } from '../hooks/usePhotoDetailKeys'
import {
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetFavoriteMutation,
  useSetRatingMutation,
} from '../hooks/usePhotos'
import { usePhotoSequenceNavigation } from '../hooks/usePhotoSequenceNavigation'
import { usePersonFilter } from '../hooks/usePersonFilter'
import { ownFavorite, ownRatingStatus } from '../utils/ownRating'
import { withPersonIds } from '../utils/personFilter'
import { parseRatingFilter } from '../utils/ratingFilter'
import { eyeVerdict } from '../utils/eyeVerdict'

const SWIPE_THRESHOLD_PX = 50

// Der Text der Meldung bei fehlgeschlagenem `GET /motifs`. Er steht HIER und nicht in der
// Staerkeliste: der Baustein bekommt den Text durchgereicht und entscheidet nicht selbst, wie ein
// Ladefehler heisst - so kann das Info-Popover der Kachel denselben Baustein mit einem
// eigenen Text verwenden.
const MOTIF_SET_ERROR_TEXT = 'Die Motive konnten nicht geladen werden.'

export function PhotoDetailPage() {
  const { projectId, photoId } = useParams()
  const id = Number(projectId)
  const currentPhotoId = Number(photoId)
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam
  // Blättern und Zähler laufen in der nach `person` gefilterten Folge - derselbe
  // Query-Key wie im Bildbestand, also dieselbe Folge. Jeder Weg zurück trägt beide Filter.
  const { personIds } = usePersonFilter(searchParams, setSearchParams)
  const filterSearch = withPersonIds(
    new URLSearchParams(filterParam ? { filter: filterParam } : {}),
    personIds,
  ).toString()
  const filterQuery = filterSearch ? `?${filterSearch}` : ''

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus, undefined, personIds)
  const setMutation = useSetRatingMutation(id)
  const deleteMutation = useDeleteRatingMutation(id)
  const favoriteMutation = useSetFavoriteMutation(id)
  // Das feste Motivset kommt vom Server (langlebiger Cache) - Anzeigenamen,
  // Reihenfolge und Erklaertexte der Staerkeliste stammen ausschliesslich daraus.
  const motifsQuery = useMotifsQuery()
  // EIN Mutation-Paar fuer diese Seite - `pendingMotifKeyFor` sperrt nur die Zeile, deren
  // Korrektur laeuft.
  const motifCorrectionControls = useMotifCorrectionControls(id)

  const photos = query.data?.pages.flatMap((page) => page.items) ?? []
  const total = query.data?.pages[0]?.total ?? 0
  const index = photos.findIndex((photo) => photo.id === currentPhotoId)
  const currentPhoto = index >= 0 ? photos[index] : undefined

  const { handlePrev, handleNext, advanceToNextUnrated, completed } = usePhotoSequenceNavigation({
    projectId: id,
    photos,
    index,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    filterQuery,
    username,
  })

  const currentOwnStatus = ownRatingStatus(currentPhoto?.ratings ?? [], username)
  const currentOwnFavorite = ownFavorite(currentPhoto?.ratings ?? [], username)
  // Anzeigeregel: eigene Bewertung hat immer Vorrang (gleiche Regel wie im Raster).
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
    // Auto-Advance gilt nur "nach dem Setzen einer Bewertung" - ein Toggle zurueck auf
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

  usePhotoDetailKeys({ handlePrev, handleNext, handleToggleRating, handleToggleFavorite })

  /**
   * DIE SEITE STEHT BEIM OEFFNEN OBEN - die Vorbedingung der Buehnengeometrie.
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

  const gridPath = `/projects/${id}/photos${filterQuery}`

  if (query.isLoading || query.isError || completed || !currentPhoto) {
    return (
      <PhotoDetailStates
        status={
          query.isLoading
            ? 'loading'
            : query.isError
              ? 'error'
              : completed
                ? 'completed'
                : 'not-found'
        }
        errorText={
          query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'
        }
        onRetry={() => void query.refetch()}
        gridPath={gridPath}
        selectionPath={`/projects/${id}/selection`}
      />
    )
  }

  const isMutating = setMutation.isPending || deleteMutation.isPending || favoriteMutation.isPending
  // Eye liefert hier nur die Feinlabels; die zaehlende Albumstufe kommt aus
  // `album_suitability` und bringt ihre Herkunft (`source`) mit.
  const eyeFineLabels =
    currentPhoto.eye_result != null ? eyeVerdict(currentPhoto.eye_result).fineLabels : null

  return (
    <div className="flex flex-col gap-4">
      {/* DIE BUEHNE steht als ERSTES und ohne irgendetwas darueber: Ihre Hoehe ist aus dem
          Sichtfenster gerechnet, und jedes Element darueber schoebe ihre Unterkante um die eigene
          Hoehe unter den Sichtrand. Der Shortcut-Hinweis ist deshalb in sie gewandert. */}
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
        <PhotoSuggestionNotice
          suggestion={suggestion}
          busy={isMutating}
          onAccept={() => handleToggleRating(suggestion.status)}
        />
      )}

      {/* DIE URTEILSFLAECHE - das Urteil ueber dieses Foto, unmittelbar hinter der Buehne und VOR
          den Einzelwerten. Sie traegt die Albumtauglichkeit mit Begruendung, den Rang und
          die Feinlabel; darunter steht der Motivbereich, dessen Detailzeile den reservierten
          Platz haelt.

          Der Motivbereich steht PERMANENT, auch ohne Kopfzeile - dann zeigt er an Stelle der
          Reihe einen Satz. Er ist der einzige Bedienblock dieses Abschnitts. */}
      <PhotoVerdictSection
        photo={currentPhoto}
        eyeFineLabels={eyeFineLabels}
        motifSet={motifsQuery.data}
        motifSetLoading={motifsQuery.isPending}
        motifSetError={motifsQuery.isError ? MOTIF_SET_ERROR_TEXT : undefined}
        onMotifSetRetry={() => void motifsQuery.refetch()}
        onCorrect={(motifKey, applies) =>
          motifCorrectionControls.correctMotif(currentPhoto.id, motifKey, applies)
        }
        onWithdraw={(motifKey) =>
          motifCorrectionControls.withdrawCorrection(currentPhoto.id, motifKey)
        }
        pendingMotifKey={motifCorrectionControls.pendingMotifKeyFor(currentPhoto.id)}
        error={motifCorrectionControls.error}
      />

      {/* DER PERSONENABSCHNITT - nach der Urteilsfläche, nicht in ihr: eine Person ist
          kein Motiv. Je Foto neu eingebunden, damit ein Fotowechsel Busy, Meldung und
          Gesichterwahl zurücksetzt. */}
      <PhotoPersonsSection key={currentPhoto.id} projectId={id} photo={currentPhoto} />

      {/* DAS EINZELWERTE-RASTER - Nachschlagwerk hinter dem Urteil.
          KEIN leerer Bereich bei leerer Liste. Ohne Wrapper-`div` eingebunden, damit auch
          kein leerer Behaelter stehenbleibt - der Baustein rendert dann gar nichts, und sein
          eigener Testhaken `criterion-score-grid` ist der Nachweis.

          OHNE `ranking`: Der Rang ist keiner der fuenfzehn Einzelwerte, sondern Teil des Urteils
          und steht allein in `PhotoVerdict`. */}
      <CriterionScoreGrid criterionScores={currentPhoto.criterion_scores} />

      {/* Trennlinie zwischen Urteil/Nachschlagwerk und den uebrigen Angaben: ohne sie stiessen
          die Bloecke unvermittelt aneinander, und der Wechsel von "wie dieses Foto beurteilt ist"
          zu "was das System sonst ueber dieses Foto weiss" waere nicht ablesbar. `--separator`
          ist die freistehende Linie auf dem Grund. */}
      <div className="border-t border-separator" />

      {/* AUFNAHMEZEIT: Sie steht im Informationsteil, weil sie sagt, was das System über dieses
          Foto weiß. */}
      <PhotoCaptureFacts photo={currentPhoto} headingLevel="h2" />

      {/* Layout & Platzierung: nach den Bewertungs-Buttons. IMMER sichtbar (bewusste Entscheidung,
          kein Ausblenden bei not_candidate/not_run) - kein `.length > 0`-Sichtbarkeitsgate. */}
      <div className="text-sm text-text" data-testid="cloud-vision-status-section">
        <CloudVisionStatusList cloudVisionStatus={currentPhoto.cloud_vision_status} />
      </div>

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </Button>
    </div>
  )
}
