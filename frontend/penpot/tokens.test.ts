// @vitest-environment node
/*
 * Erzeugung UND Pruefung der Penpot-Tokenliste (specs/features/0352-penpot-als-alleinige-design-
 * quelle.md, decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md Abschnitt 2).
 *
 * DIESER TEST IST DER ERZEUGER: `toMatchFileSnapshot` schreibt `design/penpot/tokens.json`. In CI
 * legt Vitest eine FEHLENDE Schnappschussdatei nicht an, sondern schlaegt fehl - die Datei muss
 * eingecheckt sein. Regeneriert wird mit `npm test -- -u`.
 *
 * Schnappschussgleichheit sagt nur "unveraendert", nicht "richtig". Daneben stehen deshalb
 * Inhaltszusicherungen, die auch bei einem frisch erzeugten Schnappschuss greifen: eingefrorene
 * Kardinalitaeten, Namensform, Wertfreiheit von `var()`, der gezaehlte `initial`-Ausschluss, eine
 * parserunabhaengige Gegenprobe gegen `index.css`, der Abgleich der Abstandsstufen gegen den
 * ECHTEN Tailwind-Lauf und die fuenf wertetragenden Abweichungen namentlich.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { compile } from '@tailwindcss/node'
import { describe, expect, it } from 'vitest'

import {
  buildTokens,
  letterSpacingToPixels,
  serializeTokens,
  SPACING_STEPS,
  TOKEN_TYPE_BY_GROUP,
  TYPOGRAFIE_FELDER,
  TYPOGRAFIE_PFLICHTFELDER,
  type PenpotToken,
  type TypografieWert,
} from './tokens.ts'

const SRC_DIR = fileURLToPath(new URL('../src/', import.meta.url))
const INDEX_CSS_PATH = fileURLToPath(new URL('../src/index.css', import.meta.url))
const TOKENS_JSON_PATH = fileURLToPath(new URL('../../design/penpot/tokens.json', import.meta.url))

const indexCss = readFileSync(INDEX_CSS_PATH, 'utf8')
const built = buildTokens(indexCss)
const tokens = built.tokens

function groupOf(token: PenpotToken): string {
  return token.name.slice(0, token.name.indexOf('.'))
}

function countByGroup(group: string): number {
  return tokens.filter((token) => groupOf(token) === group).length
}

function valueOf(name: string): string {
  const token = tokens.find((candidate) => candidate.name === name)
  if (token === undefined) {
    throw new Error(`Token ${name} wurde nicht erzeugt.`)
  }
  if (typeof token.value !== 'string') {
    throw new Error(`Token ${name} traegt einen Verbundwert, keinen Einzelwert.`)
  }
  return token.value
}

function typografieWert(name: string): TypografieWert {
  const token = tokens.find((candidate) => candidate.name === name)
  if (token === undefined || typeof token.value === 'string') {
    throw new Error(`Token ${name} ist kein Typografie-Verbundtoken.`)
  }
  return token.value
}

describe('Penpot-Tokenliste: Erzeugung aus index.css', () => {
  /*
   * Eingefrorene Kardinalitaeten je Gruppe. Die sieben Schriftstufen sind VERBUNDTOKENS vom Typ
   * `typography`: Penpot kennt keinen Token-Typ fuer Zeilenhoehen (am 2026-09-08 an einer
   * verbundenen Instanz gemessen - `lineHeight` und `lineHeights` scheitern beide hart), und eine
   * Stufe wird beim Entwerfen ohnehin in einem Zug angewandt.
   */
  it('erzeugt genau die eingefrorenen Kardinalitaeten je Gruppe', () => {
    expect(countByGroup('color')).toBe(64)
    expect(countByGroup('radius')).toBe(5)
    expect(countByGroup('space')).toBe(8)
    expect(countByGroup('font-family')).toBe(2)
    expect(countByGroup('text')).toBe(7)
    expect(tokens).toHaveLength(64 + 5 + 8 + 2 + 7)
  })

  it('legt fuer Zeilenhoehe, Schnitt und Laufweite kein eigenes Token an', () => {
    for (const gruppe of ['line-height', 'font-weight', 'letter-spacing']) {
      expect(countByGroup(gruppe), gruppe).toBe(0)
    }
  })

  it('kennt keine Gruppe ausserhalb des geschlossenen Vokabulars', () => {
    const groups = new Set(tokens.map(groupOf))
    expect([...groups].sort()).toEqual(Object.keys(TOKEN_TYPE_BY_GROUP).sort())
  })

  it('benennt jedes Token als <gruppe>.<blatt>', () => {
    const shape =
      /^(color|radius|space|font-family|text)\.[a-z0-9-]+$/
    const wrong = tokens.filter((token) => !shape.test(token.name))
    expect(wrong.map((token) => token.name)).toEqual([])
  })

  it('vergibt jeden Namen genau einmal', () => {
    const names = tokens.map((token) => token.name)
    expect(new Set(names).size).toBe(names.length)
  })

  it('traegt je Gruppe den festgelegten Penpot-Tokentyp', () => {
    for (const token of tokens) {
      expect(token.type, token.name).toBe(TOKEN_TYPE_BY_GROUP[groupOf(token)])
    }
  })

  /* Ein `var()`-Wert waere in Penpot bedeutungslos: der Plugin-Kontext kennt die CSS-Kaskade
     nicht. Der @theme-Block besteht zu zwei Dritteln aus solchen Verweisen - sie sind die
     Tailwind-ZUORDNUNG, nicht der Wert, und duerfen deshalb nicht im Ergebnis landen. */
  it('traegt ausschliesslich ausgeschriebene Werte, nie var() oder initial', () => {
    for (const token of tokens) {
      const felder = typeof token.value === 'string' ? [token.value] : Object.values(token.value)
      for (const feld of felder) {
        expect(feld, token.name).not.toContain('var(')
        expect(feld, token.name).not.toBe('initial')
      }
    }
  })

  /*
   * KEIN LEERES FELD IRGENDWO IM ERZEUGNIS. Das ist die Regel, die den ersten echten Lauf
   * gerettet haette: Im `typography`-Verbundwert ist eine leere Zeichenkette ein UNGUELTIGER Wert
   * und laesst den ganzen Aufruf scheitern ("Field 0.value is invalid") - ein Feld traegt einen
   * Wert oder fehlt ganz. Gemessen am 2026-09-08 an der laufenden Instanz.
   */
  it('gibt nirgends ein leeres Feld aus', () => {
    for (const token of tokens) {
      const felder = typeof token.value === 'string' ? [token.value] : Object.values(token.value)
      for (const feld of felder) {
        expect(feld, token.name).not.toBe('')
        expect(String(feld).trim().length, token.name).toBeGreaterThan(0)
      }
    }
    // Gegenprobe an der Serialisierung: auch kein `null` und kein `undefined` im Erzeugnis.
    expect(serializeTokens(tokens)).not.toContain('""')
    expect(serializeTokens(tokens)).not.toContain('null')
  })

  /*
   * DIE SIEBEN TYPOGRAFIE-VERBUNDTOKENS. Der Schreibwert benutzt die SINGULAR-Schluessel; die
   * Pluralformen der dokumentierten `TokenTypographyValue` sind die Leseform und werden als
   * Schreibwert abgelehnt (gemessen). Die Familie steht als REFERENZ auf eines der beiden
   * Familientokens da, damit sie nicht doppelt im System liegt.
   */
  describe('Typografie-Verbundtokens', () => {
    const stufen = ['xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl']

    it('traegt je Stufe genau ein Verbundtoken', () => {
      expect(tokens.filter((token) => groupOf(token) === 'text').map((token) => token.name)).toEqual(
        stufen.map((stufe) => `text.${stufe}`)
      )
    })

    /* Die Felder stehen in fester Reihenfolge und in Singularform; weggelassen wird nur, was
       index.css nicht fuehrt. Ein Feld ausserhalb des Vokabulars faellt hier auf. */
    it('traegt seine Felder in Singularform und fester Reihenfolge', () => {
      for (const stufe of stufen) {
        const felder = Object.keys(typografieWert(`text.${stufe}`))
        expect(felder, stufe).toEqual(TYPOGRAFIE_FELDER.filter((feld) => felder.includes(feld)))
        for (const feld of felder) {
          expect(TYPOGRAFIE_FELDER, `${stufe}: ${feld}`).toContain(feld)
        }
      }
    })

    it('traegt Familie, Groesse und Zeilenhoehe immer', () => {
      for (const stufe of stufen) {
        const wert: Record<string, string | undefined> = { ...typografieWert(`text.${stufe}`) }
        for (const feld of TYPOGRAFIE_PFLICHTFELDER) {
          expect(Object.keys(wert), `${stufe}: ${feld}`).toContain(feld)
          expect(wert[feld], `${stufe}: ${feld}`).not.toBe('')
        }
      }
    })

    it('scheitert an einer Schriftstufe ohne Groesse oder Zeilenhoehe', () => {
      expect(() =>
        buildTokens(':root {\n  --bg: #0b0c10;\n}\n@theme {\n  --text-xs: 12px;\n}')
      ).toThrow(/xs/)
    })

    it('verweist fuer die Familie auf das Familientoken, statt es zu wiederholen', () => {
      for (const stufe of stufen) {
        expect(typografieWert(`text.${stufe}`).fontFamily, stufe).toBe('{font-family.sans}')
      }
      // Gegenprobe: der Verweis zeigt auf ein Token, das es tatsaechlich gibt.
      expect(tokens.some((token) => token.name === 'font-family.sans')).toBe(true)
    })

    /* `fontSize` traegt seine Einheit - an der laufenden Instanz als gueltig gemessen. */
    it('traegt Groesse und Zeilenhoehe jeder Stufe aus index.css', () => {
      expect([
        typografieWert('text.xs').fontSize,
        typografieWert('text.xs').lineHeight,
      ]).toEqual(['12px', '1.4'])
      expect([
        typografieWert('text.3xl').fontSize,
        typografieWert('text.3xl').lineHeight,
      ]).toEqual(['64px', '1.05'])
      for (const stufe of stufen) {
        expect(typografieWert(`text.${stufe}`).fontSize, stufe).toMatch(/^[0-9]+px$/)
        expect(typografieWert(`text.${stufe}`).lineHeight, stufe).toMatch(/^[0-9.]+$/)
      }
    })

    /* AM BESTAND AUSGEMESSEN, nicht ueberschlagen: fuenf Stufen tragen einen Schnitt, xs und sm
       nicht. Ein ergaenzter Standardwert `400` waere genau die getippte Wertekopie, die ADR 0066
       verbietet - das Feld bleibt deshalb leer. */
    /* WEGGELASSEN, NICHT LEER: `--text-xs`/`--text-sm` tragen keinen Schnitt. Ein ergaenzter
       Standardwert `400` waere die getippte Wertekopie, ein leeres Feld ein ungueltiger Wert. */
    it('laesst den Schnitt weg, wo index.css keinen fuehrt', () => {
      expect(Object.keys(typografieWert('text.xs'))).not.toContain('fontWeight')
      expect(Object.keys(typografieWert('text.sm'))).not.toContain('fontWeight')
      expect(
        stufen.filter((stufe) => 'fontWeight' in typografieWert(`text.${stufe}`))
      ).toEqual(['base', 'lg', 'xl', '2xl', '3xl'])
      expect(typografieWert('text.3xl').fontWeight).toBe('700')
    })

    /* Nur --text-3xl traegt eine Laufweite - und sie muss eine BLANKE ZAHL IN PX sein: ein
       em-Wert wird als Tokenwert akzeptiert und loest auch auf, kommt an der Textform aber als 0
       an (gemessen). Umgerechnet gegen die Schriftgroesse der Stufe greift sie nachweislich. */
    it('rechnet die Laufweite von em in eine blanke px-Zahl um', () => {
      expect(
        stufen.filter((stufe) => 'letterSpacing' in typografieWert(`text.${stufe}`))
      ).toEqual(['3xl'])
      expect(typografieWert('text.3xl').letterSpacing).toBe('-1.28')
      expect(typografieWert('text.3xl').letterSpacing).not.toContain('em')
    })

    it('rechnet die Laufweite gegen die Schriftgroesse der jeweiligen Stufe', () => {
      expect(letterSpacingToPixels('-0.02em', '64px')).toBe('-1.28')
      expect(letterSpacingToPixels('-0.02em', '16px')).toBe('-0.32')
      expect(letterSpacingToPixels('0.05em', '20px')).toBe('1')
      expect(() => letterSpacingToPixels('-0.02rem', '64px')).toThrow()
    })
  })

  /* Ohne die ZAEHLUNG wanderte eine kuenftig wiederbelebte Stufe still nach Penpot oder eine
     gestrichene als Groesse "initial". */
  it('schliesst genau die sechs auf initial gestrichenen Stufen aus und zaehlt sie', () => {
    expect(built.excludedInitialTokens).toEqual([
      '--text-4xl',
      '--text-5xl',
      '--text-6xl',
      '--text-7xl',
      '--text-8xl',
      '--text-9xl',
    ])
    expect(built.excludedInitialTokens).toHaveLength(6)
    for (const step of ['4xl', '5xl', '6xl', '7xl', '8xl', '9xl']) {
      expect(tokens.some((token) => token.name === `text.${step}`), step).toBe(false)
    }
  })

  /*
   * FEHLSCHLAGEN STATT UEBERSPRINGEN. Eine stillschweigend uebersprungene Deklaration ist genau
   * die Fehlerklasse, gegen die dieser Erzeuger antritt: ein Token, das in Penpot fehlt, bei
   * gruener CI. Dieselbe Regel setzt src/designSystem.contract.test.ts fuer die Kontrastmatrix
   * durch.
   */
  it('scheitert an einer nicht verstandenen Deklaration statt sie zu ueberspringen', () => {
    expect(() => buildTokens(':root {\n  farbe: #ffffff;\n}\n@theme {\n}')).toThrow()
    expect(() =>
      buildTokens(':root {\n  --bg: #0b0c10;\n}\n@theme {\n  --unbekannt-xs: 3px;\n}')
    ).toThrow(/--unbekannt-xs/)
  })

  /*
   * Die EINE namentliche Ausnahme (specs/features/0387-schrittleiste-fortschritt.md):
   * `--spacing-header` ist eine Layout-Konstante der App-Huelle, kein Design-Token - sie erzeugt
   * bewusst keinen Eintrag. Geprueft wird beides zugleich, sonst waere die Ausnahme ein Loch:
   * sie schweigt NUR fuer diesen einen Namen, jeder andere `--spacing-*`-Name faellt weiterhin in
   * den Fehlerzweig.
   */
  it('ueberspringt --spacing-header namentlich, nicht ueber ein Praefixmuster', () => {
    const mitHeader = buildTokens(
      ':root {\n  --bg: #0b0c10;\n}\n@theme {\n  --spacing-header: 3.5rem;\n}'
    )
    const namen = mitHeader.tokens.map((token) => token.name)
    expect(namen.filter((name) => name.includes('header'))).toEqual([])
    // Positiv-Gegenprobe: der Lauf hat ueberhaupt Tokens erzeugt.
    expect(namen).toContain('color.bg')
    expect(() =>
      buildTokens(':root {\n  --bg: #0b0c10;\n}\n@theme {\n  --spacing-sidebar: 3.5rem;\n}')
    ).toThrow(/--spacing-sidebar/)
  })

  it('scheitert an einem :root-Wert, der kein 6-stelliger Hexwert ist', () => {
    expect(() =>
      buildTokens(':root {\n  --bg: color-mix(in srgb, #fff 50%, #000);\n}\n@theme {\n}')
    ).toThrow(/--bg/)
  })

  it('scheitert an einem fehlenden :root- oder @theme-Block', () => {
    expect(() => buildTokens('@theme {\n}')).toThrow()
    expect(() => buildTokens(':root {\n  --bg: #0b0c10;\n}')).toThrow()
  })

  /* PARSERUNABHAENGIGE GEGENPROBE: ohne sie beweist die Kardinalitaet nur, dass der Parser mit
     sich selbst uebereinstimmt. */
  it('belegt jedes Farbtoken woertlich in index.css', () => {
    for (const token of tokens.filter((candidate) => groupOf(candidate) === 'color')) {
      const leaf = token.name.slice('color.'.length)
      expect(indexCss, token.name).toContain(`--${leaf}:`)
    }
  })

  it('leitet die acht Abstandsstufen aus Tailwinds Basis ab', () => {
    expect(SPACING_STEPS).toEqual([1, 2, 3, 4, 6, 8, 12, 16])
    expect(tokens.filter((token) => groupOf(token) === 'space').map((token) => [token.name, token.value])).toEqual([
      ['space.1', '4px'],
      ['space.2', '8px'],
      ['space.3', '12px'],
      ['space.4', '16px'],
      ['space.6', '24px'],
      ['space.8', '32px'],
      ['space.12', '48px'],
      ['space.16', '64px'],
    ])
  })

  /*
   * Die Abstandsstufen sind die einzige Gruppe OHNE eigene Deklaration in index.css. Sie werden
   * deshalb gegen den ECHTEN Tailwind-Lauf geprueft: was erzeugt `p-1`, was `p-16`.
   *
   * JEDE STUFE BEKOMMT EINEN EIGENEN compile()-LAUF. `build()` arbeitet inkrementell - einmal
   * aufgenommene Kandidaten bleiben in der Ausgabe, ein einziger Lauf faerbte also ab dem ersten
   * Treffer alle folgenden gruen. Geprueft wird der ERZEUGTE DEKLARATIONSWERT (Faktor und Basis),
   * nicht bloss "erzeugt ueberhaupt eine Regel".
   */
  it('deckt sich je Abstandsstufe mit dem echten Tailwind-Lauf', async () => {
    for (const step of SPACING_STEPS) {
      const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
      const baseline = compiled.build([])
      const output = compiled.build([`p-${step}`])
      expect(output, `p-${step}`).not.toBe(baseline)

      const spacingBase = /--spacing:\s*([^;]+);/.exec(output)
      expect(spacingBase, `p-${step}: keine --spacing-Basis in der Ausgabe`).not.toBeNull()
      const baseRem = Number.parseFloat(spacingBase![1])
      expect(Number.isNaN(baseRem), `p-${step}`).toBe(false)

      // `p-1` gibt Tailwind ohne Faktor aus (`padding: var(--spacing)`), ab `p-2` mit `calc()`.
      const withFactor = /padding:\s*calc\(var\(--spacing\)\s*\*\s*([0-9.]+)\)/.exec(output)
      const withoutFactor = /padding:\s*var\(--spacing\)\s*;/.exec(output)
      const factor = withFactor === null ? (withoutFactor === null ? Number.NaN : 1) : Number(withFactor[1])
      expect(factor, `p-${step}: unverstandene Padding-Deklaration`).toBe(step)

      // 1rem = 16px; die Tokenwerte sind Pixel, weil Penpot keine rem-Kaskade kennt.
      expect(valueOf(`space.${step}`), `p-${step}`).toBe(`${baseRem * 16 * factor}px`)
    }
  }, 120_000)

  /*
   * EINZIGE BEWUSSTE UEBERSETZUNG (ADR 0066 Abschnitt 2): nur die Primaerfamilie, nicht der
   * CSS-Ausweichstack. Beide Haelften als eigene Testfaelle - ein naives `split(',')[0]` liefert
   * die Apostrophe mit, und ein Schriftname mit Anfuehrungszeichen findet in Penpot keine Schrift.
   */
  it('traegt die Schriftfamilie ohne Anfuehrungszeichen', () => {
    expect(valueOf('font-family.sans')).toBe('Inter')
    expect(valueOf('font-family.mono')).toBe('JetBrains Mono')
  })

  it('traegt die Schriftfamilie ohne Ausweichkette', () => {
    for (const name of ['font-family.sans', 'font-family.mono']) {
      expect(valueOf(name), name).not.toContain(',')
      expect(valueOf(name), name).not.toContain("'")
      expect(valueOf(name), name).not.toContain('"')
    }
  })

  /*
   * AKZEPTANZKRITERIUM 2 ALS EINGEFRORENE TABELLE. Uebertragen wird der Stand aus index.css, nicht
   * der Board-Stand: sonst kehrten die in ADR 0055 Punkt 4 begruendet korrigierten, schlechter
   * lesbaren Farbwerte ueber die neue Quelle zurueck. Die drei uebrigen der acht dokumentierten
   * Abweichungen (Symbolwahl, Verwendungsregel, Randbreite) sind keine Tokenwerte und wandern
   * nicht als solche mit.
   */
  describe('Akzeptanzkriterium 2: die fuenf wertetragenden Abweichungen', () => {
    it('traegt --text-muted mit dem Projektwert #8D92A4 statt dem Board-Wert #62677A', () => {
      expect(valueOf('color.text-muted').toUpperCase()).toBe('#8D92A4')
      expect(serializeTokens(tokens).toUpperCase()).not.toContain('#62677A')
    })

    it('traegt --border-control mit dem Projektwert #727891 statt dem Board-Wert #2A2E3D', () => {
      expect(valueOf('color.border-control').toUpperCase()).toBe('#727891')
    })

    it('traegt --danger-text mit dem Projektwert #FF5A26 statt dem Board-Wert #FF3D00', () => {
      expect(valueOf('color.danger-text').toUpperCase()).toBe('#FF5A26')
      // Die Flaechenfarbe --danger behaelt den Board-Wert - nur die TEXTfarbe ist korrigiert.
      expect(valueOf('color.danger').toUpperCase()).toBe('#FF3D00')
    })

    it('traegt die dunkle Badge-Tinte #0B0C10 auf allen drei Bewertungstoenen', () => {
      for (const tone of ['favorite', 'album-worthy', 'rejected']) {
        expect(valueOf(`color.rating-${tone}-fg`).toUpperCase(), tone).toBe('#0B0C10')
      }
    })

    it('traegt die Chip-Schrift "Gebaeude/Bauwerk" mit #FF44A1 statt dem Board-Wert #FF007F', () => {
      expect(valueOf('color.chip-gebaeude-bauwerk-fg').toUpperCase()).toBe('#FF44A1')
      expect(serializeTokens(tokens).toUpperCase()).not.toContain('#FF007F')
    })
  })

  it('haelt die Deklarationsreihenfolge von index.css ein', () => {
    const colorLeaves = tokens
      .filter((token) => groupOf(token) === 'color')
      .map((token) => token.name.slice('color.'.length))
    // Am Zeilenanfang verankert: `--rating-rejected-fg:` kommt weiter oben auch in einem
    // Fliesstext-Kommentar vor, ein blosses indexOf faende dort die falsche Stelle.
    const positions = colorLeaves.map((leaf) => {
      const hit = new RegExp(`^[ \\t]*--${leaf}:`, 'm').exec(indexCss)
      expect(hit, leaf).not.toBeNull()
      return hit!.index
    })
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
    expect(tokens[0].name).toBe('color.bg')
  })

  /* Derselbe Text bedeutet als Objektliteral im Quelltext etwas anderes als ueber `JSON.parse`
     (ADR 0066 Abschnitt 5 Punkt 3) - der Erzeuger gibt deshalb keinen solchen Schluessel aus. */
  it('gibt keinen Schluessel __proto__ aus', () => {
    expect(serializeTokens(tokens)).not.toContain('__proto__')
  })

  it('serialisiert festgelegt: zwei Leerzeichen Einrueckung, abschliessender Zeilenumbruch', () => {
    const serialized = serializeTokens(tokens)
    expect(serialized).toBe(`${JSON.stringify(tokens, null, 2)}\n`)
    expect(serialized.endsWith('\n')).toBe(true)
    expect(JSON.parse(serialized)).toEqual(tokens)
  })

  /* DIE ERZEUGUNG SELBST. Steht bewusst am Ende: schlaegt eine der Zusicherungen oben fehl, ist
     der Schnappschuss ohnehin nicht das, was eingecheckt werden soll. */
  it('erzeugt design/penpot/tokens.json', async () => {
    await expect(serializeTokens(tokens)).toMatchFileSnapshot(TOKENS_JSON_PATH)
  })
})
