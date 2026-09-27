import { describe, expect, it } from 'vitest'

import type { BrowseEntry, FolderCountOut } from '../api/types'
import { arrangeFolders } from './folderListing'
import type { FolderSort } from './folderListing'

function folder(name: string, modified_at: string | null = null): BrowseEntry {
  return { name, path: `Eltern/${name}`, modified_at }
}

function exact(name: string, count: number): FolderCountOut {
  return { path: `Eltern/${name}`, count, at_limit: false, error: false }
}

function atLimit(name: string): FolderCountOut {
  return { path: `Eltern/${name}`, count: 500, at_limit: true, error: false }
}

function failed(name: string): FolderCountOut {
  return { path: `Eltern/${name}`, count: 0, at_limit: false, error: true }
}

const ALL_SORTS: FolderSort[] = ['name_asc', 'name_desc', 'count_desc', 'modified_desc']

function names(
  entries: BrowseEntry[],
  sort: FolderSort,
  options: { searchTerm?: string; counts?: FolderCountOut[]; countsSettled?: boolean } = {},
): string[] {
  return arrangeFolders(entries, {
    sort,
    searchTerm: options.searchTerm ?? '',
    counts: options.counts,
    countsSettled: options.countsSettled ?? true,
  }).entries.map((entry) => entry.name)
}

describe('arrangeFolders - Name', () => {
  it('ordnet Zahlen im Namen natürlich', () => {
    const entries = [folder('IMG_10'), folder('IMG_100'), folder('IMG_9')]

    expect(names(entries, 'name_asc')).toEqual(['IMG_9', 'IMG_10', 'IMG_100'])
  })

  it('ordnet ohne Rücksicht auf Groß-/Kleinschreibung', () => {
    const entries = [folder('gamma'), folder('Beta'), folder('alpha')]

    expect(names(entries, 'name_asc')).toEqual(['alpha', 'Beta', 'gamma'])
  })

  it('entscheidet den Gleichstand Foo/foo fest, unabhängig von der Lieferreihenfolge', () => {
    expect(names([folder('foo'), folder('Foo')], 'name_asc')).toEqual(['Foo', 'foo'])
    expect(names([folder('Foo'), folder('foo')], 'name_asc')).toEqual(['Foo', 'foo'])
  })

  it('liefert für umgestellte Eingaben dieselbe Ausgabe', () => {
    const entries = [folder('b'), folder('IMG_2'), folder('A'), folder('a'), folder('IMG_10')]
    const reversed = [...entries].reverse()

    expect(names(reversed, 'name_asc')).toEqual(names(entries, 'name_asc'))
    expect(names(entries, 'name_asc')).toEqual(['A', 'a', 'b', 'IMG_2', 'IMG_10'])
  })

  it('stellt Name Z–A als exakte Umkehrung von Name A–Z dar', () => {
    const entries = [folder('foo'), folder('IMG_10'), folder('Foo'), folder('IMG_9'), folder('bar')]

    expect(names(entries, 'name_desc')).toEqual([...names(entries, 'name_asc')].reverse())
  })
})

describe('arrangeFolders - Bildanzahl', () => {
  const entries = [
    folder('Fehler-b'),
    folder('Zehn-b'),
    folder('Voll-b'),
    folder('Null'),
    folder('Ohne-Eintrag'),
    folder('Zehn-a'),
    folder('Drei'),
    folder('Fehler-a'),
    folder('Voll-a'),
  ]
  const counts = [
    failed('Fehler-b'),
    exact('Zehn-b', 10),
    atLimit('Voll-b'),
    exact('Null', 0),
    exact('Zehn-a', 10),
    exact('Drei', 3),
    failed('Fehler-a'),
    atLimit('Voll-a'),
  ]

  it('ordnet 500+ vor exakte Zahlen absteigend vor fehlgeschlagene Zählungen, Gleichstände nach Name', () => {
    expect(names(entries, 'count_desc', { counts })).toEqual([
      'Voll-a',
      'Voll-b',
      'Zehn-a',
      'Zehn-b',
      'Drei',
      'Null',
      'Fehler-a',
      'Fehler-b',
      'Ohne-Eintrag',
    ])
  })

  it('stellt einen Ordner ohne Zähleintrag in die Fehlergruppe, nach der 0', () => {
    const order = names([folder('Ohne'), folder('Leer')], 'count_desc', {
      counts: [exact('Leer', 0)],
    })

    expect(order).toEqual(['Leer', 'Ohne'])
  })

  it('ordnet nach Name A–Z, wenn die ganze Zählanfrage gescheitert ist', () => {
    const order = names([folder('c'), folder('A'), folder('b')], 'count_desc', {
      counts: undefined,
      countsSettled: true,
    })

    expect(order).toEqual(['A', 'b', 'c'])
  })
})

describe('arrangeFolders - vorläufige Reihenfolge', () => {
  const entries = [folder('b'), folder('c'), folder('a')]
  const counts = [exact('a', 1), exact('b', 2), exact('c', 3)]

  it.each(ALL_SORTS.flatMap((sort) => [true, false].map((settled) => [sort, settled] as const)))(
    'ist bei %s und eingetroffen=%s nur für Bildanzahl vor dem Eintreffen vorläufig',
    (sort, countsSettled) => {
      const result = arrangeFolders(entries, { sort, searchTerm: '', counts, countsSettled })

      expect(result.provisional).toBe(sort === 'count_desc' && !countsSettled)
    },
  )

  it('zeigt die vorläufige Liste in Name A–Z', () => {
    expect(names(entries, 'count_desc', { counts: undefined, countsSettled: false })).toEqual([
      'a',
      'b',
      'c',
    ])
  })
})

