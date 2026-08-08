import type { QualityLevel } from '../utils/qualityLevel'
import { QUALITY_LEVEL_LABELS } from '../utils/qualityLevel'

const DOTS: Record<QualityLevel, string> = {
  high: '●●●',
  medium: '●●○',
  low: '●○○',
}

interface QualityMeterProps {
  level: QualityLevel
  className?: string
}

/**
 * Grobe, verstaendliche 3-Stufen-Qualitaets-Einordnung statt eines Rohwerts
 * (specs/features/0024-top-photo-selection-category-mix.md, UI/UX-Abschnitt "Grobe Qualitaets-
 * Einordnung statt Rohwert") - bewusst kein Stern-Symbol (Kollision mit dem `favorite`-★) und keine
 * Prozess-Status-Farbe (Qualitaet ist weder Erfolg noch Fehler). Das Drei-Punkte-Meter ist rein
 * dekorativ (`aria-hidden`), der ausgeschriebene Stufenname daneben ist der eigentliche,
 * screenreader-sichtbare Text (Barrierefreiheits-Grundsatz "Information nie nur ueber Farbe/Form").
 * Nur in der Detailansicht verwendet, nicht auf der Grid-Kachel.
 */
export function QualityMeter({ level, className }: QualityMeterProps) {
  return (
    <span className={className}>
      <span aria-hidden="true" className="text-text-h">
        {DOTS[level]}
      </span>{' '}
      {QUALITY_LEVEL_LABELS[level]}
    </span>
  )
}
