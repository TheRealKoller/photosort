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
import './verspielt.css'
import './minimal.css'
import './kreativ.css'

export type DirectionId = 'organic' | 'klar' | 'verspielt' | 'minimal' | 'kreativ'

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
    id: 'verspielt',
    label: 'Verspielt',
    character: 'Kräftige Farben, dicke Konturen, gestempelte Sticker — Fotosortieren als Bastelbogen.',
  },
  {
    id: 'minimal',
    label: 'Minimal',
    character: 'Weißraum statt Rahmen, Grautöne statt Farbe — Farbe bedeutet hier ausschließlich Zustand.',
  },
  {
    id: 'kreativ',
    label: 'Plakat',
    character: 'Beton, Ink-Konturen, Signalfarben und eine Times-Schlagzeile — die Oberfläche als Plakat.',
  },
]
