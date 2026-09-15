import type { ReactNode } from 'react'

import type { DuplicateDecision, PhotoOut } from '../api/types'
import { cn } from '../lib/utils'
import { PhotoImage } from './PhotoImage'
import { Button } from './ui/button'
import { Icon, type IconName } from './ui/icon'

/**
 * Die ZWEI Zustände einer Aufnahme in der Vergleichsansicht — je Zustand ein eigener Wert, ein
 * eigener sichtbarer Text und ein eigenes Symbol.
 *
 * DIE DREIFACHE CODIERUNG IST DIE ZUSAGE, nicht die Farbe: In Graustufen liegen die
 * Umrissfarben dicht beieinander, und ein Zustand, den nur der Umriss trägt, ist ohne
 * Farbwahrnehmung nicht ablesbar.
 *
 * ES GIBT KEINEN DRITTEN EINTRAG. „Noch offen" ist kein Zustand mehr: Die Ansicht zeigt die
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

export interface DuplicatePhotoTileProps {
  photo: PhotoOut
  /** Der Zustand, der ohne weiteres Zutun eintritt — nicht die gespeicherte Entscheidungszeile.
   * Ob er vom System oder vom Nutzer stammt, weiß die Kachel nicht und zeigt sie nicht. */
  effectiveDecision: DuplicateDecision
  /** Ob „behalten" hier überhaupt etwas bewirken kann. Bei `false` rendert die Kachel KEINE
   * Wahlschaltflächen und zeigt stattdessen den Grund. */
  keepPossible: boolean
  enlarged: boolean
  /** true, solange die Entscheidung DIESER Aufnahme läuft. Andere Kacheln bleiben bedienbar. */
  deciding: boolean
  onToggle: () => void
  onDecide: (decision: DuplicateDecision) => void
  /** Die Bedienleiste der Vergrößerung (Vor/Zurück/Schließen) — von der Seite gestellt, weil
   * Blättern eine Aussage über die GRUPPE ist und nicht über diese eine Aufnahme. */
  controls?: ReactNode
}

/**
 * EINE Aufnahme der Duplikat-Gruppe.
 *
 * KEIN Aufbau auf `PhotoCard`/`CurationPhotoTile`/`RatingBadge`: Deren Vokabular ist die
 * Albumentscheidung eines Nutzers. Hier steht die andere Frage — ob die Aufnahme den
 * Ausschuss-Schritt überlebt —, und ein geteilter Baustein machte die beiden an jeder Lesestelle
 * verwechselbar.
 *
 * ALLE MITGLIEDER SIND GLEICHRANGIG: Diese eine Komponente rendert jedes von ihnen, und keines
 * trägt eine Auszeichnung als Gewinner, Original oder Vorgeschlagener. Die Kachel weiß nicht,
 * welche Rolle ihre Aufnahme im Stern hat, und kann sie deshalb auch nicht zeigen. Der Zustand,
 * den sie zeigt, ist keine solche Auszeichnung — er sagt, was ohne Zutun geschieht.
 *
 * DIE BILDFLÄCHE IST EIN NATIVES `<button>` — Enter und Leertaste wirken ohne eigenen
 * Tastatur-Handler, und der zugängliche Name nennt die Aktion samt Dateiname. Die Wahlzeile liegt
 * daneben, nie darin: verschachtelte Schaltflächen sind kein gültiges HTML.
 */
