// LAUFREGEL: jederzeit-wiederholbar
/*
 * Legt den Token-Satz `photosort` in der Penpot-Datei "PhotoSort — Dark Utility Register" an bzw.
 * gleicht ihn ab (decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md).
 *
 * AUSFUEHRUNG: ausschliesslich ueber den Skill `penpot-design` in der Hauptsession. Die Nutzlast
 * wird mechanisch zusammengesetzt - genau eine Einfuegestelle der Form
 *   const TOKENS = <exakter Inhalt von tokens.json>;
 * gefolgt von dieser Datei, unveraendert. Werte werden nie im Aufruf angepasst; ist ein Wert
 * falsch, wird `frontend/src/index.css` geaendert und neu erzeugt.
 *
 * `execute_code` FUEHRT DEN TEXT ALS FUNKTIONSRUMPF AUS und liefert nur zurueck, was ein `return`
 * zurueckgibt (gemessen). Ein blanker Ausdruck am Dateiende ginge still verloren - deshalb endet
 * diese Datei, wie jede Nutzlastdatei, auf ein `return`.
 *
 * LAUFREGEL "jederzeit-wiederholbar": Der Inhalt dieser Datei ist vollstaendig erzeugt, in ihm
 * kann keine Gestaltungsabsicht stecken, die nicht auch im Repository stuende. Ein zweiter Lauf
 * erzeugt keine Dubletten.
 *
 * DIESES SKRIPT LOESCHT NICHTS. Ein in Penpot zusaetzlich vorhandenes Token bleibt unangetastet
 * und wird als BEFUND gemeldet, nicht als Fehler gewertet.
 *
 * WAS CI HIER NICHT PRUEFEN KANN (Spec 0352, verbindlicher Bestandteil):
 *  1. Diese Datei ist zum Zeitpunkt des Pull Requests UNAUSGEFUEHRTER CODE. Geprueft sind
 *     Erzeugung, Vollstaendigkeit, Benennung, referentielle Integritaet, Wertefreiheit und die
 *     FORM der API-Aufrufe. Ob ein Plugin-API-Aufruf zur Laufzeit das Gewuenschte bewirkt, kann
 *     kein Test hier sagen. Ein oder zwei Korrekturrunden nach dem ersten echten Lauf sind
 *     eingeplant, kein Fehlschlag.
 *  2. Kein Test kann Penpot lesen. Der Abgleich ist eine Handlung, keine Zusicherung.
 *  3. Die Dauerregel "entwerfen nur mit Tokens" ist LLM-interpretierter Text; statisch verankert
 *     ist nur, DASS sie im Skill steht.
 */

const SATZ_NAME = 'photosort'

/** Aufrufform gemessen: `addSet` nimmt ein Objekt, kein blankes Argument. */
function findeOderLegeSatzAn() {
  const katalog = penpot.library.local.tokens
  const vorhanden = katalog.sets.find((satz) => satz.name === SATZ_NAME)
  if (vorhanden) {
    return vorhanden
  }
  return katalog.addSet({ name: SATZ_NAME })
}

/*
 * EIN TOKEN-SATZ WIRKT ERST NACH `toggleActive()` - gemessen, nicht vermutet: vorher bleibt
 * `resolvedValue` null und keine Bindung greift.
 *
 * `toggleActive` SCHALTET UM und ist damit nicht von sich aus wiederholbar - ein zweiter Lauf
 * schaltete den Satz sonst wieder ab, und die Laufregel "jederzeit-wiederholbar" waere gebrochen.
 * Der lesbare Zustand, an dem sich die Umschaltung festmachen laesst, ist derselbe, an dem die
 * Wirkung gemessen wurde: solange der Satz inaktiv ist, bleibt `resolvedValue` leer.
 */
function stelleSatzAktiv(satz) {
  const probe = satz.tokens[0]
  if (!probe) {
    return false
  }
  if (probe.resolvedValue === null || probe.resolvedValue === undefined) {
    satz.toggleActive()
    return true
  }
  return false
}

/**
 * Vergleicht Tokenwerte STRUKTURELL, nicht per Identitaet. Die sieben Schriftstufen tragen einen
 * Verbundwert (Objekt); ein `!==` waere dort immer wahr, und jeder Lauf meldete sie als
 * "abgeglichen" und schriebe sie neu. Feste Feldreihenfolge, damit der Vergleich nicht an der
 * Schluesselreihenfolge haengt, und ein einelementiges Array gilt als sein eigener Skalar - so
 * legt Penpot eine Schriftfamilie ab.
 */
function kanonisch(wert) {
  if (wert === null || wert === undefined) {
    return ''
  }
  if (Array.isArray(wert)) {
    // Penpot normalisiert einen `fontFamilies`-Wert beim Ablegen zu einem Array ("Inter" ->
    // ["Inter"]). Ein einelementiges Array und derselbe Skalar sind derselbe Wert - ohne diese
    // Zeile meldete der Abgleich beide Schriftfamilien bei jedem Lauf als nicht schreibbar
    // (gemessener Fehlalarm des ersten echten Laufs).
    if (wert.length === 1) {
      return kanonisch(wert[0])
    }
    return wert.map(kanonisch).join(',')
  }
  if (typeof wert !== 'object') {
    return String(wert)
  }
  return Object.keys(wert)
    .sort()
    .map((schluessel) => schluessel + '=' + kanonisch(wert[schluessel]))
    .join('|')
}

/** Zielzustands-idempotent: am Namen suchen, anlegen wenn es fehlt, sonst abgleichen. */
function main() {
  const satz = findeOderLegeSatzAn()
  const bestehende = new Map(satz.tokens.map((token) => [token.name, token]))
  const angelegt = []
  const abgeglichen = []
  const nichtSchreibbar = []

  for (const token of TOKENS) {
    const vorhanden = bestehende.get(token.name)
    if (!vorhanden) {
      // Aufrufform gemessen: EIN Objekt mit `type`, `name`, `value`.
      satz.addToken({ type: token.type, name: token.name, value: token.value })
      angelegt.push(token.name)
      continue
    }
    if (kanonisch(vorhanden.value) === kanonisch(token.value)) {
      continue
    }
    vorhanden.value = token.value
    // Schreibpfad abgesichert: ob `value` ueberhaupt schreibbar ist, ist nicht gemessen. Ein
    // stiller Nicht-Schreiber waere sonst von einem erfolgreichen Abgleich nicht zu unterscheiden.
    if (kanonisch(vorhanden.value) === kanonisch(token.value)) {
      abgeglichen.push(token.name)
    } else {
      nichtSchreibbar.push(token.name)
    }
  }

  const erzeugte = new Set(TOKENS.map((token) => token.name))
  const zusaetzlich = satz.tokens.map((token) => token.name).filter((name) => !erzeugte.has(name))
  const aktiviert = stelleSatzAktiv(satz)

  return {
    satz: SATZ_NAME,
    erwartet: TOKENS.length,
    angelegt: angelegt,
    abgeglichen: abgeglichen,
    nichtSchreibbar: nichtSchreibbar,
    aktiviert: aktiviert,
    zusaetzlichInPenpot: zusaetzlich,
  }
}

return JSON.stringify(main(), null, 2)
