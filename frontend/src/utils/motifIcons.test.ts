import { describe, expect, it } from 'vitest'

import { ICON_NAMES } from '../components/ui/icon'
import { MOTIF_KEYS } from '../test/motifSetFixture'
import { motifIconName } from './motifIcons'

/**
 * specs/features/0490-motivstaerke-kompakt.md, AK5 und ADR 0113 Punkt 3.
 */
describe('motifIconName', () => {
  it.each([
    ['menschen', 'user-round'],
    ['landschaft', 'mountain-snow'],
    ['bauwerk_sehenswuerdigkeit', 'landmark'],
    ['stadt_strasse', 'building-2'],
    ['tiere', 'paw-print'],
    ['essen_trinken', 'utensils'],
    ['aktivitaet', 'footprints'],
    ['detail_stimmung', 'sparkles'],
  ])('ordnet %s das Symbol %s zu', (motifKey, iconName) => {
    expect(motifIconName(motifKey)).toBe(iconName)
  })

  it('deckt jeden Schluessel der Registry ab, ohne auf das Ersatzsymbol zu fallen', () => {
    // Ohne diesen Fall bliebe eine vergessene Zuordnung gruen: sie faellt still auf `tag`.
    for (const key of MOTIF_KEYS) {
      expect(motifIconName(key), key).not.toBe('tag')
    }
  })

  it('liefert ausschliesslich Namen, die der Symbolsatz auch kennt', () => {
    for (const key of [...MOTIF_KEYS, 'unbekannt']) {
      expect(ICON_NAMES, key).toContain(motifIconName(key))
    }
  })

  it('faellt fuer einen unbekannten Schluessel auf das Ersatzsymbol zurueck', () => {
    // Ein Altwert aus der Laufhistorie zerreisst die Reihe nicht.
    expect(motifIconName('unerkannt')).toBe('tag')
  })

  it.each(['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty'])(
    'greift fuer %s nicht auf Object.prototype durch',
    (motifKey) => {
      // Dieselbe Begruendung wie in utils/motifLabels.ts: ein Objekt-Lookup traefe hier einen
      // geerbten Wert und lieferte eine Funktion statt eines Symbolnamens.
      expect(motifIconName(motifKey)).toBe('tag')
    },
  )

  it('faellt fuer den leeren Schluessel auf das Ersatzsymbol zurueck', () => {
    expect(motifIconName('')).toBe('tag')
  })
})
