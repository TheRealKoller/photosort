import type { CategoryKey } from '../api/types'
import { categoryAbbreviation, formatCategoryKey, type CategorySet } from '../utils/categoryLabels'
import { cn } from '../lib/utils'

interface CategoryBadgeProps {
  categoryKey: CategoryKey
  /** Das ueber `GET /categories` geladene Set (specs/features/0289-feste-kategorien.md) - liefert
   * Anzeigename und Kuerzel. Darf leer sein, solange das Set noch laedt; dann greift der
   * generische Fallback, das Badge bleibt lesbar statt leer. */
  categories: CategorySet
  className?: string
}

/*
 * Die dreizehn Chip-Farbpaare, geschluesselt nach `category_key`
 * (decisions/0055-dark-utility-register-fundament.md Punkt 6). Vollstaendig ausgeschriebene
 * Klassennamen, kein Zusammenbauen per Template-String - Tailwind erkennt Utility-Klassen nur als
 * statische, vollstaendige Strings; dieselbe Regel wie in ui/badge.tsx, statisch erzwungen in
 * src/designSystem.contract.test.ts.
 *
 * DAS IST DIE TEIL-RUECKNAHME VON SPEC 0289. Dort wurde jede frontendseitige, nach `category_key`
 * geschluesselte Tabelle abgeschafft, weil Anzeigenamen zur Laufzeit vom Server kommen. Fuer
 * ANZEIGENAMEN bleibt das so (sie kommen weiterhin ueber `GET /categories`, siehe unten). Fuer
 * FARBEN entsteht hier eine neue solche Tabelle, weil der Server keine Farben liefert und auch
 * keine liefern sollte: eine Chip-Farbe ist eine Gestaltungs-, keine Fachentscheidung.
 *
 * Die dadurch entstehende Kopplung ist real und bewusst getragen: kommt je eine vierzehnte
 * Kategorie hinzu, braucht sie hier einen Eintrag und zeigt sonst neutral. Der Fallback verhindert,
 * dass das ein Fehler wird - es bleibt eine sichtbare Luecke, kein Absturz und kein leeres Badge.
 */
const CHIP_CLASSES: Readonly<Record<string, string>> = {
  menschen: 'bg-chip-menschen text-chip-menschen-fg',
  tier: 'bg-chip-tier text-chip-tier-fg',
  pflanze: 'bg-chip-pflanze text-chip-pflanze-fg',
  landschaft: 'bg-chip-landschaft text-chip-landschaft-fg',
  gebaeude_bauwerk: 'bg-chip-gebaeude-bauwerk text-chip-gebaeude-bauwerk-fg',
  innenraum: 'bg-chip-innenraum text-chip-innenraum-fg',
  essen_trinken: 'bg-chip-essen-trinken text-chip-essen-trinken-fg',
  fahrzeug: 'bg-chip-fahrzeug text-chip-fahrzeug-fg',
  gegenstand: 'bg-chip-gegenstand text-chip-gegenstand-fg',
  dokument_screenshot: 'bg-chip-dokument-screenshot text-chip-dokument-screenshot-fg',
  kunst_kreatives: 'bg-chip-kunst-kreatives text-chip-kunst-kreatives-fg',
  sport_aktivitaet: 'bg-chip-sport-aktivitaet text-chip-sport-aktivitaet-fg',
  /* "Nicht erkannt" bekommt bewusst KEINE eigene Farbe: die Kategorie drueckt kein
     Erkennungsergebnis aus, sondern dessen Fehlen. Eine dreizehnte Buntfarbe wuerde ihr eine
     Aussage geben, die sie nicht hat - das neutrale Paar sagt genau das Richtige. Damit ist sie
     zugleich die einzige Kategorie, die man auch ohne jede Farbwahrnehmung sofort von den uebrigen
     zwoelf unterscheidet. Kein Fehler-Styling: ein fehlendes Erkennungsergebnis ist kein Fehler. */
  nicht_erkannt: 'bg-chip-nicht-erkannt text-chip-nicht-erkannt-fg',
}

const NEUTRAL_CHIP_CLASSES = CHIP_CLASSES.nicht_erkannt

/**
 * Kategorie-Chip in der Board-Form (specs/architecture/0005-board-dark-utility-register.md
 * Abschnitt 6): Radius 16px, Polsterung 12/6px, Inter Semi-Bold 12px, GETOENTE Flaeche mit heller,
 * bunter Schrift.
 *
 * Der strukturelle Gegensatz zum Bewertungs-Badge (voll GEFUELLTE Flaeche mit dunkler Tinte,
 * Radius 6px) ist der eigentliche Unterscheidungstraeger und keine Kosmetik: "Menschen" liegt
 * farblich praktisch auf dem Favorit-Amber und "Landschaft" 2 Grad vom Info-Cyan. Zusammen mit der
 * bestehenden Regel "Kategorie-Badge in der Gegenecke zur Rating-Badge" bleibt auf einer Kachel
 * ohne Nachdenken erkennbar, welches von beiden die Bewertung ist.
 *
 * Sichtbar sind drei Grossbuchstaben aus dem ANZEIGENAMEN (specs/features/0289-feste-
 * kategorien.md - ueber das feste Set kollisionsfrei), der vollstaendige Name steht als
 * `aria-label`/`title`. Die Namen kommen weiterhin zur Laufzeit vom Server; die Teil-Ruecknahme
 * von 0289 gilt ausschliesslich fuer Farben.
 */
export function CategoryBadge({ categoryKey, categories, className }: CategoryBadgeProps) {
  const label = formatCategoryKey(categoryKey, categories)
  // `Object.hasOwn` statt eines direkten Zugriffs: ein historischer Altwert aus der Laufhistorie
  // wie `constructor` oder `toString` bekaeme sonst einen geerbten Prototyp-Wert statt des
  // Neutral-Fallbacks. Robustheit, kein Angriffspfad - die Keys stammen aus der eigenen Datenbank.
  const chipClasses = Object.hasOwn(CHIP_CLASSES, categoryKey)
    ? CHIP_CLASSES[categoryKey]
    : NEUTRAL_CHIP_CLASSES

  return (
    <span
      data-category-key={categoryKey}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex items-center justify-center rounded-xl px-3 py-1 text-xs font-semibold',
        chipClasses,
        className
      )}
    >
      {categoryAbbreviation(categoryKey, categories)}
    </span>
  )
}
