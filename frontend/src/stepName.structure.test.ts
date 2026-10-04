// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/*
 * Der dritte Schritt heisst an jeder sichtbaren Stelle "Klassifizierung", und die abgelösten
 * Aktionsbeschriftungen der Schrittseiten kommen nicht mehr vor. Mechanischer Beleg über den
 * Syntaxbaum statt über einen Textabgleich: Erfasst werden String- und Template-Literale,
 * JSX-Text und JSX-Attribute - ein Regex über ganze Literale übersähe JSX-Text wie
 * "Zur Kriterien-Bewertung", eine Volltextsuche fiele auf Kommentare herein.
 */

const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))

const OLD_NAMES = [
  /Kriterien[-\u2010\u2011\u00AD\s]*Bewertung/i,
  /Kategorie-Bewertung/,
  /Ausschuss aussortieren/i,
  /Wird aussortiert/i,
  /gesichtet, weiter/i,
  // Als ganzer Knopftext: "Aktualisiert" (Scan-Bilanz) bleibt erlaubt.
  /^\s*Aktualisieren\s*$/,
]

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      return sourceFiles(path)
    }
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

type TextKind = 'string' | 'template' | 'jsx-text'

/** Jeder sichtbar werdende Text einer Quelldatei samt Knotenart. Kommentare sind keine Knoten
 * des Syntaxbaums und kommen deshalb nicht vor. */
function visibleTexts(fileName: string, source: string): { kind: TextKind; text: string }[] {
  const file = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  const found: { kind: TextKind; text: string }[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isStringLiteral(node)) {
      found.push({ kind: 'string', text: node.text })
    } else if (
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node)
    ) {
      found.push({ kind: 'template', text: node.text })
    } else if (ts.isJsxText(node)) {
      found.push({ kind: 'jsx-text', text: node.text })
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return found
}

function offending(fileName: string, source: string): { kind: TextKind; text: string }[] {
  return visibleTexts(fileName, source).filter(({ text }) =>
    OLD_NAMES.some((pattern) => pattern.test(text)),
  )
}

describe('Schrittname "Klassifizierung"', () => {
  it('trägt in keinem sichtbaren Text des Quellbaums den alten Namen', () => {
    const files = sourceFiles(SRC_DIR)
    expect(files.length).toBeGreaterThan(50)

    const hits = files.flatMap((file) =>
      offending(file, readFileSync(file, 'utf-8')).map(
        (hit) => `${relative(SRC_DIR, file)}: ${hit.text.trim()}`,
      ),
    )

    expect(hits).toEqual([])
  })

  it('findet den alten Namen in jeder Knotenart, aber nicht im Kommentar (Gegenprobe)', () => {
    const source = [
      '// Kriterien-Bewertung im Zeilenkommentar zählt nicht',
      '/** Kriterien-Bewertung im Doku-Block zählt nicht */',
      "const a = 'Kriterien-Bewertung läuft'",
      'const b = `Die ${a} Kriterien\u2011Bewertung`',
      'const c = `Kriterienbewertung`',
      "const d = 'Kategorie-Bewertung ist abgeschaltet'",
      'const e = <a title="Zur kriterien bewertung">Zur Kriterien-Bewertung</a>',
    ].join('\n')

    expect(offending('probe.tsx', source)).toEqual([
      { kind: 'string', text: 'Kriterien-Bewertung läuft' },
      { kind: 'template', text: ' Kriterien\u2011Bewertung' },
      { kind: 'template', text: 'Kriterienbewertung' },
      { kind: 'string', text: 'Kategorie-Bewertung ist abgeschaltet' },
      { kind: 'string', text: 'Zur kriterien bewertung' },
      { kind: 'jsx-text', text: 'Zur Kriterien-Bewertung' },
    ])
  })

  it('findet die abgelösten Aktionsbeschriftungen, aber nicht "Aktualisiert" (Gegenprobe)', () => {
    const source = [
      '// Ausschuss aussortieren im Kommentar zählt nicht',
      "const a = 'Ausschuss aussortieren'",
      "const b = busy ? 'Wird aussortiert…' : 'x'",
      'const c = `${n} Ausschuss gesichtet, weiter`',
      'const d = <Button>Aktualisieren</Button>',
      'const e = <dt>Aktualisiert</dt>',
      "const f = 'Daten aktualisieren lassen'",
    ].join('\n')

    expect(offending('probe.tsx', source)).toEqual([
      { kind: 'string', text: 'Ausschuss aussortieren' },
      { kind: 'string', text: 'Wird aussortiert…' },
      { kind: 'template', text: ' Ausschuss gesichtet, weiter' },
      { kind: 'jsx-text', text: 'Aktualisieren' },
    ])
  })
})
