import type { RatingStatus } from '../api/types'
import { PhotoImage } from './PhotoImage'
import { RatingButtons } from './RatingButtons'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

interface PhotoDetailStageProps {
  /** `loading` und `error` rendern DENSELBEN Rahmen wie `ready` - siehe Doku-Block unten. */
  status: 'ready' | 'loading' | 'error'
  /** Die Stelle in der Reihe, z.B. "3/57". `null`, solange sie unbekannt ist. */
  counter: string | null
  /** `null` in den Zuständen ohne Foto. */
  photoId: number | null
  altText: string
  errorText?: string
  onRetry?: () => void
  currentStatus: RatingStatus | null
  favorite: boolean
  onToggle: (status: RatingStatus) => void
  onToggleFavorite: () => void
  ratingDisabled: boolean
  ratingBusy: boolean
  onPrev: () => void
  onNext: () => void
  prevDisabled: boolean
  nextDisabled: boolean
  onTouchStart?: (event: React.TouchEvent<HTMLDivElement>) => void
  onTouchEnd?: (event: React.TouchEvent<HTMLDivElement>) => void
}

/** Der Hinweis auf die Tastenbelegung. Er steht IN der Bühne und nicht darüber: Über der Bühne
 *  schöbe jedes Element sie um seine eigene Höhe nach unten, und ihre Unterkante fiele um genau
 *  diesen Betrag unter den Sichtrand - AK2 wäre damit verfehlt. Unter der Bühne stünde er im
 *  Informationsteil („was das System über dieses Foto weiß"), und über das Foto sagt er nichts. */
const SHORTCUT_TEXT = 'Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren'

/**
 * AUF TELEFONBREITE AUSGEBLENDET, erst ab `sm:` sichtbar.
 *
 * Der Satz nennt Tasten. Auf einem Telefon gibt es keine, dort nützt er also nichts - er bricht
 * aber auf 360 px mehrzeilig um und nimmt der Fotofläche genau diese Höhe. Das Ziel der Ansicht ist
 * "das Foto so groß wie möglich"; jede Zeile, die nichts trägt, geht direkt davon ab.
 *
 * KEIN VERSTOSS GEGEN AK9a: Ausgeblendet wird ein Hinweis, nicht ein Abschnitt. Die
 * Abschnittsfolge bleibt auf beiden Prüfbreiten dieselbe, es entsteht keine breitengebundene
 * `order-*`-Utility, kein `*-reverse` und keine viewport-abhängige Verzweigung im Rendering - das
 * Element steht in beiden Breiten im Dokument, nur seine Sichtbarkeit folgt der Breite.
 * `e2e/tests/bilddetail-buehne.spec.ts` misst beide Breiten gegen dieselbe Schwelle.
 */
const SHORTCUT_VISIBILITY = 'hidden sm:block'

/**
 * Die Bühne der Bilddetailansicht: Kopfzeile mit Zähler, Fotofläche, Bewertungsleiste,
 * Navigation. Sie trägt die gesamte Höhengeometrie und bekommt Zustand und Handler als Props -
 * SIE ENTSCHEIDET NICHTS SELBST. Datenzugriff, Navigation (Pfeiltasten, Wischen, Auto-Advance) und
 * Bewertungs-Mutationen bleiben ausschließlich in `pages/PhotoDetailPage.tsx`.
 *
 * DIE HÖHE HÄNGT AM SICHTFENSTER, NIE AM BILD (AK2/AK10). Die Bühne ist ein Flex-Spalten-Behälter
 * mit `h-[calc(100dvh-var(--spacing-header)-var(--spacing)*6)]`: sichtbare Höhe abzüglich
 * Kopfzeile und des oberen Innenabstands der Inhaltsspalte (`py-6` an `main` in `App.tsx`). Die
 * Kopfzeilenhöhe kommt aus demselben `--spacing-header`, aus dem `h-header`/`top-header`
 * entstehen; ein zweiter Zahlenwert dafür ist verboten.
 *
 * Kopfzeile, Bewertungsleiste und Navigation behalten ihre inhaltsbestimmte Höhe, die Fotofläche
 * nimmt mit `flex-1 min-h-0` den Rest. Das Bild steht darin als `h-full w-full object-contain` -
 * vollständig, nie beschnitten, weder auf Breite noch auf Höhe festgelegt und damit auf
 * Telefonbreite von selbst höhengeführt. KEINE MINDESTHÖHE auf der Fotofläche: Bei einem sehr
 * flachen Fenster schrumpft das Bild, statt die Bedienleiste hinauszuschieben. Ein
 * breitengeführtes Bild (`aspect-*`) fiele durch - es machte die Bühne je Format verschieden hoch
 * und schöbe beim Hochformat die Bewertungsleiste aus dem Bild.
 *
 * KEINE IN JAVASCRIPT GEMESSENE HÖHE und kein gerechneter Wert in einem Inline-Stil: Beide
 * Auswege - der Inline-Stil wie die CSS-Custom-Property als Träger eines gerechneten Wertes - sind
 * im Sicherheitskonzept untersagt. Der willkürliche Klassenwert ist stattdessen im Design-Vertrag
 * (`designSystem.contract.test.ts`) fundstellengenau freigegeben.
 *
 * ALLE DREI ZUSTÄNDE TRAGEN DENSELBEN RAHMEN. `ladend` zeigt einen Platzhalter in der Fotofläche
 * statt eines vorgezogenen Satzes, `fehler` einen `Alert` darin; Bewertung und Navigation bleiben
 * in beiden sichtbar, aber gesperrt. Ein vorgezogener Satz ließe die Seite beim Eintreffen der
 * Daten springen - die „Bewegung von Layout oder Position", die das Design-System ausschließt.
 */
