/*
 * Erzeugt die Penpot-Tokenliste aus `frontend/src/index.css`
 * (decisions/0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md Abschnitt 2).
 *
 * DIE RICHTUNG IST index.css -> Penpot, ERZEUGT STATT ABGESCHRIEBEN. Der Penpot-Plugin-Kontext hat
 * kein Dateisystem; die Werte muessen also in der Nutzlast stehen. Die Frage ist damit nicht, ob es
 * diese Kopie gibt, sondern ob sie erzeugt oder getippt ist - getippt waere sie der klassische Weg,
 * auf dem ein Design-System still auseinanderlaeuft. Ausgefuehrt wird dieser Erzeuger von
 * `tokens.test.ts` ueber einen Vitest-Dateischnappschuss; ein eigener TS-Runner, ein npm-Skript
 * oder eine neue Abhaengigkeit entstehen dadurch nicht.
 *
 * FEHLSCHLAGEN STATT UEBERSPRINGEN: Jede nicht verstandene Deklaration wirft. Ein still
 * uebersprungenes Token ist genau die Fehlerklasse, gegen die dieser Erzeuger antritt - es fehlte
 * in Penpot, bei gruener CI.
 *
 * Diese Datei liegt bewusst ausserhalb von `frontend/src/`: der Design-Vertragstest scannt `src/**`
 * und meldete die Tokennamen-Literale mit den Praefixen bg/text/border/font/rounded als tote
 * Tailwind-Utilities.
 */

/** Penpot-Tokentyp je Namensgruppe. Die Typbezeichner stammen aus ADR 0065 Abschnitt 2; sie sind
 * an der Plugin-API noch nicht gemessen und beim ersten echten Lauf zu bestaetigen (die
 * Aufbauskripte sind zum PR-Zeitpunkt unausgefuehrter Code, siehe ADR 0065 Abschnitt 7). */
export const TOKEN_TYPE_BY_GROUP: Readonly<Record<string, string>> = {
  color: 'color',
  radius: 'borderRadius',
  space: 'spacing',
  'font-size': 'fontSizes',
  'line-height': 'lineHeights',
  'font-weight': 'fontWeights',
  'letter-spacing': 'letterSpacing',
  'font-family': 'fontFamilies',
}

export interface PenpotToken {
  /** `<gruppe>.<blatt>`; das Blatt ist der CSS-Tokenname ohne `--` bzw. ohne das Gruppenpraefix,
   * damit ein Entwerfender denselben Namen sieht wie ein Entwickler. */
  name: string
  type: string
  value: string
}

export interface TokenBuildResult {
  tokens: PenpotToken[]
  /** Die auf `initial` gestrichenen Typo-Stufen. Sie werden ausgeschlossen UND gezaehlt - sonst
   * wanderte eine kuenftig wiederbelebte Stufe still nach Penpot oder eine gestrichene als
   * Groesse "initial". */
  excludedInitialTokens: string[]
}

/** Tailwinds Abstandsstufen, die das 8-Punkt-Raster des Boards ergeben (4/8/12/16/24/32/48/64px).
 * Sie sind die einzige Gruppe OHNE eigene Deklaration in index.css. */
export const SPACING_STEPS = [1, 2, 3, 4, 6, 8, 12, 16] as const

/** Tailwinds Voreinstellung fuer `--spacing`. index.css redeklariert sie nicht; deklariert sie
 * eine kuenftige Aenderung doch, gewinnt die Deklaration (und `tokens.test.ts` prueft das Ergebnis
 * zusaetzlich gegen den echten Tailwind-Lauf). */
const DEFAULT_SPACING_BASE = '0.25rem'

/** Die beiden Schriftfamilien-Tokens des Projekts. Sie sind die einzigen `:root`-Tokens ohne
 * Farbwert - dieselbe Ausnahmeliste wie in src/designSystem.contract.test.ts. */
const FONT_FAMILY_TOKENS: Readonly<Record<string, string>> = {
  '--sans': 'sans',
  '--mono': 'mono',
}

function extractBlock(css: string, header: string): string {
  const headerIndex = css.indexOf(header)
  if (headerIndex === -1) {
    throw new Error(`Kein ${header.replace(/\s*\{$/, '')}-Block in index.css gefunden.`)
  }
  const braceStart = css.indexOf('{', headerIndex)
  let depth = 0
  for (let i = braceStart; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    else if (css[i] === '}') {
      depth -= 1
      if (depth === 0) {
        return css.slice(braceStart + 1, i)
      }
    }
  }
  throw new Error(`Der ${header.replace(/\s*\{$/, '')}-Block in index.css ist nicht geschlossen.`)
}

