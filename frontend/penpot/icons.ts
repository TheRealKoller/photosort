/*
 * Erzeugt die zwoelf Penpot-Symbole aus `frontend/src/components/ui/icon.tsx`
 * (decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md Abschnitt 3).
 *
 * GERENDERT WIRD UEBER DIE PROJEKTEIGENE `Icon`-KOMPONENTE, nicht ueber einen Direktzugriff auf
 * `lucide-react`. Zwei Gruende: Erstens bleibt gueltig, dass `icon.tsx` die einzige Datei im
 * Projekt ist, die aus dem Paket importieren darf (statisch erzwungen in
 * src/designSystem.contract.test.ts - dessen Suchraum endet allerdings bei `src/**`, weshalb
 * `icons.test.ts` die Regel fuer diese Datei eigenstaendig wiederholt). Zweitens sind die
 * Penpot-Symbole dadurch nachweislich genau die, die das Produkt zeichnet, samt zentral gesetzter
 * Strichstaerke 2 und `currentColor`; ein zweiter Bezugsweg koennte davon abweichen, ohne dass es
 * auffaellt.
 *
 * Das gerenderte Markup ist fuer Penpot ein WERT und wird nie in ein Dokument eingehaengt
 * (Spec 0352, Security-Abschnitt 3).
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { Icon, ICON_NAMES } from '../src/components/ui/icon.tsx'

/** Merkmale, die im Produkt-Markup stehen, in Penpot aber schaden oder bedeutungslos sind:
 * `data-icon`/`focusable`/`aria-hidden` sind Haken der Web-Oberflaeche, `width`/`height` machten
 * die Bibliotheksinstanz unskalierbar. `viewBox` bleibt. */
const REMOVED_ATTRIBUTES = ['data-icon', 'focusable', 'aria-hidden', 'width', 'height'] as const

/**
 * Streicht die fuenf Merkmale aus der OEFFNENDEN `<svg>`-Marke - und nur dort: eine unverankerte
 * Ersetzung ueber das ganze Markup naehme einem inneren `<rect width="4">` seine Geometrie.
 * Die Verankerung an einem vorangehenden Leerzeichen ist ebenso wenig Kosmetik: `width` ist
 * Teilzeichenkette von `stroke-width`, und ein Symbol ohne Strichstaerke faellt niemandem auf,
 * bis man es sieht.
 */
export function normalizeIconMarkup(markup: string): string {
  const openingTag = /^<svg\b[^>]*>/.exec(markup)
  if (openingTag === null) {
    throw new Error(`Markup beginnt nicht mit einer <svg>-Marke: "${markup.slice(0, 40)}".`)
  }
  let tag = openingTag[0]
  for (const attribute of REMOVED_ATTRIBUTES) {
    tag = tag.replace(new RegExp(`\\s${attribute}="[^"]*"`, 'g'), '')
  }
  return tag + markup.slice(openingTag[0].length)
}

/** Die zwoelf Symbole als `name -> SVG-Markup`, in der Reihenfolge von `ICON_NAMES`. Der Satz ist
 * auf genau zwoelf festgelegt; ihn stillschweigend zu erweitern waere eine Gestaltungsentscheidung
 * ohne Vorlage (ADR 0066 Abschnitt 3). */
export function buildIcons(): Record<string, string> {
  const icons: Record<string, string> = {}
  for (const name of ICON_NAMES) {
    icons[name] = normalizeIconMarkup(renderToStaticMarkup(createElement(Icon, { name })))
  }
  return icons
}

/** Festgelegte Serialisierung, gleichlautend mit `tokens.ts`. */
export function serializeIcons(icons: Record<string, string>): string {
  return `${JSON.stringify(icons, null, 2)}\n`
}
