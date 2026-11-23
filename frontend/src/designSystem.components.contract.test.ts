// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Navigationselement, Fortschritt, Hoehen-Token, Typoskala, Kompilier-Pruefung.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts .
 */

import { compile } from '@tailwindcss/node'
import { describe, expect, it } from 'vitest'

import {
  findMatches,
  indexCss,
  sourceFiles,
  SRC_DIR,
  stringLiterals,
} from './test/designSystemScan'

describe('Design-Vertrag: Board-Navigationselement', () => {
  /*
   * specs/features/0298-projektnavigation-in-der-kopfzeile.md, AK8c: Die Aktiv-Markierung der
   * Projekt-Navigationsgruppe ist ZEICHENGLEICH zum Schrittmarker in Stepper.tsx. Die beiden
   * Rezepte bleiben bewusst dateilokal (etablierte "erst ab dem dritten Konsumenten auslagern"-
   * Praxis) - dann braucht die Zusage aber einen Waechter, sonst driften sie still auseinander.
   *
   * Diese Ebene ist die einzig moegliche: Komponententests bekommen in diesem Projekt keine
   * CSS-Assertions, sie saehen die Abweichung also nie.
   */
  const RECIPES = {
    aktiv: 'border-accent bg-overlay font-bold text-accent',
    ruhend:
      'border-border-control bg-surface text-text hover:bg-overlay hover:text-text-h ' +
      'active:bg-border active:text-text',
  }

  function literalsOf(label: string): string[] {
    const file = sourceFiles.find((candidate) => candidate.label === label)
    expect(file, `${label} nicht gefunden`).toBeDefined()
    return stringLiterals(file!.content)
  }

  /**
   * Die Schrittmarke traegt seit specs/features/0387-schrittleiste-fortschritt.md die Zustaende
   * des UMSCHLIESSENDEN Bedienelements (`group` in Stepper.tsx) und schreibt sie deshalb
   * `group-`-praefixiert. Die Bindung leitet diese Fassung aus der Fassung der
   * Projekt-Navigationsgruppe AB, statt sie ein zweites Mal zu tippen - sonst waere genau die
   * Dopplung entstanden, gegen die diese Zusicherung antritt.
   */
  function groupPraefixiert(recipe: string): string {
    return recipe.replace(/(^|\s)(hover|active):/g, '$1group-$2:')
  }

  it('praefixiert im Ableiter nur Zustaende, nicht beliebige Woerter', () => {
    // Selbsttest des Ableiters: ohne ihn koennte er alles oder nichts umschreiben und die
    // Bindung unten waere in beiden Faellen gruen.
    expect(groupPraefixiert('bg-surface hover:bg-overlay')).toBe(
      'bg-surface group-hover:bg-overlay',
    )
    expect(groupPraefixiert('text-accent')).toBe('text-accent')
  })

  it.each(Object.entries(RECIPES))(
    'fuehrt das %s-Rezept in StepMarker und ProjectNav zeichengleich',
    (_name, recipe) => {
      expect(literalsOf('src/components/ProjectNav.tsx'), 'ProjectNav ohne das Rezept').toContain(
        recipe,
      )
      expect(literalsOf('src/components/StepMarker.tsx'), 'StepMarker ohne das Rezept').toContain(
        groupPraefixiert(recipe),
      )
    },
  )

  /*
   * specs/features/0347-navigation-nebenbereich.md (AK5): Die Absetzung der Nebenzielgruppe im
   * Panel haengt am Block der HAUPTZIELE - so verschwindet die Linie ab `lg:` automatisch mit dem
   * Block, den sie abtrennt. Gebunden wird die Zeile woertlich, weil hier insbesondere die
   * Token-Wahl zur Debatte steht: `border-border` waere auf `--elevated` gar keine sichtbare
   * Linie, und der Fehler faellt in keinem Komponententest auf (jsdom hat keine Layout-Engine).
   *
   * NAV_TRIGGER_ACTIVE_CLASSES wird der Bindung oben ausdruecklich NICHT hinzugefuegt: der
   * Aktivstil des Ausloesers ist ein drittes, absichtlich abweichendes Rezept - ein Symbol-Button
   * ist kein Board-Navigationselement.
   */
  it('bindet die Trenner-Utilities der Panel-Gruppe woertlich (Spec 0347, AK5)', () => {
    expect(literalsOf('src/components/ProjectNav.tsx')).toContain(
      'mb-2 border-b border-separator pb-2 lg:hidden',
    )
  })

  it('bindet nicht gegen ein Rezept, das in keiner der beiden Dateien steht', () => {
    // Positiv-Gegenprobe: ohne sie bestuende die Bindung oben auch dann, wenn `stringLiterals`
    // nichts mehr faende und beide Seiten leer waeren.
    for (const label of ['src/components/StepMarker.tsx', 'src/components/ProjectNav.tsx']) {
      expect(literalsOf(label).length).toBeGreaterThan(0)
      expect(literalsOf(label)).not.toContain('border-accent bg-overlay font-black text-accent')
    }
  })
})

