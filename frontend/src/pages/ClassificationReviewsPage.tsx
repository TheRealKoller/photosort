import {
  CLASSIFICATION_REVIEW_TEXTS,
  CLASSIFICATION_REVIEW_TITLE,
} from '../utils/classificationReviewLabels'

/**
 * Seite 1 der Klassifizierungspruefung (Spec 0616): Liste der Pruefungen und das Anlegen-Panel.
 *
 * Bewusst noch der Kopf allein: Diese Stufe bringt Routen, Nebenziel, Client und Begriffsquelle
 * ins Produkt; Liste und Anlegen folgen als eigener Schritt. Der Kopf traegt bereits Titel und
 * dauerhaften Satz aus der Begriffsquelle, damit die Seite nicht als leerer Platzhalter erscheint.
 */
export function ClassificationReviewsPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl sm:text-2xl">{CLASSIFICATION_REVIEW_TITLE}</h1>
        <p className="text-sm text-text">{CLASSIFICATION_REVIEW_TEXTS.intro}</p>
      </header>
    </div>
  )
}
