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
  // specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: Sonderzeichen-Bedarf
  // (Umlaut) wie "gebaeude" oben - der generische Fallback koennte "Sehenswürdigkeit" nicht aus
  // dem rohen category_key "landmark" ableiten.
  landmark: 'Sehenswürdigkeit',
}

export function formatCategoryKey(categoryKey: string): string {
  // Own-Property-Check statt reinem `!== undefined` (Copilot-Review-Fund, PR #106): category_key
  // ist laut Spec ein freier, server-seitig erweiterbarer String, keine geschlossene Aufzaehlung
  // - ein reiner Plain-Object-Zugriff wuerde fuer Werte wie "toString"/"constructor" das geerbte
  // Object.prototype-Property statt undefined liefern und faelschlich als Treffer gewertet.
  if (Object.hasOwn(CATEGORY_DISPLAY_NAME_OVERRIDES, categoryKey)) {
    return CATEGORY_DISPLAY_NAME_OVERRIDES[categoryKey]
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

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md: Anzeigename eines
// Cloud-Vision-Providers (backend `provider`-Feld, aktuell "anthropic"/"mistral") - geteilt
// zwischen RemoteCategoryClassificationSection.tsx (Bestaetigungsdialog) und der neuen
// "Kategorie-Kandidaten"-Gruppe in CriterionDetailsList.tsx ("Herkunft"-Chip). Fallback auf den
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
