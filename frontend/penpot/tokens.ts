/*
 * Erzeugt die Penpot-Tokenliste aus `frontend/src/index.css`.
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

/** Penpot-Tokentyp je Namensgruppe (an einer verbundenen Instanz gemessen). Die sieben
 * Schriftstufen sind **Verbundtokens** vom Typ `typography`: Penpot kennt keinen Token-Typ fuer
 * Zeilenhoehen, und eine Stufe wird beim Entwerfen ohnehin in einem Zug angewandt.
 *
 * Ihre Gruppe heisst `text` und nicht `font-size`: Das Token traegt neben der Groesse auch
 * Zeilenhoehe, Schnitt und Laufweite - ein Gruppenname `font-size` verspraeche weniger, als
 * darin steckt. `text.base` spiegelt ausserdem `--text-base` aus index.css unmittelbar.
 *
 * Die Tabelle ist zugleich das GESCHLOSSENE Gruppenvokabular und erschoepfend: genau die fuenf
 * Gruppen, die es gibt, keine auf Vorrat. Eine erlaubte, aber unbenutzte Gruppe waere eine
 * Zusicherung, die nichts zusichert. */
export const TOKEN_TYPE_BY_GROUP: Readonly<Record<string, string>> = {
  color: 'color',
  radius: 'borderRadius',
  space: 'spacing',
  'font-family': 'fontFamilies',
  text: 'typography',
}

/**
 * Schreibwert eines `typography`-Tokens. **Singular-Schluessel** - die Pluralformen der
 * dokumentierten `TokenTypographyValue` sind die LESEform (`resolvedValue`) und werden als
 * Schreibwert abgelehnt (gemessen).
 *
 * EIN FELD TRAEGT EINEN WERT ODER FEHLT GANZ. Eine leere Zeichenkette ist ein ungueltiger Wert
 * und laesst den ganzen Aufruf scheitern ("Field 0.value is invalid") - am 2026-09-08 an der
 * laufenden Instanz gemessen, nachdem genau daran der erste echte Lauf abgebrochen ist.
 *
 * Wo der Bestand kein Feld hat, FEHLT es deshalb: `--text-xs` und `--text-sm` tragen kein
 * `--font-weight`, nur `--text-3xl` traegt ein `--letter-spacing`. An der Zusage dahinter aendert
 * das nichts - einen Standardwert `400` zu ergaenzen waere weiterhin genau die getippte Wertekopie,
 * die dieser Erzeuger verbietet; das Feld ist nur nicht mehr leer da, sondern gar nicht.
 *
 * `fontSize` traegt seine Einheit (`"12px"`) - ebenfalls gemessen und gueltig.
 */
export interface TypografieWert {
  /** Verweis auf eines der beiden Familientokens statt einer Wiederholung des Namens -
   * Referenzen loesen im Verbundwert nachweislich auf. */
  fontFamily: string
  fontSize: string
  lineHeight: string
  fontWeight?: string
  /** Blanke Zahl in px. Ein em-Wert wird als Tokenwert zwar akzeptiert, kommt an der Textform
   * aber als `0` an (gemessen) - deshalb gegen die Schriftgroesse der Stufe umgerechnet. */
  letterSpacing?: string
}

/** Feste Feldreihenfolge des Verbundwerts. Die ersten drei sind Pflicht, die beiden letzten
 * stehen nur da, wenn `index.css` sie fuehrt. */
export const TYPOGRAFIE_FELDER = [
  'fontFamily',
  'fontSize',
  'lineHeight',
  'fontWeight',
  'letterSpacing',
] as const

export const TYPOGRAFIE_PFLICHTFELDER = ['fontFamily', 'fontSize', 'lineHeight'] as const

