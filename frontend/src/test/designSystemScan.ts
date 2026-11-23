/*
 * Gemeinsamer Unterbau des Design-Vertrags "Dark Utility Register"
 * (specs/features/0320-dark-utility-register.md; Werte in decisions/0055-dark-utility-register-
 * fundament.md und specs/architecture/0005-board-dark-utility-register.md). Die Pruefungen selbst
 * liegen je Regelgruppe in `src/designSystem.*.contract.test.ts` und teilen sich diesen
 * Dateizugriff, den :root-Parser und die Fundstellen-Helfer (Spec 0651).
 *
 * WARUM DIESER DESIGN-VERTRAG UEBERHAUPT EXISTIERT: Die uebrigen Frontend-Tests selektieren
 * konventionsgemaess ueber Rollen, `aria-*` und semantische `data-*` und sind gegenueber einer
 * reinen Umgestaltung blind. Komponententests bekommen bewusst KEINE CSS-Assertions (sie
 * wuerden Stufe 2, Issue #321, nicht ueberleben). Alles, was am Design-System eine ausgerechnete
 * Zusage traegt oder eine Streichung belegen soll, wird stattdessen auf Datei-Ebene geprueft.
 *
 * Nur im Node-Umfeld lauffaehig (Dateisystem); Teil des TS-Projekts `tsconfig.contract.json`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const SRC_DIR = fileURLToPath(new URL('..', import.meta.url))
const FRONTEND_DIR = fileURLToPath(new URL('../..', import.meta.url))

const INDEX_CSS_PATH = join(SRC_DIR, 'index.css')
const INDEX_HTML_PATH = join(FRONTEND_DIR, 'index.html')
const VITE_CONFIG_PATH = join(FRONTEND_DIR, 'vite.config.ts')

export const indexCss = readFileSync(INDEX_CSS_PATH, 'utf8')
export const indexHtml = readFileSync(INDEX_HTML_PATH, 'utf8')
export const viteConfig = readFileSync(VITE_CONFIG_PATH, 'utf8')

// ---------------------------------------------------------------------------------------------
// Dateizugriff
// ---------------------------------------------------------------------------------------------

function walk(dir: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      found.push(...walk(full))
    } else {
      found.push(full)
    }
  }
  return found
}

/**
 * SELBSTAUSSCHLUSS, JE DATEI: Teile des Design-Vertrags, die die gestrichenen Tokens, die alten
 * Hexwerte oder die Suchmuster der Verwendungsregeln als LITERALE tragen (Suchbegriffe,
 * Erwartungstabellen, synthetische Zeilen), sind aus dem Scan ausgenommen - andernfalls fiele der
 * Test ueber seine eigenen Suchmuster. Jeder betroffene Teil steht
 * EINZELN hier: ein Glob oder Muster ueber alle Teile stellte auch jede kuenftige Datei still
 * frei und gilt als nicht abgeschlossen. Ein neuer Teil mit Suchmuster-Literalen wird hier
 * ergaenzt, ein Teil ohne Literale nicht - er wird mitgescannt.
 */
const SELF_EXEMPT_FILES: readonly string[] = [
  // Streichliste: gestrichene Tokens und alte Hexwerte als Suchbegriffe.
  'src/designSystem.tokens.contract.test.ts',
  // Verwendungsregeln: `text-text-disabled`, `--danger` u. a. als Suchmuster der Regeln.
  'src/designSystem.usage.contract.test.ts',
]

/** Alle Dateien unter `frontend/src/**` plus `index.html` und `vite.config.ts` - der Scan darf
 * NICHT auf `index.css` beschraenkt bleiben, sonst blitzt beim PWA-Start weiterhin die alte
 * Manifest-Farbe auf und die CI bliebe gruen. Ausgenommen sind nur die Teile aus `SELF_EXEMPT_FILES` (s.o.). */
export const scannedFiles: { path: string; label: string; content: string }[] = [
  ...walk(SRC_DIR)
    .filter((path) => !SELF_EXEMPT_FILES.includes(`src/${path.slice(SRC_DIR.length)}`))
    .map((path) => ({
      path,
      label: `src/${path.slice(SRC_DIR.length)}`,
      content: readFileSync(path, 'utf8'),
    })),
  { path: INDEX_HTML_PATH, label: 'index.html', content: indexHtml },
  { path: VITE_CONFIG_PATH, label: 'vite.config.ts', content: viteConfig },
]

export const sourceFiles = scannedFiles.filter(
  (file) =>
    file.label.endsWith('.tsx') || (file.label.endsWith('.ts') && file.label.startsWith('src/')),
)

export function findOccurrences(needle: string | RegExp): string[] {
  const pattern =
    typeof needle === 'string'
      ? null
      : new RegExp(needle.source, needle.flags.replace('g', '') + 'g')
  const hits: string[] = []
  for (const file of scannedFiles) {
    const lines = file.content.split('\n')
    lines.forEach((line, index) => {
      const match = pattern === null ? line.includes(needle as string) : pattern.test(line)
      if (pattern !== null) pattern.lastIndex = 0
      if (match) hits.push(`${file.label}:${index + 1}: ${line.trim()}`)
    })
  }
  return hits
}

