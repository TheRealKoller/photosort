import type { PhotoOut } from '../api/types'
import { formatDateTime } from '../utils/formatStats'
import { eventPlaceName } from '../utils/timeOfDay'
import { formatTimeOffset } from '../utils/timeOffset'

interface PhotoCaptureFactsProps {
  photo: Pick<
    PhotoOut,
    'taken_at' | 'taken_at_original' | 'time_offset_minutes' | 'camera' | 'event'
  >
  /** Stufe der Ueberschrift „Aufnahmezeit" - sie haengt an der Gliederung des Aufrufers. */
  headingLevel: 'h2' | 'h3'
}

/**
 * Die Aufnahmeangaben eines Fotos: Aufnahmezeit mit Korrekturzeile, Kamera und Ort. Eine
 * Renderstelle fuer Bilddetailseite und Großansicht.
 */
export function PhotoCaptureFacts({ photo, headingLevel: Heading }: PhotoCaptureFactsProps) {
  // Der Ort eines Fotos ist der Ort seines EREIGNISSES. Wie Name und Ortsname zusammengesetzt
  // werden, steht in `utils/timeOfDay.ts::eventPlaceName` und entsteht hier ausdruecklich NICHT ein
  // zweites Mal - sonst liefe die Zeile mit der Ereignis-Ueberschrift auseinander. Ohne Ortsangabe
  // steht der Satz statt einer Luecke; eine Koordinate erscheint nie als Name.
  const placeName = photo.event ? eventPlaceName(photo.event) : null

  return (
    <section className="flex flex-col gap-1 text-sm" data-testid="taken-at-section">
      <Heading className="text-xs font-semibold tracking-wide text-text-h uppercase">
        Aufnahmezeit
      </Heading>
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-text">{formatDateTime(photo.taken_at)}</span>
        {/* Die Marke NUR im Korrekturfall, im zurueckhaltenden Metadatenton: eine Korrektur
            ist der GEWOLLTE Zustand, kein Alarm. */}
        {photo.time_offset_minutes !== 0 && (
          <span className="text-xs text-text-muted" data-corrected="true">
            korrigiert
          </span>
        )}
      </p>
      {/* Die zweite Zeile nur im Korrekturfall - bei Versatz `0` wäre sie eine Wiederholung
          derselben Zeit und damit eine Aussage ohne Inhalt. */}
      {photo.time_offset_minutes !== 0 && (
        <p className="text-xs text-text-muted">
          aufgezeichnet <span className="font-mono">{formatDateTime(photo.taken_at_original)}</span>{' '}
          · {formatTimeOffset(photo.time_offset_minutes)}
        </p>
      )}
      {/* Ist keine Kamera bestimmbar, steht das als RUHIGER SATZ da und nicht als Fehlen. */}
      <p className="text-xs text-text-muted">
        {photo.camera === null
          ? 'Die Kamera dieses Fotos ist nicht bestimmbar.'
          : photo.camera.label}
      </p>
      {/* DER ORT - Name und Ortsname, OHNE Zeitspanne: die Aufnahmezeit steht direkt darueber,
          und eine zweite Zeitangabe daneben waere eine Wiederholung. Ohne Ortsangabe steht der
          Satz statt einer Luecke.

          S2 - RENDERSTELLE ZWEIER FREMDTEXTFELDER: `place.landmark_name` (Modellantwort) und
          `place_name` (Ortsdatensatz Dritter), in EINEM Wert, den `eventPlaceName` bildet. Reiner
          React-Textknoten, nie `dangerouslySetInnerHTML`, nie in `href`/`src`/`style`. Bricht in
          `PhotoDetailPage.test.tsx > rendert einen feindlich belegten Ortsnamen aus $name als
          reinen Textknoten`. */}
      <p className="text-xs text-text-muted" data-testid="place-line">
        {placeName ?? 'nicht bestimmbar'}
      </p>
    </section>
  )
}