export interface PenpotToken {
  /** `<gruppe>.<blatt>`; das Blatt ist der CSS-Tokenname ohne `--` bzw. ohne das Gruppenpraefix,
   * damit ein Entwerfender denselben Namen sieht wie ein Entwickler. */
  name: string
  type: string
  value: string | TypografieWert
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

/** Welche Schriftfamilie eine Typo-Stufe traegt. Es gibt nur eine: das Board hat keine
 * Display-Schrift, `--mono` ist Datenausgaben vorbehalten und wird an der Aufrufstelle gesetzt. */
const TYPO_FAMILIENVERWEIS = '{font-family.sans}'

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
 * EINZIGE BEWUSSTE UEBERSETZUNG DIESES ERZEUGERS: uebernommen wird die Primaerfamilie, nicht der
 * vollstaendige CSS-Stack. Eine Ausweichkette ist eine Browser-Eigenschaft und in einem
 * Entwurfswerkzeug bedeutungslos; ein Schriftname MIT Anfuehrungszeichen findet in Penpot ausserdem
 * keine Schrift. Das ist keine Auslassung, sondern die Uebersetzung.
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

/**
 * Rechnet eine Laufweite in `em` gegen die Schriftgroesse ihrer Stufe in eine blanke px-Zahl um
 * (`-0.02em` bei `64px` -> `-1.28`). GEMESSEN, nicht vermutet: Ein em-Wert wird als Tokenwert
 * akzeptiert und loest auch auf, kommt an der Textform aber als `0` an; als blanke Zahl greift die
 * Laufweite nachweislich.
 */
export function letterSpacingToPixels(value: string, fontSize: string): string {
  const em = /^(-?[0-9]*\.?[0-9]+)em$/.exec(value.trim())
  if (em === null) {
    throw new Error(`Unverstandene Laufweite "${value}".`)
  }
  const pixels = Number(em[1]) * lengthToPixels(fontSize, 'Schriftgroesse der Stufe')
  // Gleitkomma-Reste abschneiden, ohne eine Nachkommastelle zu erfinden: -0.02 * 64 = -1.28.
  return String(Number(pixels.toFixed(4)))
}

/** Die Felder einer Stufe, waehrend sie eingesammelt werden. Erst `festerTypografieWert` macht
 * daraus den Schreibwert - mit fester Feldreihenfolge und ohne leere Felder. */
interface TypoRohwert {
  fontSize?: string
  lineHeight?: string
  fontWeight?: string
  letterSpacing?: string
}

function festerTypografieWert(stufe: string, roh: TypoRohwert): TypografieWert {
  // FEHLSCHLAGEN STATT UEBERSPRINGEN: Groesse und Zeilenhoehe sind Pflicht. Fehlte eine, entstuende
  // sonst ein halbes Token, das in Penpot als gueltig durchginge.
  if (roh.fontSize === undefined || roh.lineHeight === undefined) {
    throw new Error(`Schriftstufe ${stufe} ohne Groesse oder Zeilenhoehe.`)
  }
  const wert: TypografieWert = {
    fontFamily: TYPO_FAMILIENVERWEIS,
    fontSize: roh.fontSize,
    lineHeight: roh.lineHeight,
  }
  // Ein Feld ohne Wert wird WEGGELASSEN, nie als leere Zeichenkette gesetzt - die waere ein
  // ungueltiger Wert und liesse den ganzen Aufruf scheitern (gemessen).
  if (roh.fontWeight !== undefined) wert.fontWeight = roh.fontWeight
  if (roh.letterSpacing !== undefined) wert.letterSpacing = roh.letterSpacing
  return wert
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
  /** Je Stufe genau EIN Verbundtoken, angelegt bei ihrer ersten Deklaration und danach befuellt -
   * dadurch bleibt die Reihenfolge die Deklarationsreihenfolge. */
  const typoStufen = new Map<string, TypoRohwert>()
  /** Reihenfolge der Stufen, damit der feste Wert am Ende an derselben Stelle steht. */
  const typoTokens = new Map<string, PenpotToken>()
  /** Die Laufweite braucht die Schriftgroesse derselben Stufe; sie kann im CSS davor stehen. */
  const offeneLaufweiten: [string, string][] = []

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

    /*
     * `--spacing-header` ist KEIN Design-Token, sondern eine Layout-Konstante der App-Huelle: die
     * Hoehe der fixierten Kopfzeile, aus der `h-header` und `top-header` entstehen. Sie beschreibt
     * nichts, was in Penpot gezeichnet oder gewaehlt wird - ein Token dafuer waere ein Wert ohne
     * Gegenstueck im Entwurf und verschoebe die Kardinalitaeten der Nutzlast. Bewusst NAMENTLICH
     * uebersprungen und nicht ueber ein Praefixmuster: ein kuenftiges, echtes Abstands-Token soll
     * weiterhin im Fehlerzweig landen statt still zu verschwinden.
     */
    if (name === '--spacing-header') {
      continue
    }

    const radius = /^--radius-([a-z0-9]+)$/.exec(name)
    if (radius !== null) {
      tokens.push({ name: `radius.${radius[1]}`, type: TOKEN_TYPE_BY_GROUP.radius, value })
      continue
    }

    const text = /^--text-([a-z0-9]+)(--line-height|--font-weight|--letter-spacing)?$/.exec(name)
    if (text !== null) {
      const stufe = text[1]
      if (value === 'initial') {
        if (text[2] !== undefined) {
          throw new Error(`Unerwartetes "initial" an ${name}.`)
        }
        excludedInitialTokens.push(name)
        continue
      }
      let roh = typoStufen.get(stufe)
      if (roh === undefined) {
        roh = {}
        typoStufen.set(stufe, roh)
        const token: PenpotToken = {
          name: `text.${stufe}`,
          type: TOKEN_TYPE_BY_GROUP.text,
          // Platzhalter; am Ende durch den festen Verbundwert ersetzt.
          value: '',
        }
        typoTokens.set(stufe, token)
        tokens.push(token)
      }
      if (text[2] === undefined) roh.fontSize = value
      else if (text[2] === '--line-height') roh.lineHeight = value
      else if (text[2] === '--font-weight') roh.fontWeight = value
      else offeneLaufweiten.push([stufe, value])
      continue
    }

    throw new Error(`Unverstandene @theme-Deklaration: "${name}: ${value}".`)
  }

  for (const [stufe, laufweite] of offeneLaufweiten) {
    const roh = typoStufen.get(stufe)
    if (roh === undefined || roh.fontSize === undefined) {
      throw new Error(`Laufweite an Stufe ${stufe} ohne zugehoerige Schriftgroesse.`)
    }
    roh.letterSpacing = letterSpacingToPixels(laufweite, roh.fontSize)
  }

  for (const [stufe, token] of typoTokens) {
    token.value = festerTypografieWert(stufe, typoStufen.get(stufe) ?? {})
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
