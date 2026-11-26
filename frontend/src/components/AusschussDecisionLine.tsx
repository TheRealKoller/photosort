import type { AusschussReason, DuplicateDecision } from '../api/types'
import { DUPLICATE_ZUSTAENDE } from './DuplicatePhotoTile'

/** Die Entscheidungszeile eines noch offenen Eintrags: Die Zeile trennt den GRUND der
 * Markierung von der getroffenen ENTSCHEIDUNG. */
export const AUSSCHUSS_OPEN_LABEL = 'Vorgeschlagen'

/** Die Farbe der Entscheidungszeile. `null` (noch offen) ist zurueckhaltend: Es ist der Zustand
 * ohne Handlung, nicht einer mit. */
export const ENTSCHEIDUNG_SCHRIFT: Record<DuplicateDecision | 'offen', string> = {
  keep: 'text-accent',
  discard: 'text-danger-text',
  offen: 'text-text-muted',
}

/** Der gespeicherte Zeilenwert als Wort. `null` heisst "noch nicht entschieden" - es gibt keine
 * Ruecknahme, und die Ansicht bietet deshalb auch keine an. */
export function entscheidungswort(decision: DuplicateDecision | null): string {
  return decision === null ? AUSSCHUSS_OPEN_LABEL : DUPLICATE_ZUSTAENDE[decision].text
}

/** Die Zusaetze an der Entscheidungszeile. `Aus früherem Lauf` gehoert zum dritten Grund und
 * tritt an die Stelle des Grund-Kennzeichens; `wirkt nicht mehr` markiert ein gespeichertes
 * `keep`, das den Zustand nicht mehr bestimmt. Beide Texte sind Anzeige des SERVERWERTS, keine
 * Ableitung aus `reason` oder `decision` — und sie schliessen einander aus: Wo kein aktueller
 * Grund steht, gibt es auch keinen, auf den sich `wirkt nicht mehr` beziehen koennte. */
export function Entscheidungshinweise({
  reason,
  decision,
  decisionEffective,
  keepPossible,
}: {
  reason: AusschussReason
  decision: DuplicateDecision | null
  decisionEffective: boolean | null
  keepPossible: boolean
}) {
  const ausFrueheremLauf = reason === 'earlier_decision'
  const wirktNichtMehr =
    !ausFrueheremLauf && decision === 'keep' && decisionEffective === false && !keepPossible
  if (!ausFrueheremLauf && !wirktNichtMehr) {
    return null
  }
  return (
    <>
      {ausFrueheremLauf && <span className="text-xs text-text-muted">Aus früherem Lauf</span>}
      {wirktNichtMehr && <span className="text-xs text-text-muted">wirkt nicht mehr</span>}
    </>
  )
}
