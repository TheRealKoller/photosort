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
 * `execute_code` FUEHRT DEN TEXT ALS FUNKTIONSRUMPF AUS und liefert nur zurueck, was ein `return`
 * zurueckgibt (gemessen) - deshalb endet diese Datei, wie alle vier, auf ein `return`.
 *
 * DIESES SKRIPT LOESCHT NICHTS.
 *
 * WORAN DIE BAUSTEINE WIEDERERKANNT WERDEN: an den Plugin-Daten `schluessel`, die jede
 * Variantenkomponente traegt - NICHT am Namen. `createVariantContainer` benennt die
 * Einzelkomponenten gemessen in "Component" um, und der sprechende Name lebt am Behaelter, der
 * ein Board ist und gar nicht in `penpot.library.local.components` steht. Eine Erkennung am Namen
 * oder am Behaelter fiele deshalb ins Leere - und mit ihr der Waechter oben. `verify.js` benutzt
 * dieselbe Funktion WORTGLEICH; dass beide Fassungen uebereinstimmen, ist statisch zugesichert
 * (`frontend/penpot/payload.test.ts`).
 *
 * REIHENFOLGE DER DEKLARATIONEN IST ABSICHT: `pruefeLeereDatei` und `main` stehen VOR allen
 * Funktionen, die schreibende Aufrufe enthalten. `payload.test.ts` sichert ueber die GEPARSTE
 * Aufrufstelle zu, dass die Vorbedingung vor dem ersten Schreibzugriff steht; eine Umsortierung
 * dieser Datei faerbt den Test rot.
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

/**
 * Bildet die Rollennamen aus `components.json` auf Penpot-Eigenschaften ab. Die LINKE Seite ist
 * die Design-System-Aussage und im Repository gepflegt; die RECHTE Seite ist die Plugin-API.
 *
 * Rollen, die hier fehlen, gehoeren zu Unterelementen, die dieser Aufbau nicht selbst setzt
 * (Vorschlags-Kennzeichen, Statuspille, Knauf des Schalters, Dateiname der Karte, …). Sie werden
 * NICHT stillschweigend uebergangen, sondern als `nachzubinden` zurueckgegeben - die Bindung
 * entsteht dann beim Entwerfen in Penpot, wo diese Elemente ohnehin ihre Form bekommen.
 */
const ROLLE_ZU_EIGENSCHAFT = {
  flaeche: 'fill',
  umriss: 'strokeColor',
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

/* GETEILTE ERKENNUNG - wortgleich auch in verify.js, statisch zugesichert. */
function bausteinSchluesselInDatei() {
  const gefunden = []
  for (const komponente of penpot.library.local.components) {
    const schluessel = komponente.getPluginData('schluessel')
    if (schluessel && gefunden.indexOf(schluessel) === -1) {
      gefunden.push(schluessel)
    }
  }
  return gefunden
}

/**
 * FAIL-CLOSED. Bricht ab, sobald die Datei bereits einen der zehn Bausteine traegt. Ein blosser
 * Hinweis genuegte hier nicht: das Ueberschreiben waere unwiederbringlich.
 */
function pruefeLeereDatei() {
  const vorhandene = bausteinSchluesselInDatei()
  const kollisionen = BAUSTEINE.bausteine
    .map((baustein) => baustein.schluessel)
    .filter((schluessel) => vorhandene.indexOf(schluessel) !== -1)
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
    gebaut.push({ name: bericht.name, varianten: bericht.varianten })
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

/** Aufrufform gemessen: Formen-Array plus Eigenschaft als blanke Zeichenkette. */
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
    const ziel = TEXT_ROLLEN.indexOf(rolle) !== -1 ? beschriftung : brett
    wendeTokenAn(ziel, eigenschaft, rollen[rolle])
  }
}

