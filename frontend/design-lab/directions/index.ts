/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Registry der fuenf
 * Gestaltungsrichtungen. Sie ist die einzige Stelle, an der eine Richtung "existiert" - Id,
 * Anzeigename, Ein-Satz-Charakterisierung und der Import ihrer CSS-Datei.
 *
 * Das Schutzgelaender G3(b) in ../guards.test.ts prueft, dass genau die fuenf Dateien in
 * directions/*.css und genau die hier registrierten Ids uebereinstimmen: eine Datei ohne
 * Registry-Eintrag waere im Labor unsichtbar, ein Registry-Eintrag ohne Datei ein Ladefehler.
 */
import './organic.css'
import './klar.css'
import './dunkelkammer.css'
import './minimal.css'
import './linie.css'

export type DirectionId = 'organic' | 'klar' | 'dunkelkammer' | 'minimal' | 'linie'

export interface Direction {
  id: DirectionId
  label: string
  /** Ein-Satz-Charakterisierung, erscheint als Untertitel im Vergleich "Nebeneinander". */
  character: string
}

export const DIRECTIONS: readonly Direction[] = [
  {
    id: 'organic',
    label: 'Organic',
    character: 'Warme Erdtöne, weiche Rundungen, Display-Serife — die heutige Oberfläche.',
  },
  {
    id: 'klar',
    label: 'Klar',
    character: 'Sachlich, gerahmt, dicht — eine Oberfläche, die sich wie ein sauber geführtes Archiv liest.',
  },
  {
    id: 'dunkelkammer',
    label: 'Dunkelkammer',
    character: 'Kontaktbogen und Rotlicht — Chinagraph-Markierungen auf Filmkadern, dunkel als Heimat.',
  },
  {
    id: 'minimal',
    label: 'Minimal',
    character: 'Weißraum statt Rahmen, Grautöne statt Farbe — Farbe bedeutet hier ausschließlich Zustand.',
  },
  {
    id: 'linie',
    label: 'Linie',
    character: 'Hoher Kontrast und durchlaufende Linien bei viel Luft — Ordnung ohne Enge.',
  },
]
