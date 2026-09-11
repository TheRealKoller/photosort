// LAUFREGEL: nur-auf-leerer-datei
/*
 * Baut die elf Bausteine und ihre Varianten in der Penpot-Datei
 * "PhotoSort — Dark Utility Register" auf (decisions/0066-penpot-stand-als-erzeugte-idempotente-
 * nutzlast.md Abschnitt 4).
 *
 * ⚠ WARNUNG - LAUFREGEL "nur-auf-leerer-datei": Dieses Skript laeuft NUR auf einer leeren oder neu
 * aufgebauten Datei. Nach dem ersten Bespielen gehoeren die Bausteine Penpot: dort wird entworfen,
 * dort entstehen Aenderungen, und ein Skript, das sie ueberschreibt, machte den Zweck der ganzen
 * Story zunichte. Seine dauerhafte Rolle ist die WIEDERHERSTELLUNG NACH INSTANZVERLUST, nicht die
 * laufende Pflege. Die Vorbedingung steht deshalb FAIL-CLOSED im Skript selbst (siehe
 * `pruefeLeereDatei`), vor dem ersten Schreibzugriff - nach ADR 0065 ist der Penpot-Stand die
 * normative Design-Quelle, ein versehentlicher zweiter Lauf vernichtet also nicht eine Kopie,
 * sondern das Original.
 *
 * AUSFUEHRUNG: ausschliesslich ueber den Skill `penpot-design`. Genau eine Einfuegestelle:
 *   const BAUSTEINE = <exakter Inhalt von components.json>;
 * gefolgt von dieser Datei, unveraendert.
 *
 * ⚠ EINE ZEITUEBERSCHREITUNG DIESES AUFRUFS IST KEIN FEHLSCHLAG. 146 Varianten mit je rund einem
 * Dutzend API-Aufrufen dauern laenger, als `execute_code` auf eine Antwort wartet: Der Aufruf
 * endet mit "The operation timed out", waehrend die Arbeit vollstaendig ausgefuehrt wird - beim
 * ersten echten Lauf gemessen, alle Bausteine und alle Bindungen waren danach da. Bei 146
 * Varianten ist das der NORMALFALL, nicht der Ausnahmefall.
 *
 * Vor jeder Reaktion wird der Stand ZURUECKGELESEN (Zahl der Variantenbehaelter und ihrer
 * Auspraegungen). Erst das Ergebnis entscheidet, ob etwas fehlt - nicht die Meldung. Fehlt
 * tatsaechlich etwas, ist die Datei nicht mehr leer, und ein zweiter Lauf trifft den
 * fail-closed-Waechter unten: Dessen Abbruch ist dann die RICHTIGE Antwort und wird nicht
 * umgangen. Der Weg zurueck fuehrt ueber eine leere oder neu aufgebaute Datei, nie ueber den
 * Waechter hinweg - wer ihn fuer den eigentlichen Fehler haelt, zerstoert den gerade gebauten
 * Stand, und der ist nach ADR 0065 das Original, keine Kopie.
 *
 * `execute_code` FUEHRT DEN TEXT ALS FUNKTIONSRUMPF AUS und liefert nur zurueck, was ein `return`
 * zurueckgibt (gemessen) - deshalb endet diese Datei, wie jede Nutzlastdatei, auf ein `return`.
 *
 * DIESES SKRIPT LOESCHT NICHTS.
 *
 * DER ELFTE BAUSTEIN (`skeleton` / "Platzhalter") IST HIER NICHT NACHZUTRAGEN: Dieses Skript
 * zaehlt keinen Baustein auf, es laeuft ueber `BAUSTEINE.bausteine` aus `components.json`. Der
 * neue Eintrag dort wird also mitgebaut, ohne dass eine Zeile hier davon weiss - und das ist der
 * Grund, warum die Bausteinmenge regelgebunden offen sein kann, ohne dass das Aufbauskript
 * gepflegt werden muesste. In der Story, die den Platzhalter aufgenommen hat, LAEUFT dieses
 * Skript nicht: die Datei traegt bereits Bausteine, der Waechter unten greift, und der elfte
 * Baustein entsteht in Penpot von Hand. Mitgezogen wird das Skript ausschliesslich fuer seine
 * dauerhafte Rolle - die WIEDERHERSTELLUNG NACH INSTANZVERLUST, bei der es alle elf aufbaut.
 *
 * WORAN DIE BAUSTEINE WIEDERERKANNT WERDEN: an den Plugin-Daten `schluessel`, die jede
 * Variantenkomponente traegt - NICHT am Namen. `createVariantContainer` benennt die
 * Einzelkomponenten gemessen in "Component" um, und der sprechende Name lebt am Behaelter, der
 * ein Board ist und gar nicht in `penpot.library.local.components` steht. Eine Erkennung am Namen
 * oder am Behaelter fiele deshalb ins Leere - und mit ihr der Waechter oben. `verify.js` benutzt
 * dieselbe Funktion WORTGLEICH; dass beide Fassungen uebereinstimmen, ist statisch zugesichert
 * (`frontend/penpot/payload.test.ts`).
 *
 * ⚠ NEU ERZEUGTE FORMEN WERDEN AUSDRUECKLICH AN DER SEITENWURZEL VERANKERT. Bei
 * `createShapeFromSvg` ist gemessen, dass die Form sonst im zuletzt angelegten Board landet - im
 * ersten echten Lauf der Symbole steckten dadurch alle zwoelf Gruppen ineinander. Ob `createBoard`
 * dieselbe Eigenschaft hat, ist NICHT gemessen; die Verankerung steht hier vorsorglich, weil sie
 * billig und in beiden Faellen richtig ist - und weil eine Verschachtelung bei 146 Auspraegungen
 * ungleich schwerer zu entwirren waere. Aus demselben Grund bekommt jedes Brett eine Position:
 * je Baustein eine Reihe, die Bausteine untereinander. Die Abstaende ergeben sich aus den Massen
 * der Bretter selbst, nicht aus einem getippten Raster.
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
 * ⚠ JEDE ROLLE BILDET AUF EINE LISTE AB, auch wo es nur eine Eigenschaft ist. Zwei Gruende:
 * Penpot kennt **keine Sammelnamen** - `border-radius` und `padding` werfen beide ("Field 1 is
 * invalid: should be a set of strings"), es gibt nur die vier Ecken bzw. die vier Seiten
 * einzeln (gemessen). Und eine Sonderform fuer den Einzelfall ist genau die Stelle, an der es
 * spaeter wieder auseinanderlaeuft. `applyToShapes` nimmt die Liste direkt.
 *
 * Durchgaengig camelCase: Penpot akzeptiert bei Polsterung und Abstand zwar beide Schreibweisen
 * (`padding-left` wie `paddingLeft`, gemessen), aber die vier Radius-Ecken und die vier
 * Polster-Seiten kennen nur camelCase - zwei Schreibweisen nebeneinander koennte spaeter niemand
 * erklaeren.
 *
 * Rollen, die hier fehlen, gehoeren zu Unterelementen, die dieser Aufbau nicht selbst setzt
 * (Vorschlags-Kennzeichen, Statuspille, Knauf des Schalters, Dateiname der Karte, …). Sie werden
 * NICHT stillschweigend uebergangen, sondern als `nachzubinden` zurueckgegeben - die Bindung
 * entsteht dann beim Entwerfen in Penpot, wo diese Elemente ohnehin ihre Form bekommen.
 */