function parseDeclarations(body: string): [string, string][] {
  const withoutComments = body.replace(/\/\*[\s\S]*?\*\//g, '')
  const declarations: [string, string][] = []
  for (const raw of withoutComments.split(';')) {
    const declaration = raw.trim()
    if (declaration.length === 0) continue
    const match = /^(--[a-z0-9-]+)\s*:\s*([\s\S]+)$/.exec(declaration)
    if (match === null) {
      throw new Error(`Unparsebare Deklaration: "${declaration}"`)
    }
    declarations.push([match[1], match[2].trim()])
  }
  return declarations
}

/**
 * EINZIGE BEWUSSTE UEBERSETZUNG DIESES ERZEUGERS (ADR 0065 Abschnitt 2): uebernommen wird die
 * Primaerfamilie, nicht der vollstaendige CSS-Stack. Eine Ausweichkette ist eine Browser-
 * Eigenschaft und in einem Entwurfswerkzeug bedeutungslos; ein Schriftname MIT Anfuehrungszeichen
 * findet in Penpot ausserdem keine Schrift. Das ist keine Auslassung, sondern die Uebersetzung.
 */
function primaryFontFamily(stack: string): string {
  const first = stack.split(',')[0].trim()
  return first.replace(/^['"]/, '').replace(/['"]$/, '')
}

function lengthToPixels(value: string, context: string): number {
  const match = /^([0-9]*\.?[0-9]+)(rem|px)$/.exec(value.trim())
  if (match === null) {
    throw new Error(`Unverstandene Laengenangabe "${value}" (${context}).`)
  }
  const amount = Number(match[1])
  // 1rem = 16px. Penpot kennt keine rem-Kaskade; die Tokenwerte sind deshalb Pixel.
  return match[2] === 'rem' ? amount * 16 : amount
}

/** Liest den `:root`- und den `@theme`-Block und uebersetzt sie in die Penpot-Tokenliste. Die
 * Reihenfolge des Ergebnisses ist die Deklarationsreihenfolge; die abgeleiteten Abstandsstufen
 * stehen als einzige Gruppe ohne Deklaration am Ende. */
export function buildTokens(css: string): TokenBuildResult {
  const tokens: PenpotToken[] = []
  const excludedInitialTokens: string[] = []

  for (const [name, value] of parseDeclarations(extractBlock(css, ':root {'))) {
    const fontFamilyLeaf = FONT_FAMILY_TOKENS[name]
    if (fontFamilyLeaf !== undefined) {
      tokens.push({
        name: `font-family.${fontFamilyLeaf}`,
        type: TOKEN_TYPE_BY_GROUP['font-family'],
        value: primaryFontFamily(value),
      })
      continue
    }
    if (!/^#[0-9a-fA-F]{6}$/.test(value)) {
      // Dieselbe Regel, die src/designSystem.contract.test.ts fuer die Kontrastmatrix erzwingt:
      // ein indirekter oder deckkraftbasierter Wert waere weder rechenbar noch uebertragbar.
      throw new Error(`${name} traegt keinen 6-stelligen Hexwert, sondern "${value}".`)
    }
    tokens.push({ name: `color.${name.slice(2)}`, type: TOKEN_TYPE_BY_GROUP.color, value })
  }

  let spacingBase = DEFAULT_SPACING_BASE
  for (const [name, value] of parseDeclarations(extractBlock(css, '@theme {'))) {
    // Der Loewenanteil des @theme-Blocks ist die Tailwind-ZUORDNUNG (`--color-bg: var(--bg)`) -
    // ein Verweis, kein eigener Wert. Er wird bewusst uebersprungen, und zwar nur in genau dieser
    // Form; alles andere faellt unten in den Fehlerzweig.
    if (/^var\(--[a-z0-9-]+\)$/.test(value)) {
      continue
    }
    if (name === '--spacing') {
      spacingBase = value
      continue
    }

    const radius = /^--radius-([a-z0-9]+)$/.exec(name)
    if (radius !== null) {
      tokens.push({ name: `radius.${radius[1]}`, type: TOKEN_TYPE_BY_GROUP.radius, value })
      continue
    }

    const text = /^--text-([a-z0-9]+)(--line-height|--font-weight|--letter-spacing)?$/.exec(name)
    if (text !== null) {
      const step = text[1]
      if (value === 'initial') {
        if (text[2] !== undefined) {
          throw new Error(`Unerwartetes "initial" an ${name}.`)
        }
        excludedInitialTokens.push(name)
        continue
      }
      const group =
        text[2] === undefined
          ? 'font-size'
          : (text[2].slice(2) as 'line-height' | 'font-weight' | 'letter-spacing')
      tokens.push({ name: `${group}.${step}`, type: TOKEN_TYPE_BY_GROUP[group], value })
      continue
    }

    throw new Error(`Unverstandene @theme-Deklaration: "${name}: ${value}".`)
  }

  const basePixels = lengthToPixels(spacingBase, '--spacing')
  for (const step of SPACING_STEPS) {
    tokens.push({
      name: `space.${step}`,
      type: TOKEN_TYPE_BY_GROUP.space,
      value: `${basePixels * step}px`,
    })
  }

  return { tokens, excludedInitialTokens }
}

/** Festgelegte Serialisierung: zwei Leerzeichen Einrueckung, abschliessender Zeilenumbruch. Sie
 * ist Teil der Zusage, damit ein Formatierungswechsel nicht als Wertaenderung durchgeht. */
export function serializeTokens(tokens: PenpotToken[]): string {
  return `${JSON.stringify(tokens, null, 2)}\n`
}
