import type { ClassificationReviewDetailOut, ClassificationReviewPurpose } from '../api/types'
import {
  NO_SHARED_STATEMENT_TEXT,
  noPhotosComparedText,
  notComparedText,
  PURPOSE_LABELS,
  PURPOSE_UNIT_LABELS,
  REVIEW_DETAIL_TEXTS,
  silentSide,
  UNIT_GROUP_LABELS,
  VERDICT_LABELS,
  VERDICT_ORDER,
} from '../utils/classificationReviewLabels'

const PURPOSES = Object.keys(PURPOSE_LABELS) as ClassificationReviewPurpose[]
const UNITS = ['photo', 'pair'] as const
const COUNT_COLUMNS = ['matching', 'deviating', 'presented'] as const

/*
 * Die Zweckspalte bekommt ein Drittel, die Zaehlspalten teilen den Rest zu gleichen Teilen
 * (`table-fixed` ohne eigene Breite). Das genuegt bei 360 px: Ohne feste Breiten spannt eine
 * Tabelle ihre Spalten auf die min-content-Breite von "uebereinstimmend" und "Albumtauglichkeit"
 * und schoebe die Seite waagerecht ueber den Rand (gemessen in
 * `e2e/tests/no-horizontal-scroll.spec.ts`). `hyphens-auto` bricht laengere Woerter an
 * Silbengrenzen, `break-words` bleibt der Rueckfall fuer Woerter ohne Trennstelle.
 */
const HEAD_CELL = 'hyphens-auto break-words py-2 pl-1 text-right align-bottom font-semibold sm:pl-2'
const ROW_HEAD_CELL = 'hyphens-auto py-2 text-left font-normal break-words text-text'
const NUMBER_CELL = 'py-2 pl-1 text-right tabular-nums text-text-h sm:pl-2'
const PURPOSE_COLUMN = 'w-1/3'

/**
 * Die Uebersicht einer abgeschlossenen Pruefung (Spec 0616, UI/UX): zwei schmale Tabellen statt
 * einer breiten, damit bei 360 px nichts waagerecht scrollt.
 *
 * "Abweichungen" gliedert sich nach EINHEIT: die fotozaehlenden Zwecke in einer Zeilengruppe, die
 * Merkmale (Foto × Motiv) als Paare in einer eigenen - eine Zeile "12" ohne Einheit liesse offen,
 * ob zwoelf Fotos oder zwoelf Paare gemeint sind. Die Einheit steht deshalb in jedem Spaltenkopf
 * der Gruppe. Kein Gesamturteil und keine Empfehlung: die Seite zaehlt, sie entscheidet nicht.
 */
export function ClassificationReviewOverview({
  review,
}: {
  review: ClassificationReviewDetailOut
}) {
  const kinds = { a: review.sides.a.kind, b: review.sides.b.kind }
  // Alle Fotos einzeln gescheitert: dann ist "keine Fotos verglichen" die Aussage, nicht das
  // Schweigen einer Seite.
  const nothingCompared = review.photo_count - review.unclassifiable_photo_count <= 0
  return (
    <section aria-labelledby="review-overview-title" className="flex flex-col gap-4">
      <h2 id="review-overview-title" className="text-lg">
        {REVIEW_DETAIL_TEXTS.overviewTitle}
      </h2>

      <table className="w-full table-fixed border-collapse text-sm">
        <colgroup>
          <col className={PURPOSE_COLUMN} />
        </colgroup>
        <caption className="pb-2 text-left text-sm font-semibold text-text-h">
          {REVIEW_DETAIL_TEXTS.deviationsCaption}
        </caption>
        {UNITS.map((unit) => {
          const purposes = PURPOSES.filter(
            (purpose) => review.counts_by_purpose[purpose].unit === unit,
          )
          if (purposes.length === 0) {
            return null
          }
          const unitLabel = PURPOSE_UNIT_LABELS[unit]
          return (
            <tbody key={unit} className="border-t border-separator">
              <tr className="text-xs text-text-muted">
                <th scope="col" className="py-2 text-left align-bottom font-semibold">
                  {UNIT_GROUP_LABELS[unit]}
                </th>
                {COUNT_COLUMNS.map((column) => (
                  <th key={column} scope="col" className={HEAD_CELL}>
                    {REVIEW_DETAIL_TEXTS[column]}
                    <span className="block font-normal">{unitLabel}</span>
                  </th>
                ))}
              </tr>
              {purposes.map((purpose) => {
                const counts = review.counts_by_purpose[purpose]
                const silent = silentSide(purpose, kinds)
                return (
                  <tr key={purpose} className="border-t border-separator">
                    <th scope="row" className={ROW_HEAD_CELL}>
                      {PURPOSE_LABELS[purpose]}
                    </th>
                    {counts.compared === 0 ? (
                      <td colSpan={COUNT_COLUMNS.length} className="py-2 pl-2 text-text">
                        {nothingCompared
                          ? noPhotosComparedText(review.unclassifiable_photo_count)
                          : silent !== null
                            ? notComparedText(silent)
                            : NO_SHARED_STATEMENT_TEXT}
                      </td>
                    ) : (
                      COUNT_COLUMNS.map((column) => (
                        <td key={column} className={NUMBER_CELL}>
                          {counts[column]}
                        </td>
                      ))
                    )}
                  </tr>
                )
              })}
            </tbody>
          )
        })}
      </table>

      <table className="w-full table-fixed border-collapse text-sm">
        <colgroup>
          <col className={PURPOSE_COLUMN} />
        </colgroup>
        <caption className="pb-2 text-left text-sm font-semibold text-text-h">
          {REVIEW_DETAIL_TEXTS.verdictsCaption}
        </caption>
        <thead>
          <tr className="text-xs text-text-muted">
            <th scope="col" className="py-2 text-left align-bottom font-semibold">
              {REVIEW_DETAIL_TEXTS.purposeColumn}
            </th>
            {VERDICT_ORDER.map((verdict) => (
              <th key={verdict} scope="col" className={HEAD_CELL}>
                {VERDICT_LABELS[verdict]}
              </th>
            ))}
            <th scope="col" className={HEAD_CELL}>
              {REVIEW_DETAIL_TEXTS.open}
            </th>
          </tr>
        </thead>
        <tbody>
          {PURPOSES.map((purpose) => {
            const counts = review.verdicts_by_purpose[purpose]
            return (
              <tr key={purpose} className="border-t border-separator">
                <th scope="row" className={ROW_HEAD_CELL}>
                  {PURPOSE_LABELS[purpose]}
                </th>
                {VERDICT_ORDER.map((verdict) => (
                  <td key={verdict} className={NUMBER_CELL}>
                    {counts[verdict]}
                  </td>
                ))}
                <td className={NUMBER_CELL}>{counts.open}</td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr className="border-t border-border-control font-semibold">
            <th scope="row" className="py-2 text-left text-text-h">
              {REVIEW_DETAIL_TEXTS.total}
            </th>
            {VERDICT_ORDER.map((verdict) => (
              <td key={verdict} className={NUMBER_CELL}>
                {review.verdict_counts[verdict]}
              </td>
            ))}
            <td className={NUMBER_CELL}>{review.verdict_counts.open}</td>
          </tr>
        </tfoot>
      </table>
    </section>
  )
}
