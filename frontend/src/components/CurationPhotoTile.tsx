import type { MotifSetOut, PhotoOut, RatingStatus } from '../api/types'
import { qualityLevel } from '../utils/qualityLevel'
import { CriterionDetailsPopover } from './CriterionDetailsPopover'
import { MotifAssessmentMarker } from './MotifAssessmentMarker'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Button } from './ui/button'

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
  /** true, solange die Verwerfen-Mutation DIESES Fotos laeuft. */
  rejecting: boolean
  onReject: () => void
}

/**
 * EINE Kachel der Kuratierungsansicht: `PhotoCard` samt Info-Popover, Ecken-Marker,
 * Qualitaetsstufe und Verwerfen-Aktion.
 *
 * Sie wird an ZWEI Stellen gebraucht - fuer die Top-Auswahl und fuer die eingeblendeten weiteren
 * Kandidaten -, und eine zweite Kopie waere die zweite Stelle, an der eine kuenftige Aenderung
 * vergessen wird.
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
  rejecting,
  onReject,
}: CurationPhotoTileProps) {
  // `?? null` fuer den FEHLENDEN Wert, nie fuer die Zahl selbst: `0` ist ein gueltiger
  // Qualitaetswert (schlechteste Modellstufe), und ein `||` verloere ihn lautlos. Ohne Rangzeile
  // und ohne Qualitaetswert ist `level === null` - die Kachel sagt dann "Noch nicht bewertet"
  // statt gar nichts: ein Foto ohne Stufenzeile saehe aus wie eines, dessen Zeile nur gerade
  // fehlt.
  const level = qualityLevel(photo.ranking?.rank_score ?? null)
  const reason = photo.album_suitability?.reason ?? null
  const isRejected = ownStatus === 'rejected'

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
         bestehende `PhotoCard`-Prop stellt ihn bereits vollstaendig dar (gedaempfte Bildflaeche,
         RatingBadge mit x-circle, durchgestrichener Dateiname). `undefined` heisst "die Karte
         traegt keinen Zustand" und haelt die bestehende Entscheidung aufrecht, dass in der
         Kuratierung nicht auf jeder Kachel "Neu" steht. */
      status={isRejected ? 'rejected' : undefined}
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
          {/* Die Aktion bleibt an DERSELBEN Stelle, auch verworfen - sie wechselt nur in einen
              deaktivierten Zustand. Der zugaengliche Name traegt den Dateinamen, sonst hiessen
              auf einer Seite mit vielen Kacheln alle Schaltflaechen gleich. Waehrend einer
              laufenden Mutation wird NUR die Schaltflaeche busy; Bild, Ecken-Marker und
              Info-Trigger bleiben stehen. */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isRejected || rejecting}
            busy={rejecting}
            aria-label={`${isRejected ? 'Verworfen' : 'Verwerfen'}: ${photo.relative_path}`}
            onClick={onReject}
          >
            {isRejected ? 'Verworfen' : rejecting ? 'Wird verworfen…' : 'Verwerfen'}
          </Button>
        </div>
      }
    />
  )
}
