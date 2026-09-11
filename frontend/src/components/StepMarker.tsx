import { cn } from '../lib/utils'
import { Icon } from './ui/icon'

/**
 * Die vier Auspraegungen der Schrittmarke (Baustein `step-marker` in
 * `design/penpot/components.json`). "blockiert" ist eine AUSPRAEGUNG, kein Zustand - die Zustaende
 * des Bausteins sind normal/hover/active und kommen vom umschliessenden Bedienelement.
 */
export type StepMarkerAuspraegung = 'erledigt' | 'aktuell' | 'ausstehend' | 'blockiert'

/** Die vier Namen als Laufzeitwert - Grundlage der parametrisierten Tests, damit eine fuenfte
 * Auspraegung nicht ungeprueft hinzukommen kann (Muster wie ICON_NAMES in ui/icon.tsx). */
export const STEP_MARKER_AUSPRAEGUNGEN: readonly StepMarkerAuspraegung[] = [
  'erledigt',
  'aktuell',
  'ausstehend',
  'blockiert',
]

/*
 * DIE ERSTE VERWENDUNG DES `group`-MUSTERS IM PROJEKT - deshalb hier ausdruecklich erklaert: Der
 * Marker ist NICHT das Bedienelement. Ueberfahren und Gedruecktwerden passieren am umschliessenden
 * `<Link>` bzw. `<button>` in Stepper.tsx, das dafuer `group` traegt; der Marker drueckt sie als
 * `group-hover:`/`group-active:` aus. Der Zustandstraeger ist damit ueber zwei Dateien verteilt -
 * genau deshalb zeigt die `quellen`-Angabe des Bausteins auf DIESE Datei: der Zustandsscanner der
 * Penpot-Nutzlast liest sie, und er verlangt jeden hier getragenen Zustand als gefuehrte Achse.
 *
 * NICHT ZULAESSIG sind hier `aria-disabled:`-Varianten als Stilquelle: der Scanner verlangte dann
 * eine Achse `aria-disabled`, die der Entwurf nicht fuehrt. Die Sperrung ist eine Auspraegung.
 */

/**
 * Das Board-Navigationselement in seiner AKTIVEN Auspraegung - zeichengleich zur Markierung der
 * Projekt-Navigationsgruppe (ProjectNav.tsx), im Design-Vertrag aneinander gebunden. Bewusst ein
 * eigenes Literal, damit diese Bindung eine ganze Zeichenkette vergleichen kann.
 */
const AKTIV_RECIPE = 'border-accent bg-overlay font-bold text-accent'

/**
 * Dieselbe Vorlage in ihrer RUHENDEN Auspraegung, nur mit `group-`-praefixierten Zustaenden: die
 * Zustaende kommen vom umschliessenden Bedienelement, nicht vom Marker selbst. Der Design-Vertrag
 * leitet diese Fassung aus der Fassung in ProjectNav.tsx ab, statt sie ein zweites Mal zu tippen.
 */
// prettier-ignore
const RUHEND_RECIPE = 'border-border-control bg-surface text-text group-hover:bg-overlay group-hover:text-text-h group-active:bg-border group-active:text-text'

/*
 * Groesse: schmal ueber die volle Spaltenbreite gedehnt (`h-8 w-full`), ab `sm:` quadratisch
 * (`sm:size-8 sm:shrink-0`) mit der Beschriftung DANEBEN statt darin. Die Umrandung fasst damit
 * nur noch das Zeichen des Schritts, wie im Entwurf.
 *
 * `border` statt der 1.5px des Boards: 1.5px liegt auf keiner Tailwind-Stufe, und willkuerliche
 * Werte sind statisch verboten. Radius 8px (`rounded-md`) und Schriftstufe `text-xs` wie im
 * Baustein `step-marker` hinterlegt. Keine eigene Fokusdarstellung - der Fokus liegt am
 * umschliessenden Bedienelement, und die eine globale, abgesetzte Kontur traegt ihn dort.
 */
const BASE_CLASSES =
  'flex h-8 w-full items-center justify-center rounded-md border text-xs font-semibold ' +
  'transition-colors sm:size-8 sm:shrink-0'

