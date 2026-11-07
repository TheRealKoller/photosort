import {
  CLASSIFICATION_REVIEW_TEXTS,
  CLASSIFICATION_REVIEW_TITLE,
} from '../utils/classificationReviewLabels'

/**
 * Seite 2 der Klassifizierungspruefung (Spec 0616): Uebersicht mit Fallansicht und Download.
 *
 * Bewusst noch der Kopf allein: Diese Stufe bringt Routen, Nebenziel, Client und Begriffsquelle
 * ins Produkt; Uebersicht und Fallansicht folgen als eigener Schritt.
 */
export function ClassificationReviewDetailPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl sm:text-2xl">{CLASSIFICATION_REVIEW_TITLE}</h1>
        <p className="text-sm text-text">{CLASSIFICATION_REVIEW_TEXTS.intro}</p>
      </header>
    </div>
  )
}
