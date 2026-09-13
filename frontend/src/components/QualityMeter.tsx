import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import type { QualityLevel } from '../utils/qualityLevel'
import { QUALITY_LEVEL_LABELS } from '../utils/qualityLevel'

const DOTS: Record<QualityLevel, string> = {
  high: '●●●',
  medium: '●●○',
  low: '●○○',
}

interface QualityMeterProps {
  /** `null` heißt „noch nicht bewertet" - kein Modellurteil, NICHT die schlechteste Stufe. */
  level: QualityLevel | null
  className?: string
}

/**
 * Grobe, verstaendliche 3-Stufen-Einordnung der ALBUMTAUGLICHKEIT statt eines Rohwerts - bewusst
 * kein Stern-Symbol (Kollision mit dem `favorite`-★) und keine Prozess-Status-Farbe. Das
 * Drei-Punkte-Meter ist rein dekorativ (`aria-hidden`), der ausgeschriebene Stufenname daneben
 * ist der eigentliche, screenreader-sichtbare Text (Barrierefreiheits-Grundsatz "Information nie
 * nur ueber Farbe/Form"). Das gilt auch fuer den Satz „Noch nicht bewertet".
 *
 * OHNE STUFE ERSCHEINT KEIN GLYPH. `●○○` oder `○○○` hiesse "schlechteste Stufe" statt "nicht
 * beurteilt" - und das Foto ist weder aussortiert noch fehlerhaft, sondern schlicht noch nicht
 * vom Modell gesehen.
 *
 * DIE FORM IST BEWUSST SCHMUCKLOS: die Modellaussage darf nie die Form des
 * Bewertungs-Kennzeichens „Album-würdig" annehmen (keine Badge, keine Bewertungsfarbe, kein
 * `book`-Symbol, keine gefüllte Fläche). Sonst lägen die Entscheidung eines Menschen und die
 * Schätzung eines Modells in derselben Form und Farbe auf einer Kachel.
 */
export function QualityMeter({ level, className }: QualityMeterProps) {
  if (level === null) {
    return <span className={className}>{ALBUM_SUITABILITY_NOT_RATED_TEXT}</span>
  }
  return (
    <span className={className}>
      <span aria-hidden="true" data-quality-meter-dots="" className="text-text-h">
        {DOTS[level]}
      </span>{' '}
      {QUALITY_LEVEL_LABELS[level]}
    </span>
  )
}