describe('arrangeFolders - Änderungsdatum', () => {
  it('stellt den neuesten Ordner zuerst und Ordner ohne Datum ans Ende, Gleichstände nach Name', () => {
    const entries = [
      folder('ohne-b'),
      folder('alt', '2023-01-01T00:00:00Z'),
      folder('gleich-b', '2024-06-01T12:00:00Z'),
      folder('ohne-a'),
      folder('neu', '2025-03-01T08:00:00Z'),
      folder('gleich-a', '2024-06-01T12:00:00Z'),
    ]

    expect(names(entries, 'modified_desc')).toEqual([
      'neu',
      'gleich-a',
      'gleich-b',
      'alt',
      'ohne-a',
      'ohne-b',
    ])
  })

  it('vergleicht den Zeitpunkt, nicht die Zeichenkette', () => {
    // 10:00+02:00 ist 08:00Z und damit älter als 09:00Z, obwohl die Zeichenkette größer ist.
    const entries = [
      folder('frueher', '2024-05-01T10:00:00+02:00'),
      folder('spaeter', '2024-05-01T09:00:00Z'),
    ]

    expect(names(entries, 'modified_desc')).toEqual(['spaeter', 'frueher'])
  })

  it('wertet gleiche Zeitpunkte mit verschiedenem Zonenversatz als Gleichstand', () => {
    const entries = [folder('b', '2024-05-01T08:00:00Z'), folder('a', '2024-05-01T10:00:00+02:00')]

    expect(names(entries, 'modified_desc')).toEqual(['a', 'b'])
  })
})

describe('arrangeFolders - Suche', () => {
  const entries = [
    folder('2023-07 Costa Rica'),
    folder('ÄPFEL ernte'),
    folder('Apfelbaum'),
    folder('v1.2 (final)'),
    folder('v1x2 final'),
  ]

  it('trifft einen Teil in der Mitte des Namens', () => {
    expect(names(entries, 'name_asc', { searchTerm: 'sta r' })).toEqual(['2023-07 Costa Rica'])
  })

  it('ignoriert Groß-/Kleinschreibung auch bei Umlauten, setzt Umlaute aber nicht dem Grundbuchstaben gleich', () => {
    expect(names(entries, 'name_asc', { searchTerm: 'äpfel' })).toEqual(['ÄPFEL ernte'])
    expect(names(entries, 'name_asc', { searchTerm: 'APFEL' })).toEqual(['Apfelbaum'])
  })

  it('trimmt den Begriff', () => {
    expect(names(entries, 'name_asc', { searchTerm: '  costa  ' })).toEqual(['2023-07 Costa Rica'])
  })

  it('filtert bei einem nur aus Leerzeichen bestehenden Begriff nicht', () => {
    expect(names(entries, 'name_asc', { searchTerm: '   ' })).toHaveLength(entries.length)
  })

  it('nimmt Punkt und Klammer wörtlich', () => {
    expect(names(entries, 'name_asc', { searchTerm: '1.2' })).toEqual(['v1.2 (final)'])
    expect(names(entries, 'name_asc', { searchTerm: '(fin' })).toEqual(['v1.2 (final)'])
  })

  it('prüft nur den Namen, nie den Pfad des Elternordners', () => {
    expect(names(entries, 'name_asc', { searchTerm: 'Eltern' })).toEqual([])
  })
})

describe('arrangeFolders - Suche und Sortierung zusammen', () => {
  // Die vier Kriterien ergeben unter dem Filter vier verschiedene Reihenfolgen.
  const entries = [
    folder('Tag 10', '2024-01-01T00:00:00Z'),
    folder('Anderes', '2026-01-01T00:00:00Z'),
    folder('tag 2', '2025-01-01T00:00:00Z'),
    folder('Tag 1', '2023-01-01T00:00:00Z'),
  ]
  const counts = [atLimit('Tag 10'), exact('Anderes', 99), exact('tag 2', 5), exact('Tag 1', 7)]

  it.each([
    ['name_asc', ['Tag 1', 'tag 2', 'Tag 10']],
    ['name_desc', ['Tag 10', 'tag 2', 'Tag 1']],
    ['count_desc', ['Tag 10', 'Tag 1', 'tag 2']],
    ['modified_desc', ['tag 2', 'Tag 10', 'Tag 1']],
  ] as const)('folgt mit Filter dem Kriterium %s', (sort, expected) => {
    expect(names(entries, sort, { searchTerm: 'tag', counts })).toEqual(expected)
  })

  it('filtert auch die vorläufige Reihenfolge und zeigt sie in Name A–Z', () => {
    const result = arrangeFolders(entries, {
      sort: 'count_desc',
      searchTerm: 'tag',
      counts: undefined,
      countsSettled: false,
    })

    expect(result.entries.map((entry) => entry.name)).toEqual(['Tag 1', 'tag 2', 'Tag 10'])
    expect(result.provisional).toBe(true)
  })
})
