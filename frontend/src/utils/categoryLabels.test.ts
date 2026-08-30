import { describe, expect, it } from 'vitest'

import type { CategoryOut } from '../api/types'
import {
  CATCH_ALL_CATEGORY_KEY,
  categoryAbbreviation,
  formatCategoryKey,
  sortCategoryKeys,
} from './categoryLabels'

// specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 9: die Anzeigetabelle kommt zur
// Laufzeit vom Server. Die drei Helfer bleiben deshalb reine Funktionen mit dem geladenen Set als
// EXPLIZITEM Parameter - kein QueryClientProvider, keine Abhaengigkeit von Query-Zustand.

/** Das feste 13er-Set in Anzeigereihenfolge, wie es `GET /categories` liefert (die Definitionen
 * sind hier bewusst gekuerzt - die Helfer werten nur `key`/`display_name` aus). */
const CATEGORY_SET: CategoryOut[] = [
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

describe('formatCategoryKey', () => {
  it('returns the display name from the loaded set', () => {
    expect(formatCategoryKey('menschen', CATEGORY_SET)).toBe('Menschen')
    expect(formatCategoryKey('gebaeude_bauwerk', CATEGORY_SET)).toBe('Gebäude & Bauwerk')
    expect(formatCategoryKey(CATCH_ALL_CATEGORY_KEY, CATEGORY_SET)).toBe('Nicht erkannt')
  })

  it('falls back generically for a legacy key from the run history', () => {
    // Die Laufhistorie (`PhotoRanking`) wird bewusst NICHT migriert - dort stehen weiterhin
    // Altwerte ausserhalb des Sets. Sie muessen ohne Absturz und ohne leeres Badge darstellbar
    // bleiben (Edge Case 12 der Spec).
    expect(formatCategoryKey('unerkannt', CATEGORY_SET)).toBe('Unerkannt')
    expect(formatCategoryKey('detail', CATEGORY_SET)).toBe('Detail')
    expect(formatCategoryKey('landscape', CATEGORY_SET)).toBe('Landscape')
  })

  it('falls back generically while the set is still loading', () => {
    expect(formatCategoryKey('menschen', [])).toBe('Menschen')
  })

  it('handles the empty string without throwing', () => {
    expect(formatCategoryKey('', CATEGORY_SET)).toBe('')
    expect(formatCategoryKey('', [])).toBe('')
  })

  it('does not fall through to an inherited Object.prototype property', () => {
    // Bestandstest (Copilot-Review-Fund, PR #106) auf die neue Signatur UMGESTELLT, nicht
    // geloescht: `category_key` ist weiterhin ein freier String, und ein Key wie "toString" darf
    // niemals als Treffer im Anzeigenamen-Lookup gewertet werden.
    expect(formatCategoryKey('toString', CATEGORY_SET)).toBe('ToString')
    expect(formatCategoryKey('constructor', CATEGORY_SET)).toBe('Constructor')
    expect(formatCategoryKey('hasOwnProperty', CATEGORY_SET)).toBe('HasOwnProperty')
  })
})

describe('categoryAbbreviation', () => {
  it.each([
    ['menschen', 'MEN'],
    ['tier', 'TIE'],
    ['pflanze', 'PFL'],
    ['landschaft', 'LAN'],
    ['gebaeude_bauwerk', 'GEB'],
    ['innenraum', 'INN'],
    ['essen_trinken', 'ESS'],
    ['fahrzeug', 'FAH'],
    ['gegenstand', 'GEG'],
    ['dokument_screenshot', 'DOK'],
    ['kunst_kreatives', 'KUN'],
    ['sport_aktivitaet', 'SPO'],
    ['nicht_erkannt', 'NIC'],
  ])('derives the abbreviation of %s from the display name', (key, expected) => {
    expect(categoryAbbreviation(key, CATEGORY_SET)).toBe(expected)
  })

  it('is collision-free across the whole set', () => {
    // Parametrisiert ueber ALLE 13 Anzeigenamen statt einer Stichprobe (Teststrategie 9) - eine
    // Praefix-Kollision waere in der Grid-Kachel nicht mehr aufloesbar.
    const abbreviations = CATEGORY_SET.map((entry) =>
      categoryAbbreviation(entry.key, CATEGORY_SET)
    )
    expect(new Set(abbreviations).size).toBe(CATEGORY_SET.length)
  })

  it('falls back to the raw key for a legacy value outside the set', () => {
    expect(categoryAbbreviation('unerkannt', CATEGORY_SET)).toBe('UNE')
  })
})

describe('sortCategoryKeys', () => {
  it('follows the registry display order, not alphabetical order', () => {
    // Alphabetisch waere ["menschen", "sport_aktivitaet", "tier"] - die Registry-Reihenfolge
    // stellt `menschen`, `tier`, `sport_aktivitaet` her.
    expect(sortCategoryKeys(['sport_aktivitaet', 'tier', 'menschen'], CATEGORY_SET)).toEqual([
      'menschen',
      'tier',
      'sport_aktivitaet',
    ])
  })

  it('always puts the catch-all last', () => {
    expect(sortCategoryKeys([CATCH_ALL_CATEGORY_KEY, 'tier', 'menschen'], CATEGORY_SET)).toEqual([
      'menschen',
      'tier',
      CATCH_ALL_CATEGORY_KEY,
    ])
  })

  it('puts unknown legacy values after the set but before the catch-all', () => {
    expect(
      sortCategoryKeys([CATCH_ALL_CATEGORY_KEY, 'landscape', 'tier'], CATEGORY_SET)
    ).toEqual(['tier', 'landscape', CATCH_ALL_CATEGORY_KEY])
  })

  it('sorts several legacy values deterministically among themselves', () => {
    // Expliziter Tie-Break (alphabetisch) statt eines impliziten Verlasses auf die
    // `Object.keys`-Reihenfolge - sonst haenge die Anzeige an der Einfuegereihenfolge.
    expect(sortCategoryKeys(['zoo', 'detail', 'landscape'], CATEGORY_SET)).toEqual([
      'detail',
      'landscape',
      'zoo',
    ])
  })

  it('handles single-element and empty input', () => {
    expect(sortCategoryKeys([CATCH_ALL_CATEGORY_KEY], CATEGORY_SET)).toEqual([
      CATCH_ALL_CATEGORY_KEY,
    ])
    expect(sortCategoryKeys(['tier'], CATEGORY_SET)).toEqual(['tier'])
    expect(sortCategoryKeys([], CATEGORY_SET)).toEqual([])
  })

  it('falls back to a deterministic alphabetical order while the set is still loading', () => {
    expect(sortCategoryKeys(['tier', 'menschen', CATCH_ALL_CATEGORY_KEY], [])).toEqual([
      'menschen',
      'tier',
      CATCH_ALL_CATEGORY_KEY,
    ])
  })

  it('does not mutate the given array', () => {
    const original = [CATCH_ALL_CATEGORY_KEY, 'tier']
    const result = sortCategoryKeys(original, CATEGORY_SET)
    expect(original).toEqual([CATCH_ALL_CATEGORY_KEY, 'tier'])
    expect(result).not.toBe(original)
  })
})
