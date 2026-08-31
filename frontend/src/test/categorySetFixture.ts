import type { CategoryOut } from '../api/types'

/**
 * Das feste 13er-Kategorien-Set in Anzeigereihenfolge, genau wie es `GET /categories` liefert
 * (specs/features/0289-feste-kategorien.md, Registry in `backend/src/photosort/categories.py`).
 *
 * Liegt als GETEILTE Fixture hier statt je Testdatei erneut, weil das Set seit dieser Spec zur
 * Laufzeit vom Server kommt und deshalb in mehreren Ebenen gebraucht wird: als Parameter der reinen
 * Anzeigehelfer (`utils/categoryLabels`) und als Rueckgabewert des gemockten `listCategories` in den
 * Seiten-Tests. Eine Kopie je Datei waere eine driftende zweite Liste - genau das, was diese Spec
 * im Produktivcode abgeschafft hat.
 *
 * Die `definition`-Texte sind bewusst gekuerzt: keine Anzeigestelle im Frontend wertet sie aus.
 */
export const CATEGORY_SET: CategoryOut[] = [
  { key: 'menschen', display_name: 'Menschen', definition: 'd', locally_available: true },
  { key: 'tier', display_name: 'Tier', definition: 'd', locally_available: true },
  { key: 'pflanze', display_name: 'Pflanze', definition: 'd', locally_available: false },
  { key: 'landschaft', display_name: 'Landschaft', definition: 'd', locally_available: true },
  {
    key: 'gebaeude_bauwerk',
    display_name: 'Gebäude & Bauwerk',
    definition: 'd',
    locally_available: true,
  },
  { key: 'innenraum', display_name: 'Innenraum', definition: 'd', locally_available: false },
  {
    key: 'essen_trinken',
    display_name: 'Essen & Trinken',
    definition: 'd',
    locally_available: true,
  },
  { key: 'fahrzeug', display_name: 'Fahrzeug', definition: 'd', locally_available: true },
  { key: 'gegenstand', display_name: 'Gegenstand', definition: 'd', locally_available: false },
  {
    key: 'dokument_screenshot',
    display_name: 'Dokument & Screenshot',
    definition: 'd',
    locally_available: false,
  },
  {
    key: 'kunst_kreatives',
    display_name: 'Kunst & Kreatives',
    definition: 'd',
    locally_available: false,
  },
  {
    key: 'sport_aktivitaet',
    display_name: 'Sport & Aktivität',
    definition: 'd',
    locally_available: false,
  },
  { key: 'nicht_erkannt', display_name: 'Nicht erkannt', definition: 'd', locally_available: false },
]
