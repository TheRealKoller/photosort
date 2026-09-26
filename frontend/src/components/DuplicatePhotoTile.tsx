import type { Ref } from 'react'

import type { DuplicateDecision, PhotoOut } from '../api/types'
import { cn } from '../lib/utils'
import { formatExposure, formatSharpness } from '../utils/duplicateMetrics'
import { PhotoImage } from './PhotoImage'
import { Button } from './ui/button'
import { Icon, type IconName } from './ui/icon'

/**
 * Die ZWEI Zustände einer Aufnahme in der Vergleichsansicht — je Zustand ein eigener Wert, ein
 * eigener sichtbarer Text und ein eigenes Symbol.
 *
 * DIE DREIFACHE CODIERUNG IST DIE ZUSAGE, nicht die Farbe: In Graustufen liegen die
 * Umrissfarben dicht beieinander, und ein Zustand, den nur der Umriss trägt, ist ohne
 * Farbwahrnehmung nicht ablesbar. Helligkeit trägt ihn nie — beide Zustände zeigen das Bild
 * unverfälscht.
 *
 * ES GIBT KEINEN DRITTEN EINTRAG. „Noch offen" ist kein Zustand: Die Ansicht zeigt die
 * Auswertung des Überlebens-Prädikats, und jede Aufnahme trägt beim Öffnen bereits das, was ohne
 * weiteres Zutun eintritt (ADR 0111). Exportiert, damit die Schlüsselmenge selbst prüfbar ist.
 */
export const DUPLICATE_ZUSTAENDE: Record<
  DuplicateDecision,
  { text: string; icon: IconName; rahmen: string; schrift: string }
> = {
  keep: {
    text: 'Behalten',
    icon: 'check',
    rahmen: 'border-2 border-accent',
    schrift: 'text-accent',
  },
  discard: {
    text: 'Ausschuss',
    icon: 'x-circle',
    rahmen: 'border-2 border-danger',
    // `--danger-text`, nie `--danger`: der grafische Ton hält als Fließtext kein AA.
    schrift: 'text-danger-text',
  },
}

/**
 * Der feste Text bei `keepPossible === false`.
 *
 * Der Grund reist nicht als Feld der Antwort: Er folgt aus der Bedingung selbst
 * (`duplicate_of IS NULL` ist genau das, woran der Server `low_quality` festmacht). Entstünde ein
 * dritter Ablehnungsgrund, trüge `keepPossible === false` seine Begründung nicht mehr eindeutig —
 * der Grund wird dann ein eigenes Feld, statt dass dieser Text weiter behauptet, was nicht gilt.
 * Ein Backend-Test hält die Äquivalenz fest, damit das laut auffällt statt still.
 */
export const DUPLICATE_IMMUTABLE_TEXT =
  'Abgelehnt wegen geringer Bildqualität — lässt sich nicht ändern.'

/** Zustandskennzeichen aus Symbol und Wort — auf der Karte und in der Seitenspalte. */
export function DuplicateStateLabel({ decision }: { decision: DuplicateDecision }) {
  const zustand = DUPLICATE_ZUSTAENDE[decision]
  return (
    <span
      data-testid="duplicate-state"
      className={cn('flex items-center gap-1 text-xs', zustand.schrift)}
    >
      <Icon name={zustand.icon} size={14} />
      {zustand.text}
    </span>
  )
}

/**
 * Die Bewertungszeile (A7): Schärfe immer, Belichtung nur mit Wert.
 *
 * Die Werte kommen aus `sharpness`/`exposure` der Gruppenantwort, NIE aus `PhotoOut.suggestion` —
 * jenes Feld fällt nach jeder Entscheidung auf `null`. Die Auszeichnung ist nur ein Wort: kein
 * Akzent (der heißt hier „Behalten"), kein Symbol, kein Rahmen, und sie ändert nichts an Zustand
 * oder Wahl.
 */