describe('Design-Vertrag: unbestimmter Fortschritt', () => {
  /*
   * Spec 0321, UI/UX-Abschnitt 6: Der unbestimmte Balken folgt dem Board statt der
   * Browser-Voreinstellung - volle Flaeche in `--accent` mit dem bereits etablierten Puls, statt
   * eines wandernden Segments (das waere eine Positionsbewegung und ist im Design-System
   * verboten).
   *
   * Bewusst KEINE Zeichenkettensuche "behandelt die Datei den Zustand?" - das waere eine Zusage
   * ueber die Schreibweise. Genutzt wird der staerkste Mechanismus dieses Vertragstests: der
   * tatsaechliche Tailwind-Lauf. Eine unbekannte Variante ist in Tailwind KEIN Buildfehler und
   * bliebe sonst still wirkungslos.
   */
  it('erzeugt fuer die Zustandsbehandlung des Balkens tatsaechlich Regeln', async () => {
    // `build()` arbeitet inkrementell: einmal aufgenommene Kandidaten bleiben in der Ausgabe.
    // Jeder Kandidat bekommt deshalb einen EIGENEN Lauf, sonst faerbte der erste Treffer alle
    // folgenden gruen.
    async function producesRule(utility: string): Promise<boolean> {
      const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
      const baseline = compiled.build([])
      return compiled.build([utility]) !== baseline
    }

    for (const utility of [
      'indeterminate:bg-accent',
      'indeterminate:animate-pulse',
      'motion-reduce:animate-none',
      'bg-separator',
    ]) {
      expect(await producesRule(utility), utility).toBe(true)
    }
    // Gegenprobe: eine erfundene Variante erzeugt keine Regel - sonst bestuende der Test auch
    // dann, wenn `build()` alles durchwinkte. Genau das ist der Fehlermodus, gegen den diese
    // Pruefung ueberhaupt steht: ein Tippfehler in einer Variante ist in Tailwind kein Buildfehler.
    expect(await producesRule('inderterminate:bg-accent')).toBe(false)
  }, 60_000)

  it('legt die Spur des Balkens nicht mehr auf das unsichtbare --border', () => {
    const progress = sourceFiles.filter((file) => file.label === 'src/components/ui/progress.tsx')
    expect(progress).toHaveLength(1)
    expect(findMatches('bg-border', progress)).toEqual([])
    // Positiv-Gegenprobe: die Datei faerbt die Spur ueberhaupt ein.
    expect(findMatches('bg-separator', progress).length).toBeGreaterThan(0)
  })
})

