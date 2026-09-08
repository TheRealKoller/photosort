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
 * GEMESSEN AM 2026-09-08 an einer verbundenen Instanz (ADR 0065 Abschnitt 7):
 * `createShapeFromSvg(svgString)` existiert und liefert eine `Group` - der SVG-Weg ist bestaetigt.
 * Sie haengt dabei ein zusaetzliches Kind `base-background` (Rechteck) an, das hier entfernt wird;
 * sonst traegt jedes Symbol eine unsichtbare Flaeche. Das ist zugleich die EINZIGE Stelle, an der
 * eines dieser Skripte etwas entfernt - und sie ist von der abschliessenden Liste gedeckt: das
 * Rechteck ist im selben Lauf vom Skript selbst entstanden.
 *
 * Die Signatur der Tokenanwendung bleibt in EINER Funktion gekapselt (`wendeTokenAn`), damit eine
 * Korrektur eine Stelle betrifft und nicht zwoelf.
 */

const SATZ_NAME = 'photosort'
const SYMBOL_PRAEFIX = 'symbol/'
const STRICH_TOKEN = 'color.text-h'

/** Name des Kindes, das `createShapeFromSvg` von sich aus anhaengt (gemessen). */
const HILFSFLAECHE = 'base-background'

/**
 * SVG-Markup -> Penpot-Form. Die von der API selbst eingehaengte Hilfsflaeche wird direkt wieder
 * entfernt - sie ist im selben Lauf entstanden und gehoert damit zu dem, was dieses Skript
 * entfernen darf. Alles andere bleibt unangetastet.
 */
function formAusMarkup(markup) {
  const gruppe = penpot.createShapeFromSvg(markup)
  for (const kind of gruppe.children || []) {
    if (kind.name === HILFSFLAECHE) {
      kind.remove()
    }
  }
  return gruppe
}

/** Gekapselte Tokenbindung auf eine benannte Eigenschaft. */
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