const ROLLE_ZU_EIGENSCHAFT = {
  flaeche: ['fill'],
  umriss: ['strokeColor'],
  radius: [
    'borderRadiusTopLeft',
    'borderRadiusTopRight',
    'borderRadiusBottomRight',
    'borderRadiusBottomLeft',
  ],
  hoehe: ['height'],
  // Quer heisst links UND rechts, laengs oben UND unten - `px-4` setzt beide Seiten.
  'innenabstand-quer': ['paddingLeft', 'paddingRight'],
  'innenabstand-laengs': ['paddingTop', 'paddingBottom'],
  innenabstand: ['paddingLeft', 'paddingRight', 'paddingTop', 'paddingBottom'],
  // `gap-*` setzt in Tailwind beide Achsen.
  abstand: ['rowGap', 'columnGap'],
  schrift: ['fill'],
  // Singular, gemessen: der dokumentierte Name `fontFamilies` wirft.
  schriftfamilie: ['fontFamily'],
  // Eine Schriftstufe ist EIN Verbundtoken (Groesse, Zeilenhoehe, Schnitt, Laufweite zusammen) -
  // Penpot kennt keinen Token-Typ fuer Zeilenhoehen, und beim Entwerfen wird eine Stufe ohnehin
  // in einem Zug angewandt.
  typografie: ['typography'],
}

