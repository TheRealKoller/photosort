// Formatiert einen freien category_key (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
// backfill.md) fuer die Anzeige - kein festes Uebersetzungs-Woerterbuch mehr wie zu Spec-0024-
// Zeiten (PhotoCategory war ein geschlossenes 3-Wert-Enum). category_key ist jetzt ein freier,
// server-seitig erweiterbarer String (backend criteria.py::derive_category_key) - eine feste
// Uebersetzungsliste im Frontend wuerde bei jedem neuen Kriterium/jeder neuen Kategorie eine
// Frontend-Aenderung erzwingen und genau die Erweiterbarkeit wieder zunichtemachen, die das
// Datenmodell bewusst gewinnt (UI/UX-Abschnitt der Spec: "kein festes Kuerzel-Schema mehr
// moeglich"). Grossschreibung des ersten Buchstabens ist eine rein kosmetische Formatierung, kein
// Uebersetzungsschritt - der Rohwert selbst dient laut Spec als ausgeschriebener Name.

// specs/features/0045-kategorien-aus-statistiken-ableiten.md: explizites Mapping NUR fuer
// category_keys mit Sonderzeichen-Bedarf (Umlaute lassen sich nicht generisch aus dem
// Roh-Key ableiten) - kein Eintrag fuer jedes kuenftige, kategorie-faehige Kriterium noetig, der
// generische Fallback unten deckt alle unbekannten/kuenftigen Keys weiterhin ab.
const CATEGORY_DISPLAY_NAME_OVERRIDES: Readonly<Record<string, string>> = {
  gebaeude: 'Gebäude',
}

export function formatCategoryKey(categoryKey: string): string {
  const override = CATEGORY_DISPLAY_NAME_OVERRIDES[categoryKey]
  if (override !== undefined) {
    return override
  }
  if (categoryKey.length === 0) {
    return categoryKey
  }
  return categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1)
}

// Grid-Kachel-Chip (UI/UX-Abschnitt der Spec): erste drei Zeichen von category_key in
// Grossbuchstaben - seltene Praefix-Kollisionen (z.B. zwei kuenftige Kategorien mit identischem
// Praefix) sind fuer zwei bekannte Nutzer ein akzeptables Restrisiko, siehe Spec.
export function categoryAbbreviation(categoryKey: string): string {
  return categoryKey.slice(0, 3).toUpperCase()
}
