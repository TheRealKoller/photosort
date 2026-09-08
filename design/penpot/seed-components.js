// LAUFREGEL: nur-auf-leerer-datei
/*
 * Baut die zehn Bausteine und ihre Varianten in der Penpot-Datei
 * "PhotoSort — Dark Utility Register" auf (decisions/0065-penpot-stand-als-erzeugte-idempotente-
 * nutzlast.md Abschnitt 4).
 *
 * ⚠ WARNUNG - LAUFREGEL "nur-auf-leerer-datei": Dieses Skript laeuft NUR auf einer leeren oder neu
 * aufgebauten Datei. Nach dem ersten Bespielen gehoeren die Bausteine Penpot: dort wird entworfen,
 * dort entstehen Aenderungen, und ein Skript, das sie ueberschreibt, machte den Zweck der ganzen
 * Story zunichte. Seine dauerhafte Rolle ist die WIEDERHERSTELLUNG NACH INSTANZVERLUST, nicht die
 * laufende Pflege. Die Vorbedingung steht deshalb FAIL-CLOSED im Skript selbst (siehe
 * `pruefeLeereDatei`), vor dem ersten Schreibzugriff - nach ADR 0064 ist der Penpot-Stand die
 * normative Design-Quelle, ein versehentlicher zweiter Lauf vernichtet also nicht eine Kopie,
 * sondern das Original.
 *
 * AUSFUEHRUNG: ausschliesslich ueber den Skill `penpot-design`. Genau eine Einfuegestelle:
 *   const BAUSTEINE = <exakter Inhalt von components.json>;
 * gefolgt von dieser Datei, unveraendert.
 *
 * DIESES SKRIPT LOESCHT NICHTS.
 *
 * REIHENFOLGE DER DEKLARATIONEN IST ABSICHT: `pruefeLeereDatei` und `main` stehen VOR allen
 * Funktionen, die schreibende Aufrufe enthalten. `payload.test.ts` sichert ueber die GEPARSTE
 * Aufrufstelle zu, dass die Vorbedingung vor dem ersten Schreibzugriff steht; eine Umsortierung
 * dieser Datei faerbt den Test rot.
 *
 * WAS CI HIER NICHT PRUEFEN KANN (Spec 0352, verbindlicher Bestandteil):
 *  1. Diese Datei ist zum Zeitpunkt des Pull Requests UNAUSGEFUEHRTER CODE. Geprueft sind
 *     Erzeugung, Vollstaendigkeit, Benennung, referentielle Integritaet und Wertefreiheit. Ob ein
 *     Plugin-API-Aufruf funktioniert, kann kein Test hier sagen. Ein oder zwei Korrekturrunden
 *     nach dem ersten echten Lauf sind eingeplant, kein Fehlschlag.
 *  2. Kein Test kann Penpot lesen. Der Abgleich ist eine Handlung, keine Zusicherung.
 *  3. Die Dauerregel "entwerfen nur mit Tokens" ist LLM-interpretierter Text; statisch verankert
 *     ist nur, DASS sie im Skill steht.
 */

const SATZ_NAME = 'photosort'

/**
 * Bildet die Rollennamen aus `components.json` auf Penpot-Eigenschaften ab. Die LINKE Seite ist
 * die Design-System-Aussage und im Repository gepflegt; die RECHTE Seite ist der noch nicht
 * gemessene Teil der Plugin-API (ADR 0065 Abschnitt 7) und beim ersten echten Lauf zu bestaetigen.
 *
 * Rollen, die hier fehlen, gehoeren zu Unterelementen, die dieser Aufbau nicht selbst setzt
 * (Vorschlags-Kennzeichen, Statuspille, Knauf des Schalters, Dateiname der Karte, …). Sie werden
 * NICHT stillschweigend uebergangen, sondern als `nachzubinden` zurueckgegeben - die Bindung
 * entsteht dann beim Entwerfen in Penpot, wo diese Elemente ohnehin ihre Form bekommen.
 */
const ROLLE_ZU_EIGENSCHAFT = {
  flaeche: 'fill',
  umriss: 'stroke',
  radius: 'border-radius',
  hoehe: 'height',
  'innenabstand-quer': 'padding-left',
  'innenabstand-laengs': 'padding-top',
  innenabstand: 'padding',
  abstand: 'row-gap',
  schrift: 'fill',
  // Singular, gemessen: der dokumentierte Name `fontFamilies` wirft.
  schriftfamilie: 'fontFamily',
  // Eine Schriftstufe ist EIN Verbundtoken (Groesse, Zeilenhoehe, Schnitt, Laufweite zusammen) -
  // Penpot kennt keinen Token-Typ fuer Zeilenhoehen, und beim Entwerfen wird eine Stufe ohnehin
  // in einem Zug angewandt.
  typografie: 'typography',
}

/** Rollen, die auf die BESCHRIFTUNG wirken statt auf die Flaeche. */
const TEXT_ROLLEN = ['schrift', 'schriftfamilie', 'typografie']

