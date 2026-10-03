// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

import { OVERVIEW_TEXTS } from './utils/workflowOverview'

/*
 * Jede Bezeichnung, die ein Erklärtext der Ablaufübersicht in „…" zitiert, steht wörtlich an ihrer
 * Bedienstelle: als ganzes String-Literal oder als ganzer JSX-Text in einer anderen Quelldatei.
 * Ein umbenannter Knopf ließe den Text sonst still auf etwas zeigen, das es nicht mehr gibt.
 */

const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      return sourceFiles(path)
    }
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

function wholeTexts(fileName: string): string[] {
  const file = ts.createSourceFile(
    fileName,
    readFileSync(fileName, 'utf-8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  const found: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      found.push(node.text)
    } else if (ts.isJsxText(node)) {
      found.push(node.text.trim())
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return found
}

const QUOTED = /„([^“]+)“/g

describe('Zitierte Bezeichnungen der Ablaufübersicht', () => {
  const texts = Object.values(OVERVIEW_TEXTS).flatMap((entry) => [
    entry.purpose,
    entry.worker.detail,
    entry.prerequisite?.text ?? '',
  ])
  const quoted = [...new Set(texts.flatMap((text) => [...text.matchAll(QUOTED)].map((m) => m[1])))]
  const literals = new Set(
    sourceFiles(SRC_DIR)
      .filter((file) => !file.endsWith('workflowOverview.ts'))
      .flatMap(wholeTexts),
  )

  it('zitiert überhaupt Bezeichnungen', () => {
    expect(quoted.sort()).toEqual([
      'Aktualisieren',
      'Ausschuss aussortieren',
      'Ausschuss gesichtet, weiter',
      'Endauswahl',
      'Klassifizierung starten',
      'Unterschiede',
    ])
  })

  it.each(quoted)('findet "%s" wörtlich an seiner Bedienstelle', (label) => {
    expect(literals.has(label)).toBe(true)
  })
})
