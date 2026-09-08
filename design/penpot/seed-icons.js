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
 * `execute_code` FUEHRT DEN TEXT ALS FUNKTIONSRUMPF AUS und liefert nur zurueck, was ein `return`
 * zurueckgibt (gemessen) - deshalb endet diese Datei, wie alle vier, auf ein `return`.
 *
 * LAUFREGEL "jederzeit-wiederholbar": der Inhalt ist vollstaendig aus `ui/icon.tsx` erzeugt.
 *
 * DAS SVG-MARKUP IST EIN WERT, KEIN DOKUMENTFRAGMENT. Es geht als Zeichenkette an die Plugin-API
 * und wird nie in ein DOM eingehaengt (Spec 0352, Security-Abschnitt 3).
 *
 * `currentColor` HAT IN PENPOT KEINE ENTSPRECHUNG - die Symbole kaemen sonst schwarz oder
 * unsichtbar an. Die Strichfarbe der freistehenden Symbolbibliothek wird deshalb ueber das Token
 * `color.text-h` gesetzt; an einer Verwendungsstelle traegt das Symbol dasselbe Token wie der Text
 * daneben. Das ist die einzige Stelle, an der die Symboluebertragung nicht wertfrei ist. Die
 * Eigenschaft heisst gemessen `strokeColor` - `stroke` wird abgelehnt ("Field 1 is invalid").
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
 * GEMESSEN AN EINER VERBUNDENEN INSTANZ (ADR 0065 Abschnitt 7):
 * `createShapeFromSvg(svgString)` existiert und liefert eine `Group` - der SVG-Weg ist bestaetigt.
 * Sie haengt dabei ein zusaetzliches Kind `base-background` (Rechteck) an, das hier entfernt wird;
 * sonst traegt jedes Symbol eine unsichtbare Flaeche. Das ist zugleich die EINZIGE Stelle, an der
 * eines dieser Skripte etwas entfernt - und sie ist von der abschliessenden Liste gedeckt: das
 * Rechteck ist im selben Lauf vom Skript selbst entstanden.
 *
 * ⚠ `createShapeFromSvg` HAENGT DIE FORM IN DEN ZULETZT ANGELEGTEN CONTAINER. Ohne ausdrueckliches
 * Umhaengen an die Seitenwurzel entstand im ersten echten Lauf EINE Komponente, in der alle zwoelf
 * Symbolgruppen ineinander verschachtelt steckten - sobald `createComponent` aus dem ersten Symbol
 * ein Board macht, landet jede weitere Gruppe als dessen Kind. Eine nachtraeglich gesetzte Position
 * behebt das NICHT (gegengeprueft): Der Elternknoten wird beim Erzeugen entschieden, nicht anhand
 * der Koordinaten. Die Positionierung steht deshalb aus einem anderen Grund da - damit die
 * Bibliothek nicht als Stapel am Ursprung liegt.
 *
 * ⚠ `/` IST IN PENPOT EIN PFADTRENNER, KEIN NAMENSBESTANDTEIL: `symbol/star` wird beim Anlegen zu
 * `{ name: "star", path: "symbol" }` (gemessen). Die Gruppierung ist in der Oberflaeche nuetzlich
 * und bleibt - aber der Vergleich muss sie kennen, sonst trifft die Suche nie und ein zweiter Lauf
 * legte Dubletten an. Dafuer gibt es `symbolNameVon`, wortgleich auch in `verify.js`.
 *
 * ⚠ DER PRAEFIX WIRD GENAU EINMAL GESETZT - am Formnamen. Ihn danach noch einmal ueber
 * `komponente.name` zu setzen, haengt ihn ein ZWEITES Mal vor den bereits bestehenden Pfad
 * (gemessen: `path: "symbol / symbol"`). Der Formname traegt ihn, `createComponent` leitet Pfad und
 * Name daraus ab; die Form auf der Zeichenflaeche heisst dadurch ebenfalls sprechend.
 *
 * ⚠ EINE GRUPPE TRAEGT IN PENPOT KEINEN EIGENEN STRICH. Das Strichfarben-Token auf die Gruppe
 * anzuwenden lief ins Leere (gemessen: Gruppe `tokens: {}`, `strokes: []`, der Pfad darunter
 * schwarz). Angewandt wird es deshalb auf die BLATTFORMEN, rekursiv eingesammelt - die heutigen
 * Symbolgruppen sind flach, aber ein kuenftiges Symbol mit verschachtelter Gruppe verloere sonst
 * still seine Farbe.
 *
 * Der Trenner im GELESENEN `path` ist bei mehrstufigen Pfaden `" / "` (mit Leerzeichen), bei
 * einstufigen schlicht `"symbol"`. Der Vergleich in `symbolNameVon` gilt dem einstufigen Fall -
 * er ist die Stelle, an der ein kuenftig mehrstufiger Pfad still danebengriffe.
 *
 * Die Signatur der Tokenanwendung bleibt in EINER Funktion gekapselt (`wendeTokenAn`), damit eine
 * Korrektur eine Stelle betrifft und nicht zwoelf.
 */

