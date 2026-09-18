import { useId } from 'react'

import type {
  AlbumSuitabilityOut,
  CriterionScoreOut,
  FineLabelOut,
  RankingOut,
  SuggestionOut,
} from '../api/types'
import {
  ALBUM_SUITABILITY_NOT_RATED_TEXT,
  formatAlbumSuitabilityLevel,
} from '../utils/albumSuitability'
import { partitionByPresenceThreshold } from '../utils/criterionScores'
import { formatCriterionPercent } from '../utils/formatStats'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { FineLabelList } from './FineLabelList'

interface CriterionDetailsListProps {
  criterionScores: CriterionScoreOut[]
  /** Die Rangzeile des Fotos - `null`, solange kein erfolgreicher Lauf existiert. Sie trägt
   * „Rang M von N". */
  ranking: RankingOut | null
  suggestion: SuggestionOut | null
  // Blendet die Ausschuss-Gruppe unbedingt aus, unabhaengig von `suggestion` - die permanente
  // Sektion in PhotoDetailPage.tsx reicht `suggestion` zwar ohnehin nicht durch, dieses Flag ist
  // trotzdem die alleinige, direkt getestete Absicherung gegen ein versehentliches kuenftiges
  // Durchreichen.
  showSuggestion: boolean
  /** Bis zu zwei frei formulierte Feinlabels - reine Zusatzinformation am Foto, kein Motiv.
   * Ohne Feinlabels wird KEIN Platzhalter gerendert.
   *
   * SICHERHEITSHINWEIS: freier, extern erzeugter LLM-Text - ausschliesslich als regulaerer
   * React-Textknoten rendern (nie dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in
   * href/src/style). Das ist keine blosse Konvention, sondern die tragende Voraussetzung dafuer,
   * dass das Session-Token in `localStorage` liegen darf. Bricht in
   * `CriterionDetailsList.test.tsx > never renders a fine label via dangerouslySetInnerHTML`. */
  fineLabels?: FineLabelOut[]
  /** Die Albumtauglichkeit des Modells. `null` heisst „noch nicht bewertet" - dann trägt die
   * Zeile den Satz statt einer Stufe, und es erscheint KEINE Begründungszeile. `undefined`
   * heisst „diese Einbindungsstelle reicht das Feld nicht durch" und lässt die Zeile ganz weg.
   *
   * SICHERHEITSHINWEIS wie bei `fineLabels`: `reason` ist freier, extern erzeugter LLM-Text -
   * ausschliesslich als regulärer React-Textknoten rendern. Bricht in
   * `CriterionDetailsList.test.tsx > never renders the reason via dangerouslySetInnerHTML`. */
  albumSuitability?: AlbumSuitabilityOut | null
}

function CriterionRow({ score }: { score: CriterionScoreOut }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-text">{score.display_name}</dt>
      <dd className="font-medium text-text-h">{formatCriterionPercent(score.value)}</dd>
    </div>
  )
}

/**
 * Reine Praesentationskomponente mit den Bewertungsdetails eines Fotos - geteilt zwischen dem
 * Info-Popover der Kachel und der permanenten Sektion in PhotoDetailPage.tsx (DRY). Prueft selbst
 * NICHT, ob `criterionScores` leer ist - die Entscheidung, den Bereich bei leerer Liste gar nicht
 * erst einzubinden, bleibt bewusst bei den jeweiligen Aufrufern, da beide Stellen die gleiche
 * Bedingung ohnehin schon selbst pruefen muessen (Popover fuer den Trigger, PhotoDetailPage.tsx
 * fuer den Abschnitts-Rahmen).
 *
 * Gliedert die Kriterien in zwei beschriftete Bloecke "Qualitaet"/"Bildinhalt": ein Block ohne
 * Inhalt wird komplett weggelassen (keine Ueberschrift, kein leeres `<dl>`), bei komplett leerer
 * Eingabe rendert die Komponente nur noch den aeusseren Container ohne jedes `dt`/`dd`. Der
 * Ausschuss-Vorschlag bleibt ein dritter, eigener Bereich ausserhalb beider Bloecke und ohne
 * eigene Ueberschrift.
 *
 * KEIN MOTIV-TEIL. Die Motivstaerken sind ein eigener Baustein (`MotifStrengthSection`) und
 * stehen im Popover daneben, nicht hier: sie tragen ihre eigenen Zustaende (noch nicht klassifiziert,
 * lokale Grundlage, ausgeschlossen) und ihre eigene Ladelogik. Die frueheren Kategorie-Teile
 * (Kandidatenliste, "Kategorie"-Zeile, "Rolle", "Alle Kategorien"-Auswahl, Konfidenz-Erklaerung)
 * sind mit Spec 0427 vollstaendig entfallen.
 */