/**
 * FAIL-CLOSED. Bricht ab, sobald die Datei bereits einen der zehn Bausteine traegt. Ein blosser
 * Hinweis genuegte hier nicht: das Ueberschreiben waere unwiederbringlich.
 */
function pruefeLeereDatei() {
  const vorhandene = penpot.library.local.components.map((komponente) => komponente.name)
  const kollisionen = BAUSTEINE.bausteine
    .map((baustein) => baustein.name)
    .filter((name) => vorhandene.includes(name))
  if (kollisionen.length > 0) {
    throw new Error(
      'Abbruch: die Datei traegt bereits Bausteine (' +
        kollisionen.join(', ') +
        '). seed-components.js laeuft nur auf einer leeren oder neu aufgebauten Datei.'
    )
  }
}

function main() {
  pruefeLeereDatei()

  const gebaut = []
  const nachzubinden = []
  for (const baustein of BAUSTEINE.bausteine) {
    const bericht = baueBaustein(baustein)
    gebaut.push(bericht.name)
    for (const offen of bericht.nachzubinden) {
      nachzubinden.push(offen)
    }
  }

  return {
    satz: SATZ_NAME,
    gebaut: gebaut,
    nachzubinden: nachzubinden,
  }
}

// --- Ab hier stehen die schreibenden Aufrufe (siehe "REIHENFOLGE DER DEKLARATIONEN" oben). ---

function findeToken(tokenName) {
  const satz = penpot.library.local.tokens.sets.find((kandidat) => kandidat.name === SATZ_NAME)
  if (!satz) {
    throw new Error('Token-Satz fehlt - seed-tokens.js zuerst ausfuehren.')
  }
  const token = satz.tokens.find((kandidat) => kandidat.name === tokenName)
  if (!token) {
    throw new Error('Unbekanntes Token: ' + tokenName)
  }
  return token
}

/** Gekapselter, noch nicht gemessener API-Punkt: Tokenbindung auf eine benannte Eigenschaft. */
function wendeTokenAn(form, eigenschaft, tokenName) {
  findeToken(tokenName).applyToShapes([form], eigenschaft)
}

function bindeRollen(brett, beschriftung, rollen, herkunft, nachzubinden) {
  for (const rolle of Object.keys(rollen)) {
    const eigenschaft = ROLLE_ZU_EIGENSCHAFT[rolle]
    if (!eigenschaft) {
      nachzubinden.push(herkunft + ': ' + rolle + ' -> ' + rollen[rolle])
      continue
    }
    const ziel = TEXT_ROLLEN.includes(rolle) ? beschriftung : brett
    wendeTokenAn(ziel, eigenschaft, rollen[rolle])
  }
}

function baueAuspraegung(baustein, eigenschaft, auspraegung, nachzubinden) {
  const brett = penpot.createBoard()
  brett.name = eigenschaft + '=' + auspraegung
  brett.addFlexLayout()
  brett.horizontalSizing = 'auto'
  brett.verticalSizing = 'auto'

  const beschriftung = penpot.createText(auspraegung)
  brett.appendChild(beschriftung)

  const herkunft = baustein.schluessel + '/' + brett.name
  bindeRollen(brett, beschriftung, baustein.tokens, herkunft, nachzubinden)

  const proAuspraegung = baustein.tokensProAuspraegung || {}
  const achse = proAuspraegung[eigenschaft] || {}
  const besondere = achse[auspraegung]
  if (besondere) {
    bindeRollen(brett, beschriftung, besondere, herkunft, nachzubinden)
  }

  return brett
}

/**
 * Ein VARIANTEN-Behaelter je Baustein: der Zustand wird dadurch AUSWAEHLBAR, statt als zweites
 * Bild danebengestellt zu werden (Akzeptanzkriterium 4). Der maschinelle Schluessel wandert als
 * Plugin-Daten mit, der deutsche Anzeigename ist der Name des Behaelters.
 *
 * GEMESSEN: `createVariantContainer` BENENNT DIE EINZELKOMPONENTEN IN "Component" UM - der
 * sprechende Name lebt am Behaelter, nicht an den Auspraegungen. Deshalb traegt der Behaelter den
 * Anzeigenamen und die Plugin-Daten; die Brettnamen `eigenschaft=auspraegung` sind ausschliesslich
 * die Vorlage, aus der die Varianteneigenschaften entstehen, und ueberleben den Aufruf nicht.
 */
function baueBaustein(baustein) {
  const nachzubinden = []
  const bretter = []
  for (const eigenschaft of Object.keys(baustein.varianten)) {
    for (const auspraegung of baustein.varianten[eigenschaft]) {
      bretter.push(baueAuspraegung(baustein, eigenschaft, auspraegung, nachzubinden))
    }
  }

  const behaelter = penpotUtils.createVariantContainer(bretter)
  behaelter.name = baustein.name
  behaelter.setPluginData('schluessel', baustein.schluessel)

  return { name: baustein.name, nachzubinden: nachzubinden }
}

JSON.stringify(main(), null, 2)
