import { useEffect, useRef } from 'react'

import type { MotifSetOut, PhotoOut, RatingStatus } from '../api/types'
import { isInAlbum, isTakenWithoutProposal } from '../utils/albumDraft'
import { qualityLevel } from '../utils/qualityLevel'
import { CriterionDetailsPopover } from './CriterionDetailsPopover'
import { MotifAssessmentMarker } from './MotifAssessmentMarker'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

/**
 * Die Kennzeichnung von „aufgenommen, vom aktuellen Vorschlag nicht getragen".
 *
 * EINE Zeichenkette für BEIDE Datenformen (`ranking: null` und `ranking.proposed === false`) -
 * die Kennzeichnung ist an genau dieser Stelle definiert, damit dieselbe Lage nicht je nach
 * Datenform verschieden aussieht.
 */
export const NOT_PROPOSED_BADGE_TEXT = 'nicht vorgeschlagen'

export interface CurationPhotoTileProps {
  photo: PhotoOut
  /** Das geladene Motivset - reine Durchreichung an das Info-Popover, das die Motivstärken
   * schreibgeschützt zeigt. `undefined` während des Ladens bzw. nach einem Fehlschlag. */
  motifSet: MotifSetOut | undefined
  motifSetLoading: boolean
  motifSetError: string | undefined
  onMotifSetRetry: () => void
  /**
   * Die EIGENE Bewertung des anfragenden Nutzers (`utils/ownRating.ts::ownRatingStatus`), nie
   * eine zweite Ableitung aus `photo.ratings[]` - sonst stellte die Kachel die Bewertung des
   * jeweils anderen als eigene dar (Sicherheits-Muss-Kriterium).
   */
  ownStatus: RatingStatus | null
  /** true, solange die Entscheidung DIESES Fotos laeuft. */
  deciding: boolean
  onDecide: (status: RatingStatus) => void
  /** Oeffnet den Alternativen-Dialog zu diesem Bild. Geladen wird erst DORT. */
  onOpenAlternatives: () => void
  /**
   * Holt den Fokus auf den Album-Zweizustand dieser Kachel - gesetzt fuer genau EINE Kachel und
   * genau nach einem Austausch.
   *
   * Der Dialog gibt den Fokus beim Schliessen an sein ausloesendes Element zurueck; nach einem
   * Austausch ist das die Schaltflaeche eines Bildes, das den Platz gewechselt hat. React laesst
   * ALLE Aufraeumfunktionen vor allen neuen Effekten laufen - die Fokusnahme hier gewinnt
   * deshalb gegen die Rueckgabe des Dialogs, unabhaengig von der Reihenfolge im Baum.
   */
  focusDecision: boolean
}

/**
 * EINE Kachel des Album-Entwurfs: `PhotoCard` samt Info-Popover, Ecken-Marker, Qualitaetsstufe,
 * Begruendung des Modells und dem Zweizustand „Im Album" ⇄ „Gestrichen".
 *
 * MOTIVNAMEN UND STAERKEN ERSCHEINEN NICHT AUF DER KACHEL: acht Werte haben bei 158px
 * Kachelbreite keinen Platz, und der staerkste allein behauptete wieder eine Hauptkategorie. Sie
 * stehen im Info-Popover (schreibgeschuetzt) und in der Einzelbildansicht.
 */
