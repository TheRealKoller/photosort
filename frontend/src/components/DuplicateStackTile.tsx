import { Fragment } from 'react'
import { Link } from 'react-router'

import type { AusschussGroupEntry } from '../api/types'
import { duplicateComparePath } from '../utils/projectRoutes'
import { GrundKennzeichen } from './AusschussGrund'
import { PhotoImage } from './PhotoImage'

/** Die Rahmen der beiden hinteren Karten - reine Umrisse ohne Bild und ohne Anfrage. */
const HINTERE_KARTE =
  'pointer-events-none absolute rounded-md border border-border-control bg-elevated'

/**
 * EINE Duplikatgruppe der Ausschuss-Übersicht als Kartenstapel (B1–B5).
 *
 * GENAU EIN LINK, das einzige fokussierbare Element: Er führt in die Vergleichsansicht am Anker,
 * mit Rückweg. Aus der Übersicht führt damit kein Weg in die Detailansicht eines Gruppenmitglieds.
 * Die hinteren Karten sind keine eigenen Ziele (`pointer-events-none`), ein Tipp auf ihre Fläche
 * trifft denselben Link; sie verdecken weder Dateiname noch Kennzeichen.
 *
 * DER VERSATZ LIEGT INNERHALB DER KACHELMASSE aus `justifiedRows`: 8px oben und rechts, in den
 * Stufen 4 und 8. Nach außen versetzt spränge die Zeile über ihre Breite und scrollte bei 360px
 * waagerecht. `overflow-hidden` trägt nur die vordere Karte - am `li` schnitte es den Fokusring ab.
 *
 * Die Zahlen kommen vom Server: `group_size` (die ganze Serie, dieselbe Zahl wie im Kopf der
 * Vergleichsansicht) und `decision_counts` über den gespeicherten Zeilen - nie eine Ableitung in
 * TypeScript. Nur der Dateiname wird gekürzt; Kennzeichen, Anzahl und Zusammenfassung brechen um.
 */
export function DuplicateStackTile({
  projectId,
  entry,
  width,
  height,
}: {
  projectId: number
  entry: AusschussGroupEntry
  width: number
  height: number
}) {
  const { undecided, keep, discard } = entry.decision_counts
  const teile = [
    { anzahl: undecided, text: `${undecided} vorgeschlagen`, schrift: 'text-text-muted' },
    { anzahl: discard, text: `${discard} Ausschuss`, schrift: 'text-danger-text' },
    { anzahl: keep, text: `${keep} behalten`, schrift: 'text-accent' },
  ].filter((teil) => teil.anzahl > 0)
  const name =
    `Duplikat-Gruppe mit ${entry.group_size} Aufnahmen vergleichen ` +
    `(${teile.map((teil) => teil.text).join(', ')}): ${entry.cover.relative_path}`

  return (
    <li className="relative" style={{ width, height }}>
      <Link
        to={duplicateComparePath(projectId, entry.group_anchor_photo_id, { fromAusschuss: true })}
        aria-label={name}
        className="relative block size-full"
      >
        <span
          aria-hidden="true"
          data-stack-card
          className={`${HINTERE_KARTE} top-0 right-0 bottom-2 left-2`}
        />
        <span
          aria-hidden="true"
          data-stack-card
          className={`${HINTERE_KARTE} top-1 right-1 bottom-1 left-1`}
        />
        <span className="absolute top-2 right-2 bottom-0 left-0 overflow-hidden rounded-md border border-border-control bg-elevated">
          <PhotoImage
            photoId={entry.cover.id}
            variant="thumbnail"
            alt={entry.cover.relative_path}
            className="size-full object-cover"
          />
          <span className="pointer-events-none absolute top-1 left-1 rounded-sm bg-overlay p-1">
            <GrundKennzeichen reason="duplicate" />
          </span>
          <span className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-2 bg-overlay px-2 py-1 text-xs">
            <span className="text-text-h">{entry.group_size} Aufnahmen</span>
            {teile.map((teil, index) => (
              <Fragment key={teil.text}>
                {index > 0 && <span aria-hidden="true">·</span>}
                <span data-stack-summary className={`hyphens-auto ${teil.schrift}`}>
                  {teil.text}
                </span>
              </Fragment>
            ))}
            <span className="min-w-6 flex-1 truncate font-mono text-text-muted">
              {entry.cover.relative_path.split('/').pop()}
            </span>
          </span>
        </span>
      </Link>
    </li>
  )
}
