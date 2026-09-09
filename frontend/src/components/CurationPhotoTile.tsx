import type { CategoryKey, CategoryOut, PhotoOut, RankingOut, RatingStatus } from '../api/types'
import { qualityLevel } from '../utils/qualityLevel'
import { CategoryOverrideMarker } from './CategoryOverrideMarker'
import { CriterionDetailsPopover } from './CriterionDetailsPopover'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { SecondaryCategoryMarker } from './SecondaryCategoryMarker'
import { Button } from './ui/button'

/**
 * Strukturell die Rueckgabe von `hooks/useCategoryOverrideControls.ts` - hier als eigener Typ
 * ausgeschrieben, damit die Kachel nicht an den Hook gebunden ist (und im Test mit einfachen
 * Attrappen versorgt werden kann).
 */
export interface CategoryOverrideControls {
  overrideCategory: (photoId: number, categoryKey: CategoryKey) => void
  resetOverride: (photoId: number) => void
  pendingOverrideKeyFor: (photoId: number) => CategoryKey | null
  isResetPendingFor: (photoId: number) => boolean
}

export interface CurationPhotoTileProps {
  photo: PhotoOut
  /**
   * Die Zugehoerigkeit, unter der dieses Vorkommen steht. Seit
   * specs/features/0300-nebenkategorien.md ist die Kachel NICHT mehr durch das Foto allein
   * bestimmt: dasselbe Foto kann in zwei Kategorien stehen und traegt dort verschiedene Rollen.
   */
  ranking: RankingOut
  categories: CategoryOut[]
  categoriesLoading: boolean
  categoriesError: boolean
  onRetryCategories: () => void
  categoryOverrideControls: CategoryOverrideControls
  /**
   * Die EIGENE Bewertung des anfragenden Nutzers (`utils/ownRating.ts::ownRatingStatus`), nie
   * eine zweite Ableitung aus `photo.ratings[]` - sonst stellte die Kachel die Bewertung des
   * jeweils anderen als eigene dar (specs/features/0357-voller-bildvorrat-kuratierung.md,
   * Security-Muss-Kriterium 5).
   */
  ownStatus: RatingStatus | null
  /** true, solange die Verwerfen-Mutation DIESES Fotos laeuft. */
  rejecting: boolean
  onReject: () => void
}

/**
 * EINE Kachel der Kuratierungsansicht (specs/features/0357-voller-bildvorrat-kuratierung.md):
 * `PhotoCard` samt Info-Popover, Ecken-Markern, Qualitaetsstufe und Verwerfen-Aktion.
 *
 * Sie lag zuvor als rund 100 Zeilen JSX inline in `CurateCategoriesPage`. Mit dieser Story wird
 * sie an ZWEI Stellen gebraucht - fuer die Top-Auswahl und fuer die eingeblendeten weiteren
 * Kandidaten -, und eine zweite Kopie waere die zweite Stelle, an der eine kuenftige Aenderung
 * vergessen wird.
 */
export function CurationPhotoTile({
  photo,
  ranking,
  categories,
  categoriesLoading,
  categoriesError,
  onRetryCategories,
  categoryOverrideControls,
  ownStatus,
  rejecting,
  onReject,
}: CurationPhotoTileProps) {
  // `rank_score` ist ueber alle Zugehoerigkeiten eines Fotos identisch (ADR 0069 Punkt 4) -
  // dieselbe Kachel zeigt in zwei Kategorien dieselbe Qualitaetsstufe.
  const level = qualityLevel(ranking.rank_score)
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
      /* "Verworfen" ist ein ANZEIGEzustand, kein Filterkriterium (ADR 0071 Entscheidung 3): die
         bestehende `PhotoCard`-Prop stellt ihn bereits vollstaendig dar (gedaempfte Bildflaeche,
         RatingBadge mit x-circle, durchgestrichener Dateiname). `undefined` heisst "die Karte
         traegt keinen Zustand" und haelt die bestehende Entscheidung aufrecht, dass in der
         Kuratierung nicht auf jeder Kachel "Neu" steht. */
      status={isRejected ? 'rejected' : undefined}
      /* Zwei Marker koennen zugleich noetig sein: ein uebersteuertes Foto, das anderswo als
         Nebenkategorie steht (specs/features/0300-nebenkategorien.md, UI/UX-Abschnitt). Sie stehen
         NEBENEINANDER - kein Stapeln, kein Verdraengen; zwei size-6-Kreise passen auch im
         360px-Viewport in die Ecke. */
      topLeft={
        photo.category_override !== null || !ranking.is_primary ? (
          <div className="flex gap-1">
            {photo.category_override !== null && <CategoryOverrideMarker />}
            {!ranking.is_primary && <SecondaryCategoryMarker />}
          </div>
        ) : undefined
      }
      topRight={
        <CriterionDetailsPopover
          criterionScores={photo.criterion_scores}
          ranking={ranking}
          rankings={photo.rankings}
          suggestion={photo.suggestion}
          categoryCandidates={photo.category_candidates}
          fineLabels={photo.fine_labels}
          categories={categories}
          categoriesLoading={categoriesLoading}
          categoriesError={categoriesError}
          onRetryCategories={onRetryCategories}
          categoryOverride={photo.category_override}
          onOverrideCategory={(categoryKey) =>
            categoryOverrideControls.overrideCategory(photo.id, categoryKey)
          }
          onResetOverride={() => categoryOverrideControls.resetOverride(photo.id)}
          pendingOverrideKey={categoryOverrideControls.pendingOverrideKeyFor(photo.id)}
          resetPending={categoryOverrideControls.isResetPendingFor(photo.id)}
        />
      }
      footer={
        <div className="flex flex-col gap-2">
          {level && <QualityMeter level={level} className="text-xs" />}
          {/* Die Aktion bleibt an DERSELBEN Stelle, auch verworfen - sie wechselt nur in einen
              deaktivierten Zustand. Der zugaengliche Name traegt den Dateinamen, sonst hiessen
              auf einer Seite mit vielen Kacheln alle Schaltflaechen gleich. Waehrend einer
              laufenden Mutation wird NUR die Schaltflaeche busy; Bild, Ecken-Marker und
              Info-Trigger bleiben stehen (ein Skeleton ueberbrueckte frueher den Tausch auf ein
              ANDERES Foto und waere jetzt ein Flackern ohne Zweck). */}
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