describe('Design-Vertrag: geteiltes Hoehen-Token der fixierten Bereiche', () => {
  /*
   * specs/features/0387-schrittleiste-fortschritt.md, Architektur-Abschnitt 1: Kopfzeile und
   * Schrittleiste haften beide oben und duerfen sich nicht ueberlagern. Getrennt werden sie
   * GEOMETRISCH ueber EINEN Wert: `--spacing-header` im `@theme`-Block erzeugt in Tailwind v4 die
   * Utilities `h-header` (Kopfzeile) und `top-header` (Versatz der Schrittleiste).
   *
   * WARUM DAS HIER GEPRUEFT WIRD UND NICHT IN JSDOM: Eine unbekannte Utility ist in Tailwind KEIN
   * Buildfehler. Ein `top-header`, fuer das der `--spacing-*`-Namensraum wider Erwarten keine
   * Regel erzeugt, bliebe wirkungslos - die Leiste waere gar nicht mehr versetzt, und weder Build
   * noch Typpruefung noch Komponententest saehen es. Der echte Tailwind-Lauf ist der einzige
   * Mechanismus im Projekt, der diesen stillen Fehlschlag ueberhaupt bemerkt.
   */
  async function producesRule(utility: string): Promise<boolean> {
    // Eigener `compile()`-Lauf je Kandidat: `build()` arbeitet inkrementell, ein gemeinsamer Lauf
    // faerbte den zweiten Kandidaten am ersten gruen.
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const baseline = compiled.build([])
    return compiled.build([utility]) !== baseline
  }

  it('erzeugt fuer h-header und top-header tatsaechlich Regeln', async () => {
    for (const utility of ['h-header', 'top-header']) {
      expect(await producesRule(utility), utility).toBe(true)
    }
    // Gegenprobe: ein Tippfehler im selben Namensraum erzeugt KEINE Regel. Ohne sie bestuende der
    // Test auch dann, wenn `build()` alles durchwinkte.
    for (const utility of ['top-headr', 'h-headr']) {
      expect(await producesRule(utility), utility).toBe(false)
    }
  }, 60_000)

  /** Die Klassen-Literale einer Produktivdatei - ohne Kommentare, damit eine Erlaeuterung nicht
   * als Fundstelle zaehlt. */
  function classesOf(label: string): string[] {
    const file = sourceFiles.find((candidate) => candidate.label === label)
    expect(file, `${label} nicht gefunden`).toBeDefined()
    return stringLiterals(file!.content).flatMap((literal) => literal.split(/\s+/))
  }

  it('ruft das Token an genau den beiden vorgesehenen Stellen auf', () => {
    expect(classesOf('src/App.tsx'), 'Kopfzeile ohne h-header').toContain('h-header')
    expect(classesOf('src/components/Stepper.tsx'), 'Leiste ohne top-header').toContain(
      'top-header',
    )
  })

  it('traegt in keiner der beiden Dateien einen zweiten, freihaendigen Hoehenwert', () => {
    // Ein zweiter Zahlenwert fuer dieselbe Hoehe waere die Fehlerquelle, gegen die das Token
    // ueberhaupt steht: er driftet still, und die Naht zwischen beiden Leisten reisst auf.
    const zweiterWert = /\b(?:top|h|pt|mt)-(?:14|\[[^\]]+\])/
    for (const label of ['src/App.tsx', 'src/components/Stepper.tsx']) {
      const file = sourceFiles.find((candidate) => candidate.label === label)!
      expect(
        findMatches(zweiterWert, [file]).map((hit) => hit.match),
        label,
      ).toEqual([])
    }
  })

  it('haelt die Schrittleiste nicht mehr auf top-0', () => {
    const classes = classesOf('src/components/Stepper.tsx')
    expect(classes, 'Leiste haftet noch auf top-0').not.toContain('top-0')
    // Positiv-Gegenprobe: die Datei traegt ueberhaupt Klassen und haftet weiterhin.
    expect(classes).toContain('sticky')
  })

  it('laesst die Kopfzeile nicht mehr umbrechen', () => {
    // Mit fester Hoehe waere ein Umbruch stilles Abschneiden statt sichtbaren Wachsens; der
    // Nutzername wird stattdessen gekuerzt. Gegenprobe, damit die Abwesenheit nicht auch bei
    // einer leer gelesenen Datei bestuende.
    const classes = classesOf('src/App.tsx')
    expect(classes, 'Kopfzeile bricht weiterhin um').not.toContain('flex-wrap')
    expect(classes).toContain('truncate')
    expect(classes).toContain('min-w-0')
  })

  it('fuehrt den Hoehenwert genau einmal - ein Wert, zwei Aufrufstellen', () => {
    const declarations = indexCss.split('\n').filter((line) => /--spacing-header\s*:/.test(line))
    expect(declarations, 'Deklarationen von --spacing-header in index.css').toHaveLength(1)
    expect(declarations[0]).toMatch(/--spacing-header:\s*3\.5rem;/)
  })
})

