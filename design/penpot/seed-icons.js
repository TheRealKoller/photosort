// LAUFREGEL: jederzeit-wiederholbar
/*
 * Legt die zwoelf Symbole als Bibliotheks-Komponenten in der Penpot-Datei
 * "PhotoSort — Dark Utility Register" an (decisions/0065-penpot-stand-als-erzeugte-idempotente-
 * nutzlast.md Abschnitt 3).
 *
 * AUSFUEHRUNG: ausschliesslich ueber den Skill `penpot-design`. Genau eine Einfuegestelle:
 *   const ICONS = <exakter Inhalt von icons.json>;
 * gefolgt von dieser Datei, unveraendert.
 *
 * LAUFREGEL "jederzeit-wiederholbar": der Inhalt ist vollstaendig aus `ui/icon.tsx` erzeugt.
 *
 * DAS SVG-MARKUP IST EIN WERT, KEIN DOKUMENTFRAGMENT. Es geht als Zeichenkette an die Plugin-API
 * und wird nie in ein DOM eingehaengt (Spec 0352, Security-Abschnitt 3).
 *
 * `currentColor` HAT IN PENPOT KEINE ENTSPRECHUNG - die Symbole kaemen sonst schwarz oder
 * unsichtbar an. Die Strichfarbe der freistehenden Symbolbibliothek wird deshalb ueber das Token
 * `color.text-h` gesetzt; an einer Verwendungsstelle traegt das Symbol dasselbe Token wie der Text
 * daneben. Das ist die einzige Stelle, an der die Symboluebertragung nicht wertfrei ist.
 *
 * DIESES SKRIPT LOESCHT NICHTS.
 *
 * WAS CI HIER NICHT PRUEFEN KANN (Spec 0352, verbindlicher Bestandteil):
 *  1. Diese Datei ist zum Zeitpunkt des Pull Requests UNAUSGEFUEHRTER CODE. Geprueft sind
 *     Erzeugung, Vollstaendigkeit, Benennung, referentielle Integritaet und Wertefreiheit. Ob ein
 *     Plugin-API-Aufruf funktioniert, kann kein Test hier sagen. Ein oder zwei Korrekturrunden
 *     nach dem ersten echten Lauf sind eingeplant, kein Fehlschlag.
 *  2. Kein Test kann Penpot lesen. Der Abgleich ist eine Handlung, keine Zusicherung.
 *  3. Die Dauerregel "entwerfen nur mit Tokens" ist LLM-interpretierter Text; statisch verankert
 *     ist nur, DASS sie im Skill steht.
 *
 * NICHT GEMESSENE API-PUNKTE (ADR 0065 Abschnitt 7, vor dem ersten Lauf ueber `penpot_api_info`
 * zu bestaetigen): der Weg, auf dem SVG-Markup zu einer Penpot-Form wird, und die Signatur der
 * Tokenanwendung. Beides ist hier in je EINER Funktion gekapselt (`formAusMarkup`,
 * `wendeTokenAn`), damit eine Korrektur eine Stelle betrifft und nicht zwoelf.
 */

const SATZ_NAME = 'photosort'
const SYMBOL_PRAEFIX = 'symbol/'
const STRICH_TOKEN = 'color.text-h'

/** Gekapselter, noch nicht gemessener API-Punkt: SVG-Markup -> Penpot-Form. */
function formAusMarkup(markup) {
  return penpot.createShapeFromSvg(markup)
}

/** Gekapselter, noch nicht gemessener API-Punkt: Tokenbindung auf eine benannte Eigenschaft. */
function wendeTokenAn(form, eigenschaft, tokenName) {
  const satz = penpot.library.local.tokens.sets.find((kandidat) => kandidat.name === SATZ_NAME)
  if (!satz) {
    throw new Error('Token-Satz fehlt - seed-tokens.js zuerst ausfuehren.')
  }
  const token = satz.tokens.find((kandidat) => kandidat.name === tokenName)
  if (!token) {
    throw new Error('Unbekanntes Token: ' + tokenName)
  }
  token.applyToShapes([form], eigenschaft)
}

function findeKomponente(name) {
  return penpot.library.local.components.find((komponente) => komponente.name === name)
}

/** Zielzustands-idempotent: am Namen suchen, anlegen wenn es fehlt. */
function main() {
  const angelegt = []
  const vorhanden = []

  for (const kurzname of Object.keys(ICONS)) {
    const name = SYMBOL_PRAEFIX + kurzname
    if (findeKomponente(name)) {
      vorhanden.push(name)
      continue
    }
    const form = formAusMarkup(ICONS[kurzname])
    form.name = name
    wendeTokenAn(form, 'stroke', STRICH_TOKEN)
    const komponente = penpot.library.local.createComponent([form])
    komponente.name = name
    angelegt.push(name)
  }

  return {
    praefix: SYMBOL_PRAEFIX,
    erwartet: Object.keys(ICONS).length,
    angelegt: angelegt,
    bereitsVorhanden: vorhanden,
  }
}

JSON.stringify(main(), null, 2)