// ---------------------------------------------------------------------------------------------
// :root-Parser
// ---------------------------------------------------------------------------------------------

function parseRootTokens(css: string): Map<string, string> {
  const openIndex = css.indexOf(':root {')
  if (openIndex === -1) {
    throw new Error('Kein :root-Block in index.css gefunden.')
  }
  let depth = 0
  let end = -1
  const braceStart = css.indexOf('{', openIndex)
  for (let i = braceStart; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    else if (css[i] === '}') {
      depth -= 1
      if (depth === 0) {
        end = i
        break
      }
    }
  }
  if (end === -1) {
    throw new Error(':root-Block in index.css ist nicht geschlossen.')
  }

  const body = css.slice(braceStart + 1, end).replace(/\/\*[\s\S]*?\*\//g, '')
  const tokens = new Map<string, string>()
  for (const raw of body.split(';')) {
    const declaration = raw.trim()
    if (declaration.length === 0) continue
    // Bewusst KEIN stilles Ueberspringen: eine unparsebare Zeile ist genau die Fehlerklasse,
    // gegen die dieser Test antritt (ein ungeprueftes Token mit gruener CI).
    const match = /^(--[a-z0-9-]+)\s*:\s*([^]+)$/.exec(declaration)
    if (match === null) {
      throw new Error(`Unparsebare Deklaration im :root-Block: "${declaration}"`)
    }
    tokens.set(match[1], match[2].trim())
  }
  return tokens
}

export const rootTokens = parseRootTokens(indexCss)

export function hexOf(token: string): string {
  const value = rootTokens.get(token)
  if (value === undefined) {
    throw new Error(`Token ${token} ist in index.css nicht deklariert.`)
  }
  if (!/^#[0-9a-fA-F]{6}$/.test(value)) {
    throw new Error(`Token ${token} traegt keinen 6-stelligen Hexwert, sondern "${value}".`)
  }
  return value
}

/**
 * Maskiert Regex-Metazeichen in einem Suchbegriff. Die Hexwerte unten enthalten heute keine - die
 * Absicht war trotzdem Maskierung, und sie stand vorher als `hex.replace('#', '#')` da: ein
 * No-Op, der aussah, als taete er etwas (CodeQL-Alert im PR #322). Entweder richtig maskieren
 * oder gar nicht - hier richtig, damit ein spaeter ergaenzter Suchbegriff mit Sonderzeichen nicht
 * still zu einem anderen Muster wird.
 */
export function escapeForRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Entfernt Kommentarinhalt ZEILENTREU: Kommentartext wird durch Leerzeichen ersetzt, Zeilenumbrueche
 * bleiben erhalten. Ohne die Zeilentreue verschoebe ein mehrzeiliger Blockkommentar alle folgenden
 * Zeilennummern, und die Fundstellen-Meldungen des Helfers unten zeigten auf die falsche Zeile.
 */
export function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, ' '))
    .replace(/^\s*\/\/.*$/gm, (comment) => ' '.repeat(comment.length))
}

// ---------------------------------------------------------------------------------------------
// Fundstellengenaue Freigabelisten
// ---------------------------------------------------------------------------------------------

export interface ScannedFile {
  label: string
  content: string
}

/** Eine Freigabe gilt fuer GENAU EINE Zeile einer Datei, nicht fuer die ganze Datei. */
export interface AllowlistEntry {
  file: string
  /** Teilzeichenkette der freigegebenen Zeile. Darf nicht nur aus dem Suchbegriff bestehen. */
  snippet: string
  reason: string
}

export interface Occurrence {
  label: string
  line: number
  text: string
  match: string
}

/**
 * Suchbegriff einer fundstellengenauen Regel. Drei Formen, in aufsteigender Ausdrucksstaerke:
 * feste Zeichenkette, regulaerer Ausdruck, oder ein ERKENNER - eine reine Funktion, die die
 * Treffer einer Zeile liefert. Die dritte Form gibt es, weil sich "Abstandsstufe ausserhalb der
 * Skala" nicht sinnvoll als ein einziger regulaerer Ausdruck schreiben laesst; als eigene Funktion
 * ist der Erkenner ausserdem tabellengetrieben gegen synthetische Zeilen pruefbar, statt inline in
 * einer Assertion vergraben zu sein.
 */
export type Needle = string | RegExp | ((line: string) => string[])

/**
 * Alle Fundstellen eines Suchbegriffs, zeilengenau und ohne Kommentare. Bei einem regulaeren
 * Ausdruck bzw. einem Erkenner traegt jede Fundstelle zusaetzlich den tatsaechlich getroffenen Text.
 */
