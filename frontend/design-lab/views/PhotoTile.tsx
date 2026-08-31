/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): die Fotokachel des
 * Markup-Vertrags.
 *
 * Fotogrid und Kuratierung zeigen dieselbe Kachel mit unterschiedlicher Fusszeile - eine geteilte
 * Komponente statt zweier Kopien, damit die Kachel nicht zwischen beiden Ansichten driftet. Die
 * drei Ansichtskomponenten bleiben davon unberuehrt: es gibt weiterhin genau GridView/DetailView/
 * PipelineView.
 *
 * Alle Haken, die eine Richtung gestalten darf, stehen hier fest:
 *   - Klassen `dl-tile`, `dl-tile__frame`, `dl-tile__decor`, `dl-tile__img`, `dl-tile__overlay`,
 *     `dl-tile__override`, `dl-tile__corner`, `dl-info`, `dl-badge`
 *   - Zustaende `data-rating="favorite|album_worthy|rejected|none"` und `data-suggested="true"`
 *
 * `dl-tile__decor` ist ein leeres, aria-hidden Element, das die meisten Richtungen ausblenden -
 * nur "dunkelkammer" (Filmperforation an der linken Kante) macht es sichtbar.
 */
import type { ReactNode } from 'react'

import {
  RATING_LABELS,
  RATING_SYMBOLS,
  SUGGESTION_PREFIX,
  type BadgeState,
  type LabPhoto,
} from '../fixtures'
import { photoSrc } from '../photoSvg'

interface PhotoTileProps {
  photo: LabPhoto
  /** Fixture-Position - entscheidet, welches lokale Foto (falls vorhanden) das Motiv uebersteuert. */
  index: number
  /** Fusszeile der Kachel: "Übernehmen" im Grid, Qualitaets-Einordnung + "Verwerfen" in der Kuratierung. */
  footer?: ReactNode
}

export function PhotoTile({ photo, index, footer }: PhotoTileProps) {
  // Anzeigeregel der echten App: die eigene Bewertung hat immer Vorrang, ein Vorschlag erscheint
  // nur, solange keine eigene Bewertung existiert.
  const isSuggested = photo.ownRating === null && photo.suggestion !== null
  const state: BadgeState = photo.ownRating ?? photo.suggestion?.status ?? 'unrated'
  const symbol = isSuggested ? `${SUGGESTION_PREFIX}${RATING_SYMBOLS[state]}` : RATING_SYMBOLS[state]
  const badgeLabel =
    state === 'unrated'
      ? 'Unbewertet'
      : isSuggested
        ? `Vorschlag: ${RATING_LABELS[state]}`
        : RATING_LABELS[state]
  const ratingAttribute = state === 'unrated' ? 'none' : state

  return (
    <li
      className="dl-tile"
      data-rating={ratingAttribute}
      data-suggested={isSuggested ? 'true' : undefined}
    >
      <div className="dl-tile__frame">
        <span className="dl-tile__decor" aria-hidden="true" />
        <img
          className="dl-tile__img"
          src={photoSrc(index, photo.motif, photo.aspect)}
          alt={photo.fileName}
        />
        <div className="dl-tile__overlay">
          {photo.categoryOverride !== null && (
            <span className="dl-tile__override" role="img" aria-label="Kategorie manuell übersteuert">
              <span aria-hidden="true">✎</span>
            </span>
          )}
          <div className="dl-tile__corner">
            {/* Statisches Element - die Mockups loesen nichts aus. Muss in jeder Richtung ein
                44-px-Ziel sein, damit sichtbar wird, wie stark er im jeweiligen Bild auftraegt. */}
            <button type="button" className="dl-info" aria-label={`Bewertungsdetails: ${photo.fileName}`}>
              <span aria-hidden="true">i</span>
            </button>
            <span
              className="dl-badge"
              data-rating={ratingAttribute}
              data-suggested={isSuggested ? 'true' : undefined}
              aria-label={badgeLabel}
            >
              <span aria-hidden="true">{symbol}</span>
            </span>
          </div>
        </div>
      </div>
      {footer}
    </li>
  )
}