/** Rollen, die auf die BESCHRIFTUNG wirken statt auf die Flaeche. */
const TEXT_ROLLEN = ['schrift', 'schriftfamilie', 'typografie']

/*
 * DURCHGESEHEN auf die Fehlerklasse des Symbolimports ("eine Gruppe traegt keinen eigenen
 * Strich"): Hier gehen die Tokens an ein BOARD (`brett`) und an eine TEXTFORM (`beschriftung`).
 * Beide tragen ihre Eigenschaften selbst - ein Board hat Fuellung, Umriss, Radius und Polsterung,
 * eine Textform Farbe und Schriftmerkmale. Es gibt an dieser Stelle keine Gruppe, die eine
 * Bindung an ihre Kinder weiterreichen muesste. Sollte hier je eine Gruppe entstehen, gilt
 * dieselbe Regel wie in `seed-icons.js`: auf die Blattformen, nicht auf die Gruppe.
 */

/* GETEILTE ERKENNUNG - wortgleich auch in fix-flaechen.js und verify.js, statisch zugesichert. */
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
 * FAIL-CLOSED. Bricht ab, sobald die Datei bereits einen der Bausteine aus `components.json`
 * traegt - heute elf. Ein blosser Hinweis genuegte hier nicht: das Ueberschreiben waere
 * unwiederbringlich. Die Zahl steht bewusst nicht in der Bedingung: geprueft wird die Kollision
 * je Schluessel, nicht eine Anzahl.
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
  const lage = { x: penpot.viewport.center.x, y: penpot.viewport.center.y, hoehe: 0 }
  for (const baustein of BAUSTEINE.bausteine) {
    const bericht = baueBaustein(baustein, lage)
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

/** Aufrufform gemessen: Formenmenge plus Eigenschaftsliste. */
function wendeTokenAn(formen, eigenschaften, tokenName) {
  findeToken(tokenName).applyToShapes(formen, eigenschaften)
}

/**
 * Bindet die Rollen einer Tabelle und GIBT ZURUECK, welche Penpot-Eigenschaften dabei auf das
 * BRETT angewandt wurden. Der Rueckgabewert traegt die Entscheidung, ob das Brett anschliessend
 * geleert wird (ADR 0081 Abschnitt 1) - er ist das Ergebnis der Bindungslogik und kann von ihr
 * deshalb nicht abweichen.
 *
 * ⚠ EIGENSCHAFTEN, NICHT ROLLENNAMEN. `schrift` bildet ebenfalls auf `fill` ab, geht aber an die
 * BESCHRIFTUNG. Wer die vorgekommenen Rollen sammelt statt der aufs Brett angewandten
 * Eigenschaften, haelt praktisch jede Variante fuer gebunden - und der Fehler bliebe bestehen,
 * waehrend alles gruen ist.
 *
 * Der Nachschlag laeuft ueber EIGENE Schluessel: `constructor` loeste an einem Objektliteral sonst
 * auf, und aus einer unbekannten Rolle wuerde eine scheinbar bekannte.
 */
function bindeRollen(brett, beschriftung, rollen, herkunft, nachzubinden) {
  const gesetzt = []
  for (const rolle of Object.keys(rollen)) {
    const bekannt = Object.prototype.hasOwnProperty.call(ROLLE_ZU_EIGENSCHAFT, rolle)
    const eigenschaften = bekannt ? ROLLE_ZU_EIGENSCHAFT[rolle] : null
    if (!eigenschaften) {
      nachzubinden.push(herkunft + ': ' + rolle + ' -> ' + rollen[rolle])
      continue
    }
    const aufsBrett = TEXT_ROLLEN.indexOf(rolle) === -1
    wendeTokenAn([aufsBrett ? brett : beschriftung], eigenschaften, rollen[rolle])
    if (aufsBrett) {
      for (const eigenschaft of eigenschaften) {
        if (gesetzt.indexOf(eigenschaft) === -1) {
          gesetzt.push(eigenschaft)
        }
      }
    }
  }
  return gesetzt
}

/**
 * DAS KREUZPRODUKT ALLER ACHSEN eines Bausteins.
 *
 * Penpot verlangt je Variante einen Wert fuer JEDE Varianteneigenschaft: Ein Eintrag, der nur
 * `auspraegung=ghost` traegt und zu `groesse`/`zustand` schweigt, ist keine wohldefinierte
 * Variante. Gebaut wird deshalb das vollstaendige Kreuzprodukt der in `components.json`
 * gefuehrten Achsen - die Achsen selbst sind eine Design-System-Aussage und werden hier NICHT
 * reduziert. Das ergibt bei der Schaltflaeche 6 x 3 x 5 = 90 Varianten und ueber alle elf
 * Bausteine 146; das ist viel, aber mechanisch und ohne Urteil abgeleitet.
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
function baueVariante(baustein, kombination, lage, nachzubinden) {
  const brett = penpot.createBoard()
  // Verankerung VOR allem anderen: ein spaeter gesetzter Ort haengt die Form nicht um (gemessen
  // bei `createShapeFromSvg`, hier vorsorglich).
  penpot.root.appendChild(brett)
  brett.name = kombinationsName(kombination)
  brett.addFlexLayout()
  brett.horizontalSizing = 'auto'
  brett.verticalSizing = 'auto'
  brett.x = lage.x
  brett.y = lage.y

  const beschriftung = penpot.createText(brett.name)
  brett.appendChild(beschriftung)

  const herkunft = baustein.schluessel + '/' + brett.name
  let gesetzt = bindeRollen(brett, beschriftung, baustein.tokens, herkunft, nachzubinden)

  const proAuspraegung = baustein.tokensProAuspraegung || {}
  for (const achse of Object.keys(kombination)) {
    const achsenTabelle = proAuspraegung[achse] || {}
    const besondere = achsenTabelle[kombination[achse]]
    if (besondere) {
      gesetzt = gesetzt.concat(bindeRollen(brett, beschriftung, besondere, herkunft, nachzubinden))
    }
  }

  /*
   * BINDEN ODER LEEREN, nie weglassen: Ein neu erzeugtes Board traegt eine DECKEND WEISSE
   * Standardfuellung, nicht etwa keine (2026-09-10 gemessen). Wo nichts gebunden wurde, leuchtet
   * das Brett sonst weiss aus einem dunklen Entwurf heraus, und die Beschriftung darauf erreicht
   * rund 2,2:1.
   *
   * NACH dem Binden und AUSSERHALB der Achsenschleife: Eine Bindung, die auf ein geleertes Brett
   * folgt, waere unbelegt - und `button/ghost/disabled` bekommt seine Flaeche erst in der letzten
   * Iteration. Die 133 gebundenen Bretter werden hier gar nicht erst angefasst.
   */
  if (gesetzt.indexOf('fill') === -1) {
    brett.fills = []
  }

  // Abstand ist eine Brettbreite; die Zeilenhoehe waechst mit dem hoechsten Brett der Reihe.
  lage.x = brett.x + brett.width * 2
  lage.hoehe = Math.max(lage.hoehe, brett.height)

  const komponente = penpot.library.local.createComponent([brett])
  komponente.setPluginData('schluessel', baustein.schluessel)

  return { shape: komponente.mainInstance(), properties: kombination }
}

/**
 * Ein VARIANTEN-Behaelter je Baustein: der Zustand wird dadurch AUSWAEHLBAR, statt als zweites
 * Bild danebengestellt zu werden (Akzeptanzkriterium 4). Der deutsche Anzeigename lebt am
 * Behaelter - die Einzelkomponenten heissen danach gemessen "Component".
 */
function baueBaustein(baustein, lage) {
  const nachzubinden = []
  const eintraege = []
  const zeile = { x: lage.x, y: lage.y, hoehe: lage.hoehe }
  for (const kombination of kombinationen(baustein.varianten)) {
    eintraege.push(baueVariante(baustein, kombination, zeile, nachzubinden))
  }
  // Naechster Baustein beginnt eine Zeile tiefer, wieder am linken Rand.
  lage.y = zeile.y + zeile.hoehe * 2
  lage.hoehe = 0

  const behaelter = penpotUtils.createVariantContainer(eintraege)
  behaelter.name = baustein.name
  behaelter.setPluginData('schluessel', baustein.schluessel)

  return { name: baustein.name, varianten: eintraege.length, nachzubinden: nachzubinden }
}

return JSON.stringify(main(), null, 2)