/**
 * DAS KREUZPRODUKT ALLER ACHSEN eines Bausteins.
 *
 * Penpot verlangt je Variante einen Wert fuer JEDE Varianteneigenschaft: Ein Eintrag, der nur
 * `auspraegung=ghost` traegt und zu `groesse`/`zustand` schweigt, ist keine wohldefinierte
 * Variante. Gebaut wird deshalb das vollstaendige Kreuzprodukt der in `components.json`
 * gefuehrten Achsen - die Achsen selbst sind eine Design-System-Aussage und werden hier NICHT
 * reduziert. Das ergibt bei der Schaltflaeche 6 x 3 x 5 = 90 Varianten und ueber alle zehn
 * Bausteine 160; das ist viel, aber mechanisch und ohne Urteil abgeleitet.
 */
function kombinationen(varianten) {
  let ergebnis = [{}]
  for (const achse of Object.keys(varianten)) {
    const naechste = []
    for (const bisher of ergebnis) {
      for (const auspraegung of varianten[achse]) {
        const kopie = Object.assign({}, bisher)
        kopie[achse] = auspraegung
        naechste.push(kopie)
      }
    }
    ergebnis = naechste
  }
  return ergebnis
}

function kombinationsName(kombination) {
  return Object.keys(kombination)
    .map((achse) => achse + '=' + kombination[achse])
    .join(', ')
}

/**
 * Eine Variante: ein Brett mit Beschriftung, dessen Eigenschaften an Tokens gebunden sind, als
 * Bibliotheks-Komponente. Uebergeben wird an den Behaelter die HAUPTINSTANZ der Komponente samt
 * ihrer Achsenwerte - beides gemessene Vorgaben von `createVariantContainer`.
 *
 * Die Plugin-Daten `schluessel` stehen an der KOMPONENTE, nicht nur am Behaelter: Nur so bleibt
 * der Baustein wiedererkennbar, nachdem `createVariantContainer` die Komponenten in "Component"
 * umbenannt hat.
 */
function baueVariante(baustein, kombination, nachzubinden) {
  const brett = penpot.createBoard()
  brett.name = kombinationsName(kombination)
  brett.addFlexLayout()
  brett.horizontalSizing = 'auto'
  brett.verticalSizing = 'auto'

  const beschriftung = penpot.createText(brett.name)
  brett.appendChild(beschriftung)

  const herkunft = baustein.schluessel + '/' + brett.name
  bindeRollen(brett, beschriftung, baustein.tokens, herkunft, nachzubinden)

  const proAuspraegung = baustein.tokensProAuspraegung || {}
  for (const achse of Object.keys(kombination)) {
    const achsenTabelle = proAuspraegung[achse] || {}
    const besondere = achsenTabelle[kombination[achse]]
    if (besondere) {
      bindeRollen(brett, beschriftung, besondere, herkunft, nachzubinden)
    }
  }

  const komponente = penpot.library.local.createComponent([brett])
  komponente.setPluginData('schluessel', baustein.schluessel)

  return { shape: komponente.mainInstance(), properties: kombination }
}

/**
 * Ein VARIANTEN-Behaelter je Baustein: der Zustand wird dadurch AUSWAEHLBAR, statt als zweites
 * Bild danebengestellt zu werden (Akzeptanzkriterium 4). Der deutsche Anzeigename lebt am
 * Behaelter - die Einzelkomponenten heissen danach gemessen "Component".
 */
function baueBaustein(baustein) {
  const nachzubinden = []
  const eintraege = []
  for (const kombination of kombinationen(baustein.varianten)) {
    eintraege.push(baueVariante(baustein, kombination, nachzubinden))
  }

  const behaelter = penpotUtils.createVariantContainer(eintraege)
  behaelter.name = baustein.name
  behaelter.setPluginData('schluessel', baustein.schluessel)

  return { name: baustein.name, varianten: eintraege.length, nachzubinden: nachzubinden }
}

return JSON.stringify(main(), null, 2)