const AUSPRAEGUNG_CLASSES: Record<StepMarkerAuspraegung, string> = {
  // Erledigt und ausstehend sind DIESELBE ruhende Flaeche - unterschieden werden sie durch die
  // Glyphe (Haken gegen Schrittnummer), nicht durch die Farbe.
  erledigt: RUHEND_RECIPE,
  ausstehend: RUHEND_RECIPE,
  // Aktiv: anliegender Akzentrand, Akzentschrift, fetter Schnitt - nie ueber Farbe allein, das
  // `aria-current="step"` am Bedienelement traegt mit. Die Flaeche steht bereits auf `--overlay`;
  // die Rueckmeldung beim Ueberfahren/Druecken geht deshalb eine Stufe weiter auf `--border`,
  // statt auf der Stelle zu treten.
  aktuell: cn(AKTIV_RECIPE, 'group-hover:bg-border group-active:bg-border'),
  // Blockiert: gedaempfter Umriss und gedaempfte Schrift, Schloss als Glyphe. Kein pauschales
  // `opacity` auf dem ganzen Element - so bleibt das Schloss selbst lesbar. Die Rueckmeldung beim
  // Ueberfahren bleibt, denn der gesperrte Schritt IST bedienbar: er oeffnet seinen Sperrgrund.
  // prettier-ignore
  blockiert: 'border-border bg-surface text-text-muted group-hover:bg-overlay group-hover:text-text-h group-active:bg-border group-active:text-text',
}

/**
 * Das Schloss ist bewusst KEIN dreizehntes Zeichen des Symbolsatzes: der Zwoelfer-Satz ist eine
 * belegte Ableitung aus dem Board, ein dreizehntes Zeichen haette diesen Beleg nicht. Es bleibt
 * deshalb ein dateilokales SVG und ist in `ui/icon.tsx` als benannte Luecke des Satzes gefuehrt.
 */
function LockIcon() {
  return (
    <svg viewBox="0 0 16 16" className="size-4" fill="none">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth={1.5} />
      <path
        d="M5 7V5a3 3 0 0 1 6 0v2"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
      />
    </svg>
  )
}

interface StepMarkerProps {
  auspraegung: StepMarkerAuspraegung
  /** Die Schrittnummer - Glyphe ueberall dort, wo weder Haken noch Schloss gilt. */
  nummer: number
  /**
   * Ob der Schritt erledigt ist. Wird normalerweise aus der Auspraegung abgeleitet und nur dort
   * gesetzt, wo beide Aussagen auseinanderfallen: ein erledigter Schritt, der inzwischen wieder
   * gesperrt ist, HEISST "blockiert" und zeigt trotzdem den Haken. Zustandsbenennung und
   * Glyphenwahl folgen zwei verschiedenen, je unveraenderten Rangfolgen (Edge Case 2 der Spec):
   * blockiert ▸ aktuell ▸ erledigt fuer den Namen, Haken vor Schloss fuer die Glyphe.
   */
  istErledigt?: boolean
}

/**
 * Die Schrittmarke der Pipeline-Schrittleiste (Baustein `step-marker` des Entwurfs) - rein
 * praesentational: kein Zustand, kein Routing, kein eigener zugaenglicher Name. Der Name des
 * Schritts samt seiner Zustandsangabe steht am umschliessenden Bedienelement in Stepper.tsx.
 */
export function StepMarker({
  auspraegung,
  nummer,
  istErledigt = auspraegung === 'erledigt',
}: StepMarkerProps) {
  const glyphe = istErledigt ? 'haken' : auspraegung === 'blockiert' ? 'schloss' : 'nummer'

  return (
    <span
      // Semantischer Haken im Stil der bestehenden data-icon/data-status-Konvention: die Tests
      // selektieren darueber statt ueber einen Klassennamen.
      data-step-state={auspraegung}
      className={cn(BASE_CLASSES, AUSPRAEGUNG_CLASSES[auspraegung])}
    >
      {/* GENAU EINE Glyphe, und zwar von Bauart wegen: ein einziger Knoten traegt sie, die
          Fallunterscheidung waehlt nur ihren Inhalt. Rein dekorativ - die Aussage steht
          vollstaendig im zugaenglichen Namen des Bedienelements. */}
      <span data-glyph={glyphe} aria-hidden="true" className="flex items-center justify-center">
        {glyphe === 'haken' ? (
          <Icon name="check" size={16} />
        ) : glyphe === 'schloss' ? (
          <LockIcon />
        ) : (
          nummer
        )}
      </span>
    </span>
  )
}