export function CurationPhotoTile({
  photo,
  motifSet,
  motifSetLoading,
  motifSetError,
  onMotifSetRetry,
  ownStatus,
  deciding,
  onDecide,
  onOpenAlternatives,
  focusDecision,
}: CurationPhotoTileProps) {
  const decisionRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (focusDecision) {
      decisionRef.current?.focus()
    }
  }, [focusDecision])

  // `?? null` fuer den FEHLENDEN Wert, nie fuer die Zahl selbst: `0` ist ein gueltiger
  // Qualitaetswert (schlechteste Modellstufe), und ein `||` verloere ihn lautlos. Ohne Rangzeile
  // und ohne Qualitaetswert ist `level === null` - die Kachel sagt dann "Noch nicht bewertet"
  // statt gar nichts: ein Foto ohne Stufenzeile saehe aus wie eines, dessen Zeile nur gerade
  // fehlt.
  const level = qualityLevel(photo.ranking?.rank_score ?? null)
  const reason = photo.album_suitability?.reason ?? null
  const inAlbum = isInAlbum(ownStatus)
  const takenWithoutProposal = isTakenWithoutProposal(photo, ownStatus)

  return (
    <PhotoCard
      relativePath={photo.relative_path}
      image={
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt={photo.relative_path}
          className="size-full object-cover"
        />
      }
      /* "Verworfen" ist ein ANZEIGEzustand, kein Filterkriterium: die
         bestehende `PhotoCard`-Prop stellt ihn bereits vollstaendig dar (RatingBadge mit
         x-circle, durchgestrichener Dateiname). `undefined` heisst "die Karte
         traegt keinen Zustand" und haelt die bestehende Entscheidung aufrecht, dass in der
         Kuratierung nicht auf jeder Kachel "Neu" steht. */
      status={inAlbum ? undefined : 'rejected'}
      /* DER EINZIGE Motiv-Marker der Kachel. Lokale Grundlage und Dokument-Ausschluss stehen im
         Info-Popover und in der Einzelansicht, nicht als weitere Ecken-Glyphen. `=== null`
         geprueft und nicht auf Falsyness: `undefined` (Feld nicht durchgereicht) ist keine
         Aussage ueber den Klassifizierungsstand. */
      topLeft={photo.motif_assessment === null ? <MotifAssessmentMarker /> : undefined}
      topRight={
        <CriterionDetailsPopover
          criterionScores={photo.criterion_scores}
          ranking={photo.ranking ?? null}
          suggestion={photo.suggestion}
          fineLabels={photo.fine_labels}
          motifSet={motifSet}
          motifSetLoading={motifSetLoading}
          motifSetError={motifSetError}
          onMotifSetRetry={onMotifSetRetry}
          assessment={photo.motif_assessment ?? null}
          motifs={photo.motifs}
          albumSuitability={photo.album_suitability ?? null}
        />
      }
      footer={
        <div className="flex flex-col gap-2">
          <QualityMeter level={level} className="text-xs" />
          {/* Die Begruendung des Modells: visuell auf zwei Zeilen gekuerzt (`line-clamp-2`), im
              DOM und damit fuer Screenreader VOLLSTAENDIG - gekuerzt wird die Darstellung, nie
              die Zeichenkette. Ohne Begruendung entfaellt die Zeile ersatzlos, kein Platzhalter
              und kein "—". Reiner React-Textknoten: freier Modelltext, nie als HTML, nie in
              `href`/`src`/`style`. Kein Ausklapp-Bedienelement - die Fusszeile behaelt genau eine
              Trefferflaeche. */}
          {reason !== null && (
            <p data-album-suitability-reason="" className="line-clamp-2 text-xs text-text">
              {reason}
            </p>
          )}
          {/* „Aufgenommen, vom aktuellen Vorschlag nicht getragen" - UEBER der Fusszeile, weil
              der Zustand zum Bild gehoert und nicht zur Aktion. Die Kachel wird dabei NICHT ans
              Ende sortiert: das Bild ist eine bewusste eigene Entscheidung, kein Mangel. */}
          {takenWithoutProposal && (
            <div>
              <Badge tone="neutral">{NOT_PROPOSED_BADGE_TEXT}</Badge>
            </div>
          )}
          {/* ZWEI Trefferflaechen nebeneinander - die Fusszeile verliert hier bewusst ihre
              bisherige Ein-Trefferflaechen-Regel. Links der Zweizustand der Albumentscheidung,
              rechts der Zugang zu den Alternativen; 12px Abstand (`gap-3`), beide auf dem Telefon
              sichtbar mindestens 44px hoch (`h-11 sm:h-8`, wie die Bewertungsleiste).

              DER ZWEIZUSTAND ist ein Druck ohne Bestaetigungsschritt und ohne Dialog.
              `aria-pressed` statt einer eigenen Umschalter-Rolle; die Beschriftung nennt den
              ZUSTAND, nicht die Handlung. Beide zugaenglichen Namen tragen den Dateinamen - sonst
              hiessen auf einer Seite mit vielen Kacheln alle Schaltflaechen gleich.

              Waehrend der eigenen laufenden Mutation ist der Zweizustand gesperrt: Ein zweiter
              Druck auf DASSELBE Foto liefe in den Unique-Constraint der Bewertungszeile.
              Verschiedene Fotos entscheiden unabhaengig voneinander. Die Alternativen bleiben
              erreichbar - sie lesen nur. */}
          <div className="flex gap-3">
            <Button
              ref={decisionRef}
              type="button"
              variant="outline"
              size="sm"
              className="h-11 flex-1 sm:h-8"
              aria-pressed={inAlbum}
              disabled={deciding}
              busy={deciding}
              aria-label={`${inAlbum ? 'Im Album' : 'Gestrichen'}: ${photo.relative_path}`}
              onClick={() => onDecide(inAlbum ? 'rejected' : 'album_worthy')}
            >
              {inAlbum ? 'Im Album' : 'Gestrichen'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-11 flex-1 sm:h-8"
              aria-label={`Alternativen: ${photo.relative_path}`}
              onClick={onOpenAlternatives}
            >
              Alternativen
            </Button>
          </div>
        </div>
      }
    />
  )
}
