import { Icon, type IconName } from './ui/icon'
import type { MotifFillStep } from '../utils/motifStrength'

/**
 * Ein Motivsymbol als Fuellstand: dasselbe Symbol ZWEIMAL uebereinander - unten vollstaendig in
 * `text-text-muted`, darueber deckungsgleich in der Bandfarbe, beschnitten auf die unteren
 * `fillPercent` Prozent seiner Hoehe (ADR 0113 Punkt 2).
 *
 * DIE UMRISSEBENE IST BEI JEDER STAERKE VOLLSTAENDIG DA, einschliesslich 0 % und 100 %: Die
 * Symbolform bleibt damit immer erkennbar, und ein schwach vertretenes Motiv wirkt nicht
 * abgeschnitten (AK2).
 *
 * `fillPercent` kommt FERTIG GERUNDET herein - derselbe Wert, den die Aufrufstelle als Text
 * zeigt. Hier wird nicht ein zweites Mal gerundet, sonst koennten Fuellhoehe und angezeigte Zahl
 * auseinanderlaufen (AK4).
 *
 * Beide Ebenen sind `aria-hidden`; die Aussage traegt der zugaengliche Name der umgebenden
 * Schaltflaeche. Der Beschnitt steht als `clip-path`-Rezept in `index.css` (`motif-fill-clip`);
 * uebergeben wird nur der Prozentwert als CSS-Variable - eine `clip-path-[…]`-Utility im TSX
 * loeste die Vertragsregel "keine willkuerlichen Werte" aus.
 *
 * KEIN VERLAUF UND KEINE MASKE IM SVG: beide verlangen je Symbol eine eindeutige Id im Dokument
 * und damit einen Eingriff in `ui/icon.tsx`, deren Ausgabe zugleich der Penpot-Schnappschuss ist.
 */
interface MotifStrengthSymbolProps {
  iconName: IconName
  step: MotifFillStep
  /** Bereits gerundeter Prozentwert (0-100) - die Hoehe der Fuellung. */
  fillPercent: number
  size?: number
}

/** Die drei Bandfarben aus dem bestehenden Vorrat (ADR 0113 Punkt 4). `none` faerbt nicht ein:
 * die Fuellebene ist dann ohnehin auf 0 % beschnitten. */
const FILL_TONE: Record<MotifFillStep, string> = {
  strong: 'text-status-success',
  medium: 'text-status-running',
  weak: 'text-status-failed',
  none: '',
}

export function MotifStrengthSymbol({
  iconName,
  step,
  fillPercent,
  size = 24,
}: MotifStrengthSymbolProps) {
  return (
    <span className="relative inline-flex items-center justify-center">
      <span data-motif-layer="outline" className="text-text-muted">
        <Icon name={iconName} size={size} />
      </span>
      <span
        data-motif-layer="fill"
        className={`motif-fill-clip absolute inset-0 inline-flex items-center justify-center ${FILL_TONE[step]}`}
        style={{ '--motif-fill': `${fillPercent}%` } as React.CSSProperties}
      >
        <Icon name={iconName} size={size} />
      </span>
    </span>
  )
}