export function findMatches(needle: Needle, files: ScannedFile[]): Occurrence[] {
  const found: Occurrence[] = []
  for (const file of files) {
    stripComments(file.content)
      .split('\n')
      .forEach((line, index) => {
        const base = { label: file.label, line: index + 1, text: line.trim() }
        if (typeof needle === 'string') {
          if (line.includes(needle)) found.push({ ...base, match: needle })
          return
        }
        if (typeof needle === 'function') {
          for (const match of new Set(needle(line))) {
            found.push({ ...base, match })
          }
          return
        }
        const pattern = new RegExp(
          needle.source,
          needle.flags.includes('g') ? needle.flags : `${needle.flags}g`,
        )
        const seen = new Set<string>()
        let match: RegExpExecArray | null
        while ((match = pattern.exec(line)) !== null) {
          if (match[0].length === 0) {
            pattern.lastIndex += 1
            continue
          }
          // Mehrfachtreffer desselben Textes in einer Zeile sind EINE Fundstelle - sonst
          // meldete `gap-1.5 sm:gap-1.5` zweimal dasselbe.
          if (!seen.has(match[0])) {
            seen.add(match[0])
            found.push({ ...base, match: match[0] })
          }
        }
      })
  }
  return found
}

/** Deckt der Suchbegriff den ganzen Ausschnitt ab, ist der Ausschnitt nur der Suchbegriff. */
function isBareNeedle(snippet: string, needle: Needle): boolean {
  const trimmed = snippet.trim()
  if (typeof needle === 'string') {
    return trimmed === needle
  }
  if (typeof needle === 'function') {
    return needle(trimmed).includes(trimmed)
  }
  const match = new RegExp(needle.source, needle.flags.replace('g', '')).exec(trimmed)
  return match !== null && match[0] === trimmed
}

/**
 * Gleicht jede Fundstelle eines Suchbegriffs gegen eine fundstellengenaue Freigabeliste ab und
 * meldet DREI Fehlerklassen statt einer:
 *
 *  (a) Fundstelle ohne passenden Eintrag - die eigentliche Regel.
 *  (b) Eintrag ohne Fundstelle - verwaiste Freigabe. Genau daran verrotten solche Listen: die
 *      Zeile verschwindet, die Freigabe bleibt und deckt spaeter still etwas anderes.
 *  (c) Ausschnitt, der nur aus dem Suchbegriff selbst besteht - sonst liesse sich die alte,
 *      dateiweise Granularitaet still wiederherstellen.
 *
 * Die zu durchsuchenden Dateien sind Parameter, damit der Helfer gegen synthetische Eingaben
 * testbar ist, ohne das Dateisystem anzufassen.
 */
export function allowlistedOccurrences(
  needle: Needle,
  entries: AllowlistEntry[],
  files: ScannedFile[] = tsxFiles(),
): string[] {
  const problems: string[] = []
  const matched = new Set<number>()

  for (const occurrence of findMatches(needle, files)) {
    const index = entries.findIndex(
      (entry) => entry.file === occurrence.label && occurrence.text.includes(entry.snippet),
    )
    if (index === -1) {
      problems.push(`nicht freigegeben: ${occurrence.label}:${occurrence.line}: ${occurrence.text}`)
    } else {
      matched.add(index)
    }
  }

  entries.forEach((entry, index) => {
    if (!matched.has(index)) {
      problems.push(`verwaiste Freigabe ohne Fundstelle: ${entry.file} :: ${entry.snippet}`)
    }
    if (isBareNeedle(entry.snippet, needle)) {
      problems.push(`Ausschnitt ist nur der Suchbegriff selbst: ${entry.file} :: ${entry.snippet}`)
    }
  })

  return problems
}

/** String-Literale einer Quelldatei. Template-Literale mit `${` werden uebersprungen - sonst
 * entstehen Fehlalarme aus zusammengesetzten Strings, die zur Laufzeit ganz anders aussehen. */
export function stringLiterals(source: string): string[] {
  const stripped = stripComments(source)
  const literals: string[] = []
  const pattern = /'([^'\\\n]*)'|"([^"\\\n]*)"|`([^`\\]*)`/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(stripped)) !== null) {
    const value = match[1] ?? match[2] ?? match[3]
    if (value === undefined) continue
    if (value.includes('${')) continue
    literals.push(value)
  }
  return literals
}

export function tsxFiles(): typeof sourceFiles {
  return sourceFiles.filter((file) => file.label.endsWith('.tsx'))
}

/**
 * Nur die Produktivdateien. Die Skalenregeln unten gelten fuer das MARKUP des Produkts, nicht fuer
 * Testdateien: dort stehen Klassennamen als Zeichenketten in Assertionen (z.B. `input.test.tsx`
 * haelt `focus:border-[1.5px]` fest), und eine Regel, die dort anschlaegt, zwingt dazu, genau die
 * Zusicherung zu loeschen, die sie absichern soll. Ebenfalls nicht dazu gehoeren die gemeinsamen
 * Testbausteine unter `src/test/` (Spec 0651): sie sind Testcode, und die Menge der Produktivdateien
 * bleibt damit dieselbe wie vor dem Umbau.
 */
export function productionTsxFiles(): typeof sourceFiles {
  return tsxFiles().filter(
    (file) => !file.label.endsWith('.test.tsx') && !file.label.startsWith('src/test/'),
  )
}