export function DuplicatePhotoTile({
  photo,
  effectiveDecision,
  keepPossible,
  enlarged,
  deciding,
  onToggle,
  onDecide,
  controls,
}: DuplicatePhotoTileProps) {
  const zustand = DUPLICATE_ZUSTAENDE[effectiveDecision]
  // Die Dämpfung gilt AUSSCHLIESSLICH in der Übersicht: Die vergrößerte Aufnahme bleibt
  // unverfälscht, weil sie beurteilt werden soll.
  const gedaempft = effectiveDecision === 'discard' && !enlarged

  return (
    <li
      data-duplicate-decision={effectiveDecision}
      className={cn(
        'flex flex-col gap-3 rounded-lg bg-elevated p-2 sm:p-3',
        zustand.rahmen,
        enlarged && 'col-span-full',
      )}
    >
      {/* Die Bildfläche beschneidet - Trefferflächen-Utilities haben hier nichts zu suchen, sie
          würden still abgeschnitten. Sie ist ohnehin deutlich größer als 44px. */}
      <button
        type="button"
        onClick={onToggle}
        aria-label={`${photo.relative_path} ${enlarged ? 'verkleinern' : 'vergrößern'}`}
        data-testid="duplicate-image"
        /* `data-dimmed` steht IMMER, nie bloß im gedämpften Fall: Ein fehlendes Attribut wäre von
           „nicht gedämpft" nicht zu unterscheiden, und der Prüfstack kann den berechneten
           Deckkraftwert sonst gegen keine Absicht halten. Die tatsächliche Dämpfung hängt an
           genau diesem einen `opacity-*` an der BILDFLÄCHE — am Kachelkörper drückte dieselbe
           Utility Kennzeichen und Dateinamen unter die Kontrastschwelle. */
        data-dimmed={gedaempft ? 'true' : 'false'}
        /* BEIDE ZUSTÄNDE RESERVIEREN IHRE HÖHE, BEVOR DAS BILD DA IST — `h-96` in der
           Vergrößerung, nicht `max-h-96`. Die Bildfläche lädt über einen authentifizierten Abruf
           und trifft damit immer erst nach dem ersten Rendern ein; ohne reservierte Höhe ist die
           vergrößerte Kachel bis dahin 145px hoch und wächst beim Eintreffen um 384px. Alles
           darunter rutscht dann aus dem Sichtbereich, nachdem bereits gescrollt wurde — die
           übrige Gruppe verschwindet, und die Vergrößerung ist faktisch doch ein Vollbild
           (`e2e/tests/grid-columns.spec.ts`, „laesst die Gruppe im Blick"). */
        className={cn(
          'block w-full overflow-hidden rounded-md',
          enlarged ? 'h-96' : 'aspect-square',
          gedaempft && 'opacity-40',
        )}
      >
        <PhotoImage
          photoId={photo.id}
          /* In der Vergrößerung die große Variante: Dort wird beurteilt, und ein hochskaliertes
             Vorschaubild entschiede die Frage nach der Schärfe falsch. */
          variant={enlarged ? 'display' : 'thumbnail'}
          alt={photo.relative_path}
          className={cn('size-full', enlarged ? 'object-contain' : 'object-cover')}
        />
      </button>

      <div className="flex items-center justify-between gap-2">
        <span
          data-testid="duplicate-state"
          className={cn('flex items-center gap-1 text-xs', zustand.schrift)}
        >
          <Icon name={zustand.icon} size={14} />
          {zustand.text}
        </span>
        {/* Nur der Basisname, außerhalb jeder Trefferfläche. Extern entstandener Text,
            ausschließlich als React-Textknoten. */}
        <span className="min-w-6 truncate font-mono text-xs text-text-muted">
          {photo.relative_path.split('/').pop()}
        </span>
      </div>

      {/* ZWEI Trefferflächen mit 12px Abstand (`gap-3`) - die Pflichtgrenze zwischen
          aufgespannten Bedienelementen, kein Gestaltungsspielraum: In einer Überlappung gewinnt
          das obenliegende Element, und ein Fehlgriff schreibt hier, welche Bilder den Homeserver
          verlassen.

          KEINE DRITTE SCHALTFLÄCHE: Eine Rücknahme nach „noch nicht entschieden" gibt es nicht,
          und die Ansicht bietet sie deshalb auch nicht an. `aria-pressed` folgt dem WIRKSAMEN
          Zustand, nicht einer gespeicherten Zeile; beide zugänglichen Namen tragen den Dateinamen,
          sonst hießen im selben Raster alle Schaltflächen gleich.

          BEI `keepPossible === false` STEHT HIER GAR KEINE WAHL, auch nicht „Ausschuss": Kein
          Wert der Entscheidungszeile ändert den Zustand dieser Aufnahme, und ein angenommener
          Klick bliebe still wirkungslos. Bewusst NICHT `disabled` — „nicht anwendbar" ist etwas
          anderes als „kurzzeitig gesperrt", und ein gesperrter Knopf verspräche, später zu
          wirken. */}
      {keepPossible ? (
        <div className="flex gap-3">
          {(['keep', 'discard'] as const).map((wert) => (
            <Button
              key={wert}
              type="button"
              variant="outline"
              size="sm"
              className="flex-1"
              aria-pressed={effectiveDecision === wert}
              disabled={deciding}
              busy={deciding && effectiveDecision !== wert}
              aria-label={`${DUPLICATE_ZUSTAENDE[wert].text}: ${photo.relative_path}`}
              onClick={() => onDecide(wert)}
            >
              {DUPLICATE_ZUSTAENDE[wert].text}
            </Button>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted">{DUPLICATE_IMMUTABLE_TEXT}</p>
      )}

      {enlarged && controls}
    </li>
  )
}
