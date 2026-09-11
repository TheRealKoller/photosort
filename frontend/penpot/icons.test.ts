// @vitest-environment node
/*
 * Erzeugung UND Pruefung der zwoelf Penpot-Symbole (specs/features/0352-penpot-als-alleinige-
 * design-quelle.md, decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md Abschnitt 3).
 *
 * Wie bei den Tokens ist der Test der ERZEUGER: `toMatchFileSnapshot` schreibt
 * `design/penpot/icons.json`; in CI schlaegt eine fehlende Schnappschussdatei fehl.
 *
 * Jede einzelne Zusage der Normalisierung ist ein EIGENER Testfall, damit sie bei einem
 * Paket-Update von `lucide-react` nicht still kippt.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ICON_NAMES } from '../src/components/ui/icon.tsx'
import { buildIcons, normalizeIconMarkup, serializeIcons } from './icons.ts'

const ICONS_JSON_PATH = fileURLToPath(new URL('../../design/penpot/icons.json', import.meta.url))
const ICONS_TS_PATH = fileURLToPath(new URL('./icons.ts', import.meta.url))

const icons = buildIcons()
const iconsSource = readFileSync(ICONS_TS_PATH, 'utf8')

describe('Penpot-Symbole: Erzeugung aus ui/icon.tsx', () => {
  it('erzeugt genau zwoelf Symbole', () => {
    expect(Object.keys(icons)).toHaveLength(12)
  })

  it('traegt exakt die Schluesselmenge von ICON_NAMES, in deren Reihenfolge', () => {
    expect(Object.keys(icons)).toEqual([...ICON_NAMES])
  })

  /*
   * `icons.ts` rendert ueber die PROJEKTEIGENE Komponente `ui/icon.tsx`, nie ueber einen
   * Direktzugriff auf `lucide-react`. Erstens bleibt damit gueltig, dass `icon.tsx` die einzige
   * Datei ist, die aus dem Paket importieren darf; zweitens sind die Penpot-Symbole dadurch
   * nachweislich genau die, die das Produkt zeichnet - samt zentral gesetzter Strichstaerke.
   *
   * DIE REGEL WIRD HIER EIGENSTAENDIG WIEDERHOLT statt vorausgesetzt: der Suchraum des
   * Design-Vertragstests endet bei `src/**`, `frontend/penpot/` liegt ausserhalb.
   */
  it('importiert nicht aus lucide-react, sondern aus der projekteigenen Icon-Komponente', () => {
    expect(iconsSource).not.toMatch(/from\s+'lucide-react'/)
    expect(iconsSource).not.toMatch(/require\(\s*'lucide-react'\s*\)/)
    expect(iconsSource).toMatch(/from\s+'\.\.\/src\/components\/ui\/icon\.tsx'/)
  })

  it('liefert je Symbol ein vollstaendiges SVG-Element', () => {
    for (const [name, markup] of Object.entries(icons)) {
      expect(markup.startsWith('<svg '), name).toBe(true)
      expect(markup.endsWith('</svg>'), name).toBe(true)
      expect(markup, name).toMatch(/<(path|circle|line|rect|polyline|polygon|ellipse)\b/)
    }
  })

  describe('Normalisierung: entfernte Merkmale', () => {
    it('entfernt data-icon', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).not.toContain('data-icon')
      }
    })

    it('entfernt focusable', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).not.toContain('focusable')
      }
    })

    it('entfernt aria-hidden', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).not.toContain('aria-hidden')
      }
    })

    /* Eine feste Pixelgroesse machte die Bibliotheksinstanz in Penpot unskalierbar. Geprueft wird
       ausschliesslich die OEFFNENDE Marke: `image` traegt ein inneres `<rect width="18">`, und das
       ist Geometrie, kein Darstellungsmass. */
    it('entfernt width und height aus der oeffnenden svg-Marke', () => {
      for (const [name, markup] of Object.entries(icons)) {
        const openingTag = /^<svg\b[^>]*>/.exec(markup)
        expect(openingTag, name).not.toBeNull()
        expect(openingTag![0], name).not.toMatch(/\swidth="/)
        expect(openingTag![0], name).not.toMatch(/\sheight="/)
      }
    })

    /* Gegenprobe zur vorigen Zusage: die Geometrie innerer Formen bleibt unangetastet - sonst
       bestuende der Test auch dann, wenn die Normalisierung das halbe Symbol wegraeumte. */
    it('laesst die Geometrie innerer Formen stehen', () => {
      expect(icons.image).toContain('<rect width="18" height="18"')
    })
  })

  describe('Normalisierung: erhaltene Merkmale', () => {
    it('erhaelt viewBox', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).toContain('viewBox="0 0 24 24"')
      }
    })

    it('erhaelt die Board-Strichstaerke 2', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).toContain('stroke-width="2"')
      }
    })

    /* `currentColor` hat in Penpot keine Entsprechung - die Strichfarbe der freistehenden
       Symbolbibliothek wird dort ueber das Token `color.text-h` gesetzt (ADR 0066 Abschnitt 7).
       Im erzeugten Markup bleibt der Wert trotzdem stehen: er ist das, was das Produkt zeichnet. */
    it('erhaelt stroke="currentColor"', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).toContain('stroke="currentColor"')
      }
    })

    it('erhaelt fill="none"', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).toContain('fill="none"')
      }
    })

    it('erhaelt stroke-linecap und stroke-linejoin', () => {
      for (const [name, markup] of Object.entries(icons)) {
        expect(markup, name).toContain('stroke-linecap="round"')
        expect(markup, name).toContain('stroke-linejoin="round"')
      }
    })
  })

  describe('Normalisierung: Selbsttests gegen synthetisches Markup', () => {
    it('entfernt genau die fuenf Merkmale und laesst den Rest stehen', () => {
      const raw =
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" ' +
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
        'stroke-linejoin="round" class="lucide lucide-star" data-icon="star" aria-hidden="true" ' +
        'focusable="false"><path d="M1 1"></path></svg>'
      expect(normalizeIconMarkup(raw)).toBe(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
          'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
          'class="lucide lucide-star"><path d="M1 1"></path></svg>',
      )
    })

    /* `width` ist Teilzeichenkette von `stroke-width` - eine unverankerte Ersetzung naehme dem
       Symbol seine Strichstaerke, und zwar unbemerkt. */
    it('verwechselt stroke-width nicht mit width', () => {
      expect(normalizeIconMarkup('<svg stroke-width="2" width="16"></svg>')).toBe(
        '<svg stroke-width="2"></svg>',
      )
    })

    it('fasst ausschliesslich die oeffnende Marke an', () => {
      expect(normalizeIconMarkup('<svg width="16"><rect width="4" height="4"></rect></svg>')).toBe(
        '<svg><rect width="4" height="4"></rect></svg>',
      )
    })

    it('scheitert an Markup, das kein SVG-Element ist', () => {
      expect(() => normalizeIconMarkup('<div></div>')).toThrow()
    })
  })

  it('gibt keinen Schluessel __proto__ aus', () => {
    expect(serializeIcons(icons)).not.toContain('__proto__')
  })

  it('serialisiert festgelegt: zwei Leerzeichen Einrueckung, abschliessender Zeilenumbruch', () => {
    const serialized = serializeIcons(icons)
    expect(serialized).toBe(`${JSON.stringify(icons, null, 2)}\n`)
    expect(JSON.parse(serialized)).toEqual(icons)
  })

  it('erzeugt design/penpot/icons.json', async () => {
    await expect(serializeIcons(icons)).toMatchFileSnapshot(ICONS_JSON_PATH)
  })
})