const SATZ_NAME = 'photosort'
const SYMBOL_PFAD = 'symbol'
const STRICH_TOKEN = 'color.text-h'

/* GETEILTE ERKENNUNG - wortgleich auch in verify.js, statisch zugesichert. */
function symbolNameVon(komponente) {
  if (komponente.path !== SYMBOL_PFAD) {
    return ''
  }
  return komponente.name
}

/** Name des Kindes, das `createShapeFromSvg` von sich aus anhaengt (gemessen). */
const HILFSFLAECHE = 'base-background'

/**
 * SVG-Markup -> Penpot-Form.
 *
 * Zwei Dinge geschehen hier zwingend direkt nach dem Erzeugen: das Umhaengen an die Seitenwurzel
 * (sonst landet die Gruppe im zuletzt angelegten Board, siehe Dateikopf) und das Entfernen der von
 * der API selbst eingehaengten Hilfsflaeche - sie ist im selben Lauf entstanden und gehoert damit
 * zu dem, was dieses Skript entfernen darf. Alles andere bleibt unangetastet.
 */
function formAusMarkup(markup) {
  const gruppe = penpot.createShapeFromSvg(markup)
  penpot.root.appendChild(gruppe)
  for (const kind of gruppe.children || []) {
    if (kind.name === HILFSFLAECHE) {
      kind.remove()
    }
  }
  return gruppe
}

/** Sammelt die Blattformen eines Baums ein - REKURSIV, nicht nur eine Ebene tief. */
function blattformen(form, gesammelt) {
  const kinder = form.children || []
  if (kinder.length === 0) {
    gesammelt.push(form)
    return gesammelt
  }
  for (const kind of kinder) {
    blattformen(kind, gesammelt)
  }
  return gesammelt
}

/** Gekapselte Tokenbindung auf eine benannte Eigenschaft. Aufrufform gemessen: `applyToShapes`
 * nimmt eine Formenmenge und die Eigenschaft als blanke Zeichenkette. */
function wendeTokenAn(formen, eigenschaft, tokenName) {
  const satz = penpot.library.local.tokens.sets.find((kandidat) => kandidat.name === SATZ_NAME)
  if (!satz) {
    throw new Error('Token-Satz fehlt - seed-tokens.js zuerst ausfuehren.')
  }
  const token = satz.tokens.find((kandidat) => kandidat.name === tokenName)
  if (!token) {
    throw new Error('Unbekanntes Token: ' + tokenName)
  }
  token.applyToShapes(formen, eigenschaft)
}

function findeKomponente(kurzname) {
  return penpot.library.local.components.find(
    (komponente) => symbolNameVon(komponente) === kurzname
  )
}

/** Zielzustands-idempotent: am Namen suchen, anlegen wenn es fehlt. */
function main() {
  const angelegt = []
  const vorhanden = []
  // Eine Reihe statt eines Stapels am Ursprung. Der Abstand ist eine Symbolbreite - so kommt die
  // Bibliothek ohne getipptes Rastermass aus.
  const lage = { x: penpot.viewport.center.x, y: penpot.viewport.center.y }

  for (const kurzname of Object.keys(ICONS)) {
    if (findeKomponente(kurzname)) {
      vorhanden.push(kurzname)
      continue
    }
    const form = formAusMarkup(ICONS[kurzname])
    form.name = SYMBOL_PFAD + '/' + kurzname
    form.x = lage.x
    form.y = lage.y
    lage.x = form.x + form.width * 2
    // Auf die Blattformen, nicht auf die Gruppe - eine Gruppe traegt keinen eigenen Strich.
    wendeTokenAn(blattformen(form, []), 'strokeColor', STRICH_TOKEN)
    // Der Praefix steht bereits im Formnamen; `createComponent` leitet Pfad und Name daraus ab.
    // Ihn hier erneut zu setzen haengt ihn ein zweites Mal vor.
    penpot.library.local.createComponent([form])
    angelegt.push(kurzname)
  }

  return {
    pfad: SYMBOL_PFAD,
    erwartet: Object.keys(ICONS).length,
    angelegt: angelegt,
    bereitsVorhanden: vorhanden,
  }
}

return JSON.stringify(main(), null, 2)