export function CriterionDetailsList({
  criterionScores,
  ranking,
  suggestion,
  showSuggestion,
  fineLabels = [],
  albumSuitability,
}: CriterionDetailsListProps) {
  const { quality: qualityScores, content: contentScores } =
    partitionByPresenceThreshold(criterionScores)
  // "Rang" gehoert fachlich zum Bildinhalt-Block - er erscheint deshalb auch ohne ein einziges
  // Inhalts-Kriterium, sobald eine Rangzeile MIT Rang vorliegt. Auf `!== null` geprueft, nie auf
  // Falsyness: "Rang - von 12" waere eine Rangaussage ueber ein Foto ohne Rang.
  const showRankRow = ranking !== null && ranking.rank_position !== null
  const showContentBlock = contentScores.length > 0 || showRankRow
  // Die Albumtauglichkeit gehoert in den Qualitaetsblock - sie IST der Qualitaetswert des Fotos.
  // `undefined` laesst die Zeile weg, `null` traegt den Satz "Noch nicht bewertet".
  const showAlbumSuitability = albumSuitability !== undefined
  const showQualityBlock = qualityScores.length > 0 || showAlbumSuitability
  const showSuggestionGroup = showSuggestion && suggestion !== null
  // Ein einzelnes useId() mit Suffixen statt zweier Aufrufe (React-Doku-Muster fuer mehrere
  // zusammengehoerige Ids) - noetig, weil zwei Instanzen gleichzeitig im DOM stehen koennen
  // (Popover ueber der permanenten Sektion) und feste Ids dann kollidieren wuerden.
  const blockId = useId()
  const qualityHeadingId = `${blockId}-quality`
  const contentHeadingId = `${blockId}-content`

  return (
    <div className="flex flex-col gap-4">
      {showQualityBlock && (
        // role="group" + aria-labelledby am Wrapper, NICHT am <dl>: ein <dl> hat in dieser
        // Toolchain keine namensfaehige Rolle, die Beschriftung kaeme dort weder im
        // Accessibility-Tree noch in einer Rollenabfrage an.
        <div role="group" aria-labelledby={qualityHeadingId} className="flex flex-col gap-2">
          <h3 id={qualityHeadingId} className="text-xs font-medium text-text-h">
            Qualität
          </h3>
          <dl className="flex flex-col gap-2">
            {/* Die Modellstufe steht VOR den lokalen Messungen: sie führt, die Messungen
                korrigieren sie nur innerhalb ihrer Stufe. */}
            {showAlbumSuitability && (
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Albumtauglichkeit</dt>
                <dd className="font-medium text-text-h">
                  {albumSuitability === null
                    ? ALBUM_SUITABILITY_NOT_RATED_TEXT
                    : formatAlbumSuitabilityLevel(albumSuitability.level)}
                </dd>
              </div>
            )}
            {qualityScores.map((score) => (
              <CriterionRow key={score.criterion_key} score={score} />
            ))}
          </dl>
          {/* Die Begründung des Modells über die VOLLE Breite und UNGEKÜRZT - das Popover ist
              288px breit und scrollt bereits. Reiner React-Textknoten: freier LLM-Text, nie als
              HTML. Ohne Begründung entfällt der Träger ersatzlos, kein Platzhalter. */}
          {albumSuitability != null && albumSuitability.reason !== null && (
            <p data-album-suitability-reason="" className="text-xs text-text">
              {albumSuitability.reason}
            </p>
          )}
        </div>
      )}
      {showContentBlock && (
        <div role="group" aria-labelledby={contentHeadingId} className="flex flex-col gap-2">
          {/* "Bildinhalt" statt des frueheren "Kategorien": die Zeilen darunter sind
              Mess-Signale ueber den Bildinhalt (Menschen, Tier, Gebaeude, Landschaft, …) und
              bilden seit Spec 0427 keine Kategorie mehr. Bewusst auch kein Motiv-Wort - die
              Motivstaerken sind eine andere Aussage und stehen in ihrer eigenen Liste. */}
          <h3 id={contentHeadingId} className="text-xs font-medium text-text-h">
            Bildinhalt
          </h3>
          <dl className="flex flex-col gap-2">
            {contentScores.map((score) => (
              <CriterionRow key={score.criterion_key} score={score} />
            ))}
            {showRankRow && ranking !== null && (
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Rang</dt>
                <dd className="font-medium text-text-h">
                  Rang {ranking.rank_position} von {ranking.partition_size}
                </dd>
              </div>
            )}
          </dl>
          {/* Feinlabel-Chips: raeumlich deutlich von den Kriterienzeilen getrennt, kompakter und
              in einem anderen Ton (`suggested`-Variante des Akzent-Chips) - sie sind
              Zusatzinformation, keine Einordnung. Bewusst OHNE Icon/Symbol, damit sie nicht mit
              den Bewertungs-Chips verwechselt werden. Ohne Feinlabels wird KEIN Platzhalter
              gerendert - der Bereich entfaellt ersatzlos. */}
          {fineLabels.length > 0 && (
            <div className="mt-2 flex flex-col gap-2">
              <h4 className="text-xs text-text">Feinlabels</h4>
              {/* Die Chips selbst liegen in `FineLabelList` - zeichengleich geteilt mit dem
                  Seitenurteil, damit sie nicht an zwei Stellen verschieden aussehen. */}
              <FineLabelList fineLabels={fineLabels} />
            </div>
          )}
        </div>
      )}
      {/* Dritter, eigener Bereich ausserhalb beider Bloecke und bewusst OHNE eigene
          Ueberschrift - erscheint auch dann, wenn beide Bloecke leer sind. */}
      {showSuggestionGroup && (
        <dl className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Ausschuss-Vorschlag</dt>
            <dd className="font-medium text-text-h">{formatSuggestionStatusLabel(suggestion)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Grund</dt>
            <dd className="font-medium text-text-h">{formatSuggestionReason(suggestion)}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}