export function DuplicateMetrics({
  sharpness,
  exposure,
  bestSharpness,
  bestExposure,
}: {
  sharpness: number | null
  exposure: number | null
  bestSharpness: boolean
  bestExposure: boolean
}) {
  return (
    <dl className="flex flex-col gap-1 text-xs">
      <div className="flex flex-wrap gap-x-1">
        <dt className="text-text-muted">Schärfe</dt>
        <dd className="text-text">
          {formatSharpness(sharpness)}
          {bestSharpness && <span className="font-semibold text-text-h"> — schärfste</span>}
        </dd>
      </div>
      {exposure !== null && (
        <div className="flex flex-wrap gap-x-1">
          <dt className="text-text-muted">Belichtung</dt>
          <dd className="text-text">
            {formatExposure(exposure)}
            {bestExposure && <span className="font-semibold text-text-h"> — beste Belichtung</span>}
          </dd>
        </div>
      )}
    </dl>
  )
}

/**
 * Die Wahlzeile — oder, bei `keepPossible === false`, der Grund an ihrer Stelle.
 *
 * ZWEI Trefferflächen mit 12px Abstand (`gap-3`) — die Pflichtgrenze zwischen aufgespannten
 * Bedienelementen: In einer Überlappung gewinnt das obenliegende Element, und ein Fehlgriff
 * schreibt hier, welche Bilder den Homeserver verlassen. Heißer Pfad: am Telefon sichtbar 44px.
 * Ist die Karte schmal, brechen die Schaltflächen untereinander um, statt überzulaufen.
 *
 * KEINE DRITTE SCHALTFLÄCHE: Eine Rücknahme nach „noch nicht entschieden" gibt es nicht.
 * `aria-pressed` folgt dem WIRKSAMEN Zustand; die gedrückte Schaltfläche trägt zusätzlich ihr
 * Symbol. Beide zugänglichen Namen tragen den Dateinamen, sonst hießen im selben Raster alle
 * Schaltflächen gleich.
 *
 * BEI `keepPossible === false` STEHT HIER GAR KEINE WAHL, auch nicht „Ausschuss": Kein Wert der
 * Entscheidungszeile ändert den Zustand, und ein angenommener Klick bliebe still wirkungslos.
 * Bewusst NICHT `disabled` — ein gesperrter Knopf verspräche, später zu wirken.
 */
export function DuplicateChoice({
  photo,
  effectiveDecision,
  keepPossible,
  deciding,
  onDecide,
}: {
  photo: PhotoOut
  effectiveDecision: DuplicateDecision
  keepPossible: boolean
  deciding: boolean
  onDecide: (decision: DuplicateDecision) => void
}) {
  if (!keepPossible) {
    return <p className="text-xs text-text-muted">{DUPLICATE_IMMUTABLE_TEXT}</p>
  }
  return (
    <div role="group" aria-label={`Wahl: ${photo.relative_path}`} className="flex flex-wrap gap-3">
      {(['keep', 'discard'] as const).map((wert) => (
        <Button
          key={wert}
          type="button"
          variant="outline"
          size="sm"
          className="h-11 grow sm:h-8"
          aria-pressed={effectiveDecision === wert}
          disabled={deciding}
          busy={deciding && effectiveDecision !== wert}
          aria-label={`${DUPLICATE_ZUSTAENDE[wert].text}: ${photo.relative_path}`}
          onClick={() => onDecide(wert)}
        >
          {effectiveDecision === wert && <Icon name={DUPLICATE_ZUSTAENDE[wert].icon} size={14} />}
          {DUPLICATE_ZUSTAENDE[wert].text}
        </Button>
      ))}
    </div>
  )
}

export interface DuplicatePhotoTileProps {
  photo: PhotoOut
  /** Der Zustand, der ohne weiteres Zutun eintritt — nicht die gespeicherte Entscheidungszeile.
   * Ob er vom System oder vom Nutzer stammt, weiß die Kachel nicht und zeigt sie nicht. */
  effectiveDecision: DuplicateDecision
  /** Ob „behalten" hier überhaupt etwas bewirken kann. Bei `false` rendert die Kachel KEINE
   * Wahlschaltflächen und zeigt stattdessen den Grund. */
  keepPossible: boolean
  sharpness: number | null
  exposure: number | null
  /** Auszeichnungen über den ANGEZEIGTEN Werten der ganzen Gruppe — gebildet von der Seite. */
  bestSharpness: boolean
  bestExposure: boolean
  /** true, solange die Entscheidung DIESER Aufnahme läuft. Andere Kacheln bleiben bedienbar. */
  deciding: boolean
  onOpen: () => void
  onDecide: (decision: DuplicateDecision) => void
  /** Die Bildfläche — die Seite setzt dorthin den Fokus zurück, wenn die Großansicht schließt. */
  imageRef?: Ref<HTMLButtonElement>
}

