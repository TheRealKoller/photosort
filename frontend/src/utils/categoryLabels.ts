import type { CategoryKey, CategoryOut } from '../api/types'

// specs/features/0289-feste-kategorien.md, Umsetzungsschritt 7: die Anzeigetabelle kommt zur
// LAUFZEIT vom Server (`GET /categories`, ADR 0049 Entwurfsentscheidung 5) - das frueher hier
// gepflegte `CATEGORY_DISPLAY_NAME_OVERRIDES`-Woerterbuch ist ersatzlos entfallen.
//
// Die drei Helfer sind bewusst REINE FUNKTIONEN mit dem geladenen Set als EXPLIZITEM Parameter
// (Testvorgabe der Spec, nicht Stilfrage): eine modul-globale, vom Query-Cache befuellte Variable
// haette sie nur noch mit `QueryClientProvider` testbar gemacht und ihre Tests von Query-Zustand
// abhaengig.
//
// `categories` darf jederzeit leer sein (Set noch nicht geladen) - dann greift ueberall der
// generische Fallback, kein Absturz und kein leeres Badge.

export type CategorySet = readonly CategoryOut[]

/**
 * Auffangkorb-Key des Backends (`categories.py::CATEGORY_NOT_RECOGNIZED`) - Fotos, fuer die kein
 * Bildmotiv sicher bestimmbar war. Kein verwaister Key, sondern eine regulaer waehlbare Kategorie
 * des Sets.
 */
export const CATCH_ALL_CATEGORY_KEY = 'nicht_erkannt'

/**
 * Generischer Fallback fuer einen Key, der NICHT im geladenen Set steht - praktisch nur noch fuer
 * Altwerte aus der Laufhistorie (`"unerkannt"`, `"landscape"`, `"people"`; die Laufhistorie wird
 * bewusst nicht migriert) und fuer die kurze Phase, in der das Set noch laedt. Reine Kosmetik
 * (erster Buchstabe gross), kein Uebersetzungsschritt.
 */
function genericFallback(categoryKey: string): string {
  if (categoryKey.length === 0) {
    return categoryKey
  }
  return categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1)
}

function findDisplayName(categoryKey: string, categories: CategorySet): string | null {
  for (const entry of categories) {
    if (entry.key === categoryKey) {
      return entry.display_name
    }
  }
  return null
}

/**
 * Anzeigename eines `category_key`: der `display_name` aus dem geladenen Set, sonst der generische
 * Fallback. Bewusst eine lineare Suche ueber genau 13 Eintraege statt eines aus dem Set gebauten
 * Objekt-Lookups - damit gibt es auch keinen `Object.prototype`-Durchgriff mehr, gegen den der
 * fruehere `Object.hasOwn`-Check (Copilot-Review-Fund, PR #106) schuetzen musste. Ein Key wie
 * `"toString"` trifft hier strukturell keinen Eintrag und faellt korrekt auf den Fallback.
 */
export function formatCategoryKey(categoryKey: CategoryKey, categories: CategorySet): string {
  return findDisplayName(categoryKey, categories) ?? genericFallback(categoryKey)
}

/**
 * Kuerzel fuer die Grid-Kachel (UI/UX-Abschnitt der Spec 0289): erste drei Zeichen des
 * ANZEIGENAMENS in Grossbuchstaben - nicht mehr des rohen Keys. Ueber das feste 13er-Set ist das
 * kollisionsfrei ("MEN"/"TIE"/"PFL"/"LAN"/"GEB"/"INN"/"ESS"/"FAH"/"GEG"/"DOK"/"KUN"/"SPO"/"NIC"),
 * abgesichert durch einen parametrisierten Test ueber alle 13 Anzeigenamen. Fuer einen Altwert
 * ohne Set-Eintrag greift derselbe generische Fallback wie oben.
 */
export function categoryAbbreviation(categoryKey: CategoryKey, categories: CategorySet): string {
  return formatCategoryKey(categoryKey, categories).slice(0, 3).toUpperCase()
}

/**
 * Reihenfolge kategorialer Listen (Abschnitts-Ueberschriften, Override-Auswahl): die
 * ANZEIGEREIHENFOLGE der Server-Registry, nicht alphabetisch - so ist die Reihenfolge ueberall im
 * Produkt identisch. Danach folgen unbekannte Altwerte aus der Laufhistorie (untereinander
 * alphabetisch als expliziter, deterministischer Tie-Break - sonst haenge die Anzeige an der
 * `Object.keys`-Reihenfolge), und ganz zuletzt immer der Auffangkorb "Nicht erkannt"
 * (Design-System-Muster "Auffangkorb-Kategorie mit erklaerend dezentem Signal").
 *
 * Liefert ein neues Array statt das uebergebene zu sortieren.
 */
export function sortCategoryKeys(
  categoryKeys: readonly CategoryKey[],
  categories: CategorySet
): CategoryKey[] {
  const registryOrder = new Map<string, number>()
  categories.forEach((entry, index) => registryOrder.set(entry.key, index))

  // Drei Raenge: 0 = bekannter Set-Eintrag (Registry-Reihenfolge entscheidet), 1 = unbekannter
  // Altwert, 2 = Auffangkorb. Der Auffangkorb steht damit auch dann zuletzt, wenn er in der
  // Registry (Anzeigereihenfolge) an derselben Stelle steht.
  function rank(key: CategoryKey): number {
    if (key === CATCH_ALL_CATEGORY_KEY) {
      return 2
    }
    return registryOrder.has(key) ? 0 : 1
  }

  return [...categoryKeys].sort((a, b) => {
    if (a === b) return 0
    const rankDiff = rank(a) - rank(b)
    if (rankDiff !== 0) return rankDiff
    if (rank(a) === 0) {
      return (registryOrder.get(a) ?? 0) - (registryOrder.get(b) ?? 0)
    }
    return a < b ? -1 : 1
  })
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md: Anzeigename eines
// Cloud-Vision-Providers (backend `provider`-Feld, aktuell "anthropic"/"mistral") - geteilt
// zwischen ClassificationSection.tsx (Erklaertext bei angewaehlter Cloud-Nutzung; bis
// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md der Bestaetigungsdialog in
// RemoteCategoryClassificationSection.tsx) und der "Kategorie-Kandidaten"-Gruppe in
// CriterionDetailsList.tsx ("Herkunft"-Chip). Fallback auf den
// rohen Wert fuer einen kuenftigen, hier noch nicht gepflegten Provider - kein Absturz.
const PROVIDER_DISPLAY_NAMES: Readonly<Record<string, string>> = {
  anthropic: 'Anthropic',
  mistral: 'Mistral',
}

export function formatProviderLabel(provider: string): string {
  if (Object.hasOwn(PROVIDER_DISPLAY_NAMES, provider)) {
    return PROVIDER_DISPLAY_NAMES[provider]
  }
  return provider
}