export function PhotoDetailStage({
  status,
  counter,
  photoId,
  altText,
  errorText,
  onRetry,
  currentStatus,
  favorite,
  onToggle,
  onToggleFavorite,
  ratingDisabled,
  ratingBusy,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  onTouchStart,
  onTouchEnd,
}: PhotoDetailStageProps) {
  const inactive = status !== 'ready'

  return (
    <div
      data-testid="photo-detail-stage"
      className="flex h-[calc(100dvh-var(--spacing-header)-var(--spacing)*6)] flex-col gap-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3 text-xs text-text-muted">
        {/* Bleibt unveraendert stehen (es wird nichts entfernt): durch die Tasten-Kaestchen der
            Bewertungsleiste teilweise redundant, aber der Pfeiltasten-Teil hat kein sichtbares
            Gegenstueck. Nur als Metadatenzeile gesetzt statt als Fliesstext. */}
        <p className={SHORTCUT_VISIBILITY}>{SHORTCUT_TEXT}</p>
        {counter !== null && <p>{counter}</p>}
      </div>

      {/* `min-h-0` ist nicht optional: Ohne es bekaeme das Flex-Kind seine Inhaltsgroesse als
          Mindesthoehe und schoebe Bewertungsleiste und Navigation aus dem Sichtfenster - genau der
          Fehlermodus, den AK2 ausschliesst. */}
      <div
        data-testid="photo-detail-stage-photo"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        className="relative min-h-0 flex-1"
      >
        {status === 'error' ? (
          <div className="flex h-full w-full items-center justify-center">
            <Alert onRetry={onRetry}>{errorText ?? 'Fehler beim Laden der Fotos.'}</Alert>
          </div>
        ) : status === 'loading' || photoId === null ? (
          <Skeleton
            data-testid="photo-detail-stage-placeholder"
            className="h-full w-full rounded-md"
          />
        ) : (
          /* `object-contain` schlaegt per tailwind-merge das `object-cover` des Bausteins. Weder
             Breite noch Hoehe sind festgelegt - `h-full w-full` fuellt den Kasten, `object-contain`
             passt das Bild vollstaendig darin ein. */
          <PhotoImage
            photoId={photoId}
            variant="display"
            alt={altText}
            className="h-full w-full rounded-md object-contain"
          />
        )}
      </div>

      {/* Unmittelbar unter dem Foto: die primaere, haeufigste Handlung. role="group" mit
          aria-label="Bewertung" bleibt unveraendert - die Leiste wandert nur in diesen Baustein. */}
      <RatingButtons
        currentStatus={currentStatus}
        favorite={favorite}
        onToggle={onToggle}
        onToggleFavorite={onToggleFavorite}
        disabled={ratingDisabled || inactive}
        busy={ratingBusy}
      />

      <div className="flex justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          aria-label="Vorheriges Foto"
          onClick={onPrev}
          disabled={prevDisabled || inactive}
        >
          Zurück
        </Button>
        <Button
          type="button"
          variant="outline"
          aria-label="Nächstes Foto"
          onClick={onNext}
          disabled={nextDisabled || inactive}
        >
          Weiter
        </Button>
      </div>
    </div>
  )
}