/**
 * EINE Aufnahme der Duplikat-Gruppe als Karte des Rasters.
 *
 * KEIN Aufbau auf `PhotoCard`/`CurationPhotoTile`/`RatingBadge`: Deren Vokabular ist die
 * Albumentscheidung eines Nutzers. Hier steht die andere Frage — ob die Aufnahme den
 * Ausschuss-Schritt überlebt —, und ein geteilter Baustein machte die beiden an jeder Lesestelle
 * verwechselbar.
 *
 * ALLE MITGLIEDER SIND GLEICHRANGIG: Keine Karte trägt eine Auszeichnung als Gewinner, Original
 * oder Vorgeschlagener. Der Zustand, den sie zeigt, sagt, was ohne Zutun geschieht.
 *
 * ALLES STEHT GLEICHZEITIG DA (A4): Bildfläche, Dateiname, Zustandskennzeichen, Bewertungszeile
 * und Wahl — nichts liegt hinter einem Aufklappen.
 *
 * DIE BILDFLÄCHE IST EIN NATIVES `<button>` und öffnet die Großansicht. Die Wahlzeile liegt
 * daneben, nie darin: verschachtelte Schaltflächen sind kein gültiges HTML.
 */
export function DuplicatePhotoTile({
  photo,
  effectiveDecision,
  keepPossible,
  sharpness,
  exposure,
  bestSharpness,
  bestExposure,
  deciding,
  onOpen,
  onDecide,
  imageRef,
}: DuplicatePhotoTileProps) {
  return (
    <li
      data-duplicate-decision={effectiveDecision}
      className={cn(
        'flex flex-col gap-3 rounded-lg bg-elevated p-2 sm:p-3',
        DUPLICATE_ZUSTAENDE[effectiveDecision].rahmen,
      )}
    >
      {/* Die Bildfläche beschneidet - Trefferflächen-Utilities haben hier nichts zu suchen, sie
          würden still abgeschnitten. Sie ist ohnehin deutlich größer als 44px.

          JEDE AUFNAHME STEHT IN VOLLER HELLIGKEIT, in beiden Zuständen (A6): Hier liegen
          ähnliche Aufnahmen nebeneinander, und genau ihr Helligkeits- und Qualitätsunterschied
          soll beurteilt werden. Den Zustand tragen Rahmen und Kennzeichen außerhalb des Bildes.

          `aspect-square` reserviert die Höhe, bevor das authentifiziert geladene Bild eintrifft. */}
      <button
        ref={imageRef}
        type="button"
        onClick={onOpen}
        aria-label={`${photo.relative_path} vergrößern`}
        data-testid="duplicate-image"
        className="block aspect-square w-full overflow-hidden rounded-md"
      >
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt={photo.relative_path}
          className="size-full object-cover"
        />
      </button>

      <div className="flex items-center justify-between gap-2">
        <DuplicateStateLabel decision={effectiveDecision} />
        {/* Nur der Basisname, außerhalb jeder Trefferfläche. Extern entstandener Text,
            ausschließlich als React-Textknoten. */}
        <span className="min-w-6 truncate font-mono text-xs text-text-muted">
          {photo.relative_path.split('/').pop()}
        </span>
      </div>

      <DuplicateMetrics
        sharpness={sharpness}
        exposure={exposure}
        bestSharpness={bestSharpness}
        bestExposure={bestExposure}
      />

      <DuplicateChoice
        photo={photo}
        effectiveDecision={effectiveDecision}
        keepPossible={keepPossible}
        deciding={deciding}
        onDecide={onDecide}
      />
    </li>
  )
}
