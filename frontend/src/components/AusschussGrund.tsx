import type { SuggestionReason } from '../api/types'
import { cn } from '../lib/utils'
import { Icon } from './ui/icon'

/**
 * Das Grund-Kennzeichen des Ausschusses: Zeichen UND Wort, unterscheidbar nach Art.
 *
 * Die Farbe trägt die Aussage nie allein - das Wort steht daneben. `--danger-text` statt
 * `--danger`: Der grafische Ton hält als Fließtext kein AA.
 */
const GRUND_KENNZEICHEN: Record<SuggestionReason, { text: string; schrift: string }> = {
  duplicate: { text: 'Duplikat', schrift: 'text-accent' },
  low_quality: { text: 'Geringe Bildqualität', schrift: 'text-danger-text' },
}

/**
 * Der Duplikat-Stapel: drei versetzte Kartenumrisse aus der Design-Nutzlast (Schlüssel
 * `ausschuss`). DATEILOKALES SVG statt eines neuen Symbols im Satz von `ui/icon.tsx`: Der Satz
 * des Boards führt kein Stapel-Symbol, und ihn dafür zu erweitern wäre eine Gestaltungsentscheidung
 * ohne Vorlage - dieselbe Begründung wie beim Schloss in `StepMarker`.
 */
function StapelZeichen() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" width={14} height={14} className="shrink-0">
      <rect x="1.5" y="5.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
      <rect x="3.5" y="3.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
      <rect x="5.5" y="1.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
    </svg>
  )
}

/** Grund-Kennzeichen - an der Einzelkachel, am Stapel und in der Detailansicht. */
export function GrundKennzeichen({ reason }: { reason: SuggestionReason }) {
  const kennzeichen = GRUND_KENNZEICHEN[reason]
  return (
    <span className={cn('flex items-center gap-1 text-xs', kennzeichen.schrift)}>
      {reason === 'duplicate' ? <StapelZeichen /> : <Icon name="image" size={14} />}
      {kennzeichen.text}
    </span>
  )
}
