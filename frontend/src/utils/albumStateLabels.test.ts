// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ALBUM_STATE_LABELS } from './albumStateLabels'

const SRC_DIR = fileURLToPath(new URL('..', import.meta.url))

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      return sourceFiles(path)
    }
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

describe('ALBUM_STATE_LABELS', () => {
  it('names the three states with three different words', () => {
    const words = Object.values(ALBUM_STATE_LABELS)

    expect(words).toHaveLength(3)
    expect(new Set(words).size).toBe(3)
  })

  it.each(['Vorschlag', 'Aufgenommen', 'Gestrichen'])(
    'holds "%s" as the only whole string literal of the source tree',
    (word) => {
      /* Album-Entwurf und Endauswahl benennen die Haltung zu einem Foto aus EINER Quelle. Ein
       * zweites Literal derselben Bezeichnung liefe beim nächsten Umbenennen still auseinander,
       * und eine Seite spräche dann anders als die andere. Gezählt werden ausschließlich GANZE
       * String-Literale - ein Satz, in dem das Wort vorkommt, ist keine zweite Bezeichnung. */
      const literal = new RegExp(`(['"\`])${word}\\1`, 'g')
      const hits = sourceFiles(SRC_DIR).flatMap((file) =>
        (readFileSync(file, 'utf-8').match(literal) ?? []).map(() => file),
      )

      expect(hits).toHaveLength(1)
      expect(hits[0]).toMatch(/albumStateLabels\.ts$/)
    },
  )
})