describe('Design-Vertrag: Typoskala', () => {
  it('legt die Board-Groessen auf die bestehenden Tailwind-Stufen', () => {
    for (const [utility, value] of [
      ['xs', '12px'],
      ['sm', '14px'],
      ['base', '16px'],
      ['lg', '20px'],
      ['xl', '24px'],
      ['2xl', '40px'],
      ['3xl', '64px'],
    ]) {
      expect(indexCss).toMatch(new RegExp(`--text-${utility}:\\s*${value};`))
    }
  })

  it('erzeugt fuer text-4xl und groesser keine Regel mehr', async () => {
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const baseline = compiled.build([])
    for (const utility of [
      'text-4xl',
      'text-5xl',
      'text-6xl',
      'text-7xl',
      'text-8xl',
      'text-9xl',
    ]) {
      expect(compiled.build([utility]), utility).toBe(baseline)
    }
    // Gegenprobe: die verbliebenen Stufen erzeugen sehr wohl eine Regel - sonst bestuende der
    // Test auch bei einer voellig kaputten Skala.
    for (const utility of ['text-xs', 'text-3xl']) {
      expect(compiled.build([utility]), utility).not.toBe(baseline)
    }
  }, 30_000)

  it('laesst den Fehlerumriss am Eingabefeld auch im fokussierten Zustand stehen', async () => {
    // Fokussiert UND fehlerhaft duerfen sich nicht gegenseitig ausloeschen: der Fehlerumriss bleibt
    // AM Feld, die Fokusdarstellung liegt als abgesetzte Kontur aussen herum. Das haengt an der
    // Reihenfolge, in der Tailwind die beiden Varianten ausgibt - eine kuenftige Umsortierung im
    // Framework wuerde die Zusage still brechen, deshalb hier festgehalten statt angenommen.
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const output = compiled.build(['focus:border-accent', 'aria-invalid:border-danger'])
    expect(output.indexOf('aria-invalid\\:border-danger')).toBeGreaterThan(
      output.indexOf('focus\\:border-accent'),
    )
  }, 30_000)

  it('erzeugt fuer die Organic-Abstandsskala keine Regel mehr, wohl aber fuer das 8-Punkt-Raster', async () => {
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const baseline = compiled.build([])
    for (const utility of ['p-o1', 'p-o4', 'p-o8']) {
      expect(compiled.build([utility]), utility).toBe(baseline)
    }
    // Die acht Stufen 4/8/12/16/24/32/48/64 kommen aus Tailwinds Default- --spacing.
    for (const utility of ['p-1', 'p-2', 'p-3', 'p-4', 'p-6', 'p-8', 'p-12', 'p-16']) {
      expect(compiled.build([utility]), utility).not.toBe(baseline)
    }
  }, 30_000)
})

// ---------------------------------------------------------------------------------------------
// Kompilier-Pruefung
// ---------------------------------------------------------------------------------------------

/** Namensraeume, deren Werte aus dem Design-System kommen. Nur hier kann eine gestrichene Utility
 * still keine Regel mehr erzeugen - `p-4`/`flex`/`gap-2` haengen nicht an unseren Tokens. */
const DESIGN_UTILITY_ROOTS = [
  'bg',
  'text',
  'border',
  'ring',
  'outline',
  'fill',
  'stroke',
  'caret',
  'decoration',
  'divide',
  'placeholder',
  'shadow',
  'font',
  'rounded',
]

/** Nicht-Utilities, die zufaellig wie welche aussehen (CSS-Schluesselwoerter in Prosa/Attributen). */
const NOT_A_UTILITY = new Set(['border-box', 'text-top', 'text-bottom', 'font-face'])

function utilityCandidates(): Map<string, string> {
  const candidates = new Map<string, string>()
  for (const file of sourceFiles) {
    for (const literal of stringLiterals(file.content)) {
      for (const word of literal.split(/\s+/)) {
        if (word.length === 0) continue
        if (!/^[a-z0-9[\]&:_.,()/#%>*+~-]+$/.test(word)) continue
        const base = word.split(':').pop() ?? word
        const root = base.replace(/^-/, '').split('-')[0]
        if (!DESIGN_UTILITY_ROOTS.includes(root)) continue
        if (NOT_A_UTILITY.has(base)) continue
        if (!candidates.has(word)) candidates.set(word, file.label)
      }
    }
  }
  return candidates
}

describe('Design-Vertrag: Kompilier-Pruefung', () => {
  it('erzeugt fuer jede verwendete Design-Utility beim echten Tailwind-Lauf eine Regel', async () => {
    // Schliesst die Fehlerart "gestrichene Utility erzeugt still keine Regel" - weder Build noch
    // Typpruefung noch Komponententest sehen sie, in Tailwind ist ein unbekannter Klassenname
    // KEIN Fehler. Startet bewusst gruen: heute gibt es keine verwaisten Utilities, der Test ist
    // Regressionsnetz und kein TDD-Treiber.
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    // `output.includes('@layer utilities')` waere FALSCH: die blosse Layer-Deklaration steht immer
    // in der Ausgabe, unabhaengig davon, ob der Kandidat eine Regel erzeugt hat.
    const baseline = compiled.build([])
    const candidates = utilityCandidates()
    const dead: string[] = []
    for (const [candidate, origin] of candidates) {
      if (compiled.build([candidate]) === baseline) {
        dead.push(`${candidate} (${origin})`)
      }
    }
    expect(candidates.size).toBeGreaterThan(50)
    expect(dead).toEqual([])
  }, 30_000)
})
