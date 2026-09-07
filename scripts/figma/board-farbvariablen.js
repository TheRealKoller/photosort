/*
 * board-farbvariablen.js - der use_figma-Payload fuer Spec 0336 (ADR 0062).
 *
 * ACHTUNG, andere Laufzeit: Diese Datei laeuft NICHT hier, sondern im Plugin-Kontext der
 * Figma-Datei "Photosort Dark" - einem fremden, gehosteten System, in dem sie Schreibrechte hat.
 * Sie wird von der Hauptsession unveraendert dorthin gesendet. Bevor du sie aenderst, lies
 * scripts/figma/README.md: dort stehen der Ablauf, das Aufrufbudget, die Wiederaufnahme, die
 * Wiederherstellung und die byteweise Verbotsliste im Wortlaut, die
 * scripts/tests/test_figma_farbregister.py ueber diese Datei laufen laesst.
 *
 * Der Payload traegt das Farbregister als abgegrenzten, strikt JSON-parsbaren Block in sich -
 * kein zweites Registerdokument, kein Zusammensetzen vor dem Senden. Zwei Dateien, von denen eine
 * ausgefuehrt und eine geprueft wird, sind zwei Abbilder derselben Aussage, und zwei Abbilder
 * driften. Die Pruefung liest genau den Block, der auch ausgefuehrt worden ist.
 *
 * Der Payload trennt seine REINEN Teile (Register, pruefeVorkommen) von den Figma-API-Teilen und
 * legt sie unter node in globalThis.__PRUEFTEILE ab. In Figma ist `figma` definiert, der
 * ausgefuehrte Pfad ist davon unberuehrt; unter node laedt die Pruefung dieselbe Datei und ruft
 * die Entscheidungsfunktion mit Fixtures auf, statt ihren Quelltext nach Schluesselwoertern zu
 * durchsuchen.
 *
 * ZU DEN SCOPES: Sie sind aus den im Repository belegten Verwendungen abgeleitet
 * (specs/architecture/0005-board-dark-utility-register.md), nicht geraten, und bleiben dort
 * getrennt, wo die Trennung belegt ist - eine Chip-Flaeche ist nie Schrift, eine Chip-Schrift nie
 * Flaeche. Die Textstufen tragen zusaetzlich STROKE_COLOR, weil die zwoelf Board-Symbole
 * gestrichene Vektoren sind (Abschnitt 7 der Board-Referenz nennt `stroke="white"` ausdruecklich);
 * Hintergrund/Basis traegt zusaetzlich TEXT_FILL und STROKE_COLOR, weil die dunkle Tinte auf
 * gefuellten Flaechen im Board Schrift und Symbol ist. Deckt ein Scope die tatsaechliche
 * Eigenschaft nicht, meldet die Vorpruefung das als Abbruchgrund, statt die Diskrepanz still zu
 * lassen - korrigiert wird dann am Register, was nichts kostet.
 */

const REGISTER =
/* REGISTER-ANFANG */
{
  "boardName": "photosort-design-system",
  "boardKnotenId": "2:4",
  "fileKey": "zFiuhI1yjTzAQVQnceBiLC",
  "collection": "PhotoSort Farben",
  "modus": "Dunkel",
  "versionVorher": "V1.2",
  "versionNachher": "V1.3",
  "knotenGesamt": 459,
  "vorkommenGesamt": 418,
  "vorkommenFills": 318,
  "vorkommenStrokes": 100,
  "variablen": [
    {
      "name": "Hintergrund/Basis",
      "wert": "#0B0C10",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Tiefster Grund der Oberfläche, trägt den Bildfokus; zugleich die dunkle Tinte auf gefüllten Flächen (Badges, Primärschaltfläche). Hexwert #0B0C10, im Code --bg.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Hintergrund/Oberfläche",
      "wert": "#14161F",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Standard-Container und Paneele, zweite der vier Flächenstufen. Hexwert #14161F, im Code --surface.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Hintergrund/Erhöht",
      "wert": "#1E2230",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Karten, schwebende Elemente und Meldungen. Hexwert #1E2230, im Code --elevated.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Hintergrund/Overlay",
      "wert": "#262B3D",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Modale Dialoge, Tooltips und die Fläche des Sekundär-Buttons. Hexwert #262B3D, im Code --overlay.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Akzent/Primär",
      "wert": "#FFB000",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Auswahl, Favoriten, aktive Bedienelemente und laufende Vorgänge. Hexwert #FFB000, im Code --accent und --rating-favorite.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Akzent/Info",
      "wert": "#00E5FF",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Informationszustände und Hinweise. Hexwert #00E5FF, im Code --info.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Akzent/Aussortiert",
      "wert": "#FF3D00",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Zur Aussonderung gekennzeichnet: Fläche, Rand und Symbol. Hexwert #FF3D00, im Code --danger. Als Fließtext gilt stattdessen die aufgehellte Textstufe --danger-text, die das Board nicht kennt.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Akzent/Album-würdig",
      "wert": "#00E676",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Für Export und Alben bestätigt, außerdem Erfolgsmeldungen. Hexwert #00E676, im Code --accent-2 und --rating-album-worthy.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Text/Primär",
      "wert": "#FFFFFF",
      "altwerte": [],
      "scopes": ["TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Höchster Kontrast: Überschriften und Hervorhebungen, dazu die gestrichenen Symbole in Weiß. Hexwert #FFFFFF, im Code --text-h.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Text/Sekundär",
      "wert": "#A0A5B5",
      "altwerte": [],
      "scopes": ["TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Fließtext, Beschriftungen und ruhende Navigationselemente. Hexwert #A0A5B5, im Code --text.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Text/Gedämpft",
      "wert": "#8D92A4",
      "altwerte": ["#62677A"],
      "scopes": ["TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Inaktive Metadaten, Hotkeys und Tabellenköpfe. Hexwert #8D92A4, im Code --text-muted. KORREKTUR gegenüber dem Board-Wert #62677A: der verfehlt 4,5:1 auf allen vier Flächen (3,48/3,21/2,82/2,50), trägt im Board aber echten Fließtext; #8D92A4 ist der dunkelste Wert derselben Farbfamilie, der AA überall hält (ADR 0055 Punkt 4a). #62677A ist bewusst nicht zurückzuschreiben - die App liefert diesen Wert nicht aus.",
      "erwarteteVorkommen": 47,
      "neu": false
    },
    {
      "name": "Text/Deaktiviert",
      "wert": "#3E4252",
      "altwerte": [],
      "scopes": ["TEXT_FILL", "STROKE_COLOR"],
      "beschreibung": "Ausschließlich an inaktiven Bedienelementen, nie auf Inhaltstext - WCAG nimmt inaktive Bedienelemente ausdrücklich vom Kontrastkriterium aus. Hexwert #3E4252, im Code --text-disabled.",
      "erwarteteVorkommen": null,
      "neu": false
    },
    {
      "name": "Rahmen/Trennlinie",
      "wert": "#2A2E3D",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL", "STROKE_COLOR"],
      "beschreibung": "Dekorative Trenn- und Panellinie, zugleich Fläche des gedrückten Sekundär- und Ghost-Buttons und Spur der Fortschrittsanzeige. Deshalb Linie und Fläche zugleich. Hexwert #2A2E3D, im Code --border. Als sichtbarer Umriss eines Bedienelements gilt stattdessen --border-control, das das Board nicht kennt.",
      "erwarteteVorkommen": 72,
      "neu": true
    },
    {
      "name": "Kategorie/Menschen/Fläche",
      "wert": "#4D3814",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Chip-Fläche der Kategorie Menschen. Hexwert #4D3814, im Code --chip-menschen-bg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Menschen/Schrift",
      "wert": "#FFC107",
      "altwerte": [],
      "scopes": ["TEXT_FILL"],
      "beschreibung": "Chip-Schrift der Kategorie Menschen. Hexwert #FFC107, im Code --chip-menschen-fg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Tier/Fläche",
      "wert": "#163E3C",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Chip-Fläche der Kategorie Tier. Hexwert #163E3C, im Code --chip-tier-bg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Tier/Schrift",
      "wert": "#00F5D4",
      "altwerte": [],
      "scopes": ["TEXT_FILL"],
      "beschreibung": "Chip-Schrift der Kategorie Tier. Hexwert #00F5D4, im Code --chip-tier-fg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Landschaft/Fläche",
      "wert": "#1F2B49",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Chip-Fläche der Kategorie Landschaft. Hexwert #1F2B49, im Code --chip-landschaft-bg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Landschaft/Schrift",
      "wert": "#00B4D8",
      "altwerte": [],
      "scopes": ["TEXT_FILL"],
      "beschreibung": "Chip-Schrift der Kategorie Landschaft. Hexwert #00B4D8, im Code --chip-landschaft-fg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Gebäude & Bauwerk/Fläche",
      "wert": "#3B1F43",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Chip-Fläche der Kategorie Gebäude & Bauwerk. Hexwert #3B1F43, im Code --chip-gebaeude-bauwerk-bg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Gebäude & Bauwerk/Schrift",
      "wert": "#FF44A1",
      "altwerte": ["#FF007F"],
      "scopes": ["TEXT_FILL"],
      "beschreibung": "Chip-Schrift der Kategorie Gebäude & Bauwerk. Hexwert #FF44A1, im Code --chip-gebaeude-bauwerk-fg. KORREKTUR gegenüber dem Board-Wert #FF007F: der erreicht auf der Chip-Fläche #3B1F43 nur 3,80:1, die Beschriftung ist mit 12px kein Large Text, 4,5:1 gilt (ADR 0055 Punkt 4f). #FF007F ist bewusst nicht zurückzuschreiben - die App liefert diesen Wert nicht aus.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Essen & Trinken/Fläche",
      "wert": "#143C22",
      "altwerte": [],
      "scopes": ["FRAME_FILL", "SHAPE_FILL"],
      "beschreibung": "Chip-Fläche der Kategorie Essen & Trinken. Hexwert #143C22, im Code --chip-essen-trinken-bg.",
      "erwarteteVorkommen": 1,
      "neu": true
    },
    {
      "name": "Kategorie/Essen & Trinken/Schrift",
      "wert": "#70E000",
      "altwerte": [],
      "scopes": ["TEXT_FILL"],
      "beschreibung": "Chip-Schrift der Kategorie Essen & Trinken. Hexwert #70E000, im Code --chip-essen-trinken-fg.",
      "erwarteteVorkommen": 1,
      "neu": true
    }
  ],
  "restVorkommen": {
    "summe": 289,
    "variablen": [
      "Hintergrund/Basis",
      "Hintergrund/Oberfläche",
      "Hintergrund/Erhöht",
      "Hintergrund/Overlay",
      "Akzent/Primär",
      "Akzent/Info",
      "Akzent/Aussortiert",
      "Akzent/Album-würdig",
      "Text/Primär",
      "Text/Sekundär",
      "Text/Deaktiviert"
    ]
  },
  "codeEigeneWerte": [
    {
      "token": "--chip-pflanze-bg",
      "wert": "#194321",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Pflanze (H 131). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-pflanze-fg",
      "wert": "#00D627",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Pflanze (H 131). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-innenraum-bg",
      "wert": "#1E1943",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Innenraum (H 248). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-innenraum-fg",
      "wert": "#8C7AFF",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Innenraum (H 248). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-fahrzeug-bg",
      "wert": "#192743",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Fahrzeug (H 220). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-fahrzeug-fg",
      "wert": "#578FFF",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Fahrzeug (H 220). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-gegenstand-bg",
      "wert": "#43191C",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Gegenstand (H 355). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-gegenstand-fg",
      "wert": "#FF5260",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Gegenstand (H 355). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-dokument-screenshot-bg",
      "wert": "#424319",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Dokument & Screenshot (H 62). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-dokument-screenshot-fg",
      "wert": "#CFD600",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Dokument & Screenshot (H 62). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-kunst-kreatives-bg",
      "wert": "#431940",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Kunst & Kreatives (H 304). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-kunst-kreatives-fg",
      "wert": "#FF2EF1",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Kunst & Kreatives (H 304). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-sport-aktivitaet-bg",
      "wert": "#321943",
      "begruendung": "Fläche des abgeleiteten Kategorie-Paars Sport & Aktivität (H 276). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--chip-sport-aktivitaet-fg",
      "wert": "#C266FF",
      "begruendung": "Schrift des abgeleiteten Kategorie-Paars Sport & Aktivität (H 276). Nach der Ableitungsregel gerechnet, nicht entworfen; kommt auf dem Board nicht vor."
    },
    {
      "token": "--border-control",
      "wert": "#727891",
      "begruendung": "Sichtbarer Umriss eines Bedienelements. Das Board benutzt dafür die dekorative Rahmenfarbe #2A2E3D, die 3:1 deutlich verfehlt; beim Sekundär-Button ist der Umriss aber das einzige Identifikationsmerkmal."
    },
    {
      "token": "--separator",
      "wert": "#474E68",
      "begruendung": "Linie unmittelbar auf dem Grund, aus der Rahmenfarbe abgeleitet (gleicher Farbton, eine Helligkeitsstufe darüber). Das Board kennt nur die Panelkante, keine freistehende Trennlinie."
    },
    {
      "token": "--danger-text",
      "wert": "#FF5A26",
      "begruendung": "Textstufe der Aussortiert-Farbe. Das Board kennt nur die Flächenfarbe #FF3D00, die auf den beiden oberen Flächenstufen als Fließtext zu wenig Kontrast trägt."
    }
  ]
}
/* REGISTER-ENDE */
;

/* --- Reine Teile: die Vorpruefung ------------------------------------------------------------
 *
 * Reine Teile heisst: keine Figma-API, kein Zustand, kein Seiteneffekt. Sie werden vom Test in
 * ihrer eigenen Laufzeit AUSGEFUEHRT, nicht im Quelltext nach Schreibweisen durchsucht.
 */

/** Bildet jeden Hexwert des Registers auf seine Variable ab - Sollwerte und Altwerte.
 *
 * Die Altwerte sind der Grund, warum die Vorpruefung an den 48 zu korrigierenden Vorkommen nicht
 * abbricht: Sie tragen heute den vom Projekt verworfenen Board-Wert und sind damit erklaert, ohne
 * dass dieser Wert je wieder Sollwert einer Variable wuerde.
 */
function variablenNachHex(register) {
  const abbild = new Map();
  for (const eintrag of register.variablen) {
    abbild.set(eintrag.wert, eintrag);
    for (const altwert of eintrag.altwerte) {
      abbild.set(altwert, eintrag);
    }
  }
  return abbild;
}

/** Deckt der Scope der Variable die Eigenschaft, auf der das Vorkommen sitzt?
 *
 * Ein Fill kann auf einem Rahmen, einer Form oder einem Textknoten sitzen; die Messung
 * unterscheidet das bewusst nicht (die Knotenart gehoert nicht ins Inventar). Fuer eine Linie ist
 * die Aussage dagegen eindeutig.
 */
function scopeDecktEigenschaft(eintrag, eigenschaft) {
  if (eigenschaft === 'strokes') {
    return eintrag.scopes.indexOf('STROKE_COLOR') !== -1;
  }
  return eintrag.scopes.some(function (scope) {
    return scope === 'FRAME_FILL' || scope === 'SHAPE_FILL' || scope === 'TEXT_FILL';
  });
}

/** Der Abbruchcode eines einzelnen Vorkommens, oder null, wenn es erklaert ist.
 *
 * "Erklaert" heisst: entweder bereits an eine Variable des Registers gebunden ODER mit einem
 * Hexwert aus dem Register, den der Scope dieser Variable auch decken kann. Diese Formulierung
 * ist fortschrittsunabhaengig - sie gilt im unberuehrten Zustand ebenso wie nach einem Teillauf
 * und blockiert die Wiederaufnahme nicht.
 */
function abbruchcodeFuer(vorkommen, registerNamen, nachHex) {
  if (vorkommen.art === 'MIXED') {
    return 'gemischte-fuellung';
  }
  if (vorkommen.art !== 'SOLID') {
    return 'nicht-solid';
  }
  if (vorkommen.stilId) {
    return 'stil-gesetzt';
  }
  if (vorkommen.deckkraft !== 1) {
    return 'deckkraft-abweichend';
  }
  if (vorkommen.variable !== null && vorkommen.variable !== undefined) {
    return registerNamen.has(vorkommen.variable) ? null : 'fremde-variable';
  }
  const eintrag = nachHex.get(vorkommen.hex);
  if (!eintrag) {
    return 'unbekannter-hexwert';
  }
  if (!scopeDecktEigenschaft(eintrag, vorkommen.eigenschaft)) {
    return 'scope-deckt-eigenschaft-nicht';
  }
  return null;
}

/** Die Vorpruefung ueber das ganze gemessene Inventar.
 *
 * Zaehlt bis zum Ende durch, statt beim ersten Fund abzubrechen: Bei einem Abbruch kehrt der Lauf
 * mit dem VOLLEN Inventar zurueck, ohne zu schreiben - korrigiert wird dann am Register, und das
 * kostet keinen Aufruf. Ein Grund traegt einen Code aus einer geschlossenen Liste und die
 * Knoten-ID, die den Knoten exakt adressiert; nie einen Namen, nie einen Ausnahmetext aus dem
 * fremden System.
 */
function pruefeVorkommen(vorkommen, register) {
  const registerNamen = new Set(register.variablen.map(function (eintrag) {
    return eintrag.name;
  }));
  const nachHex = variablenNachHex(register);
  const abbruchgruende = [];
  let erklaert = 0;

  for (const eintrag of vorkommen) {
    const code = abbruchcodeFuer(eintrag, registerNamen, nachHex);
    if (code === null) {
      erklaert += 1;
      continue;
    }
    abbruchgruende.push({
      code: code,
      knotenId: eintrag.knotenId,
      eigenschaft: eintrag.eigenschaft,
      index: eintrag.index
    });
  }

  return {
    ok: abbruchgruende.length === 0,
    gesamt: vorkommen.length,
    erklaert: erklaert,
    abbruchgruende: abbruchgruende
  };
}

/* --- Ablaufteil: alles ab hier braucht die Figma-Plugin-Laufzeit ----------------------------
 *
 * Ein Aufruf macht den ganzen Weg: verorten -> messen -> vorpruefen -> Wiederherstellungspunkt ->
 * Variablen setzen -> binden -> Versionsangabe -> erneut messen -> beides zurueckgeben. Der
 * MCP-Zugang haengt an einem harten Aufrufkontingent (am 2026-09-06 nach drei Aufrufen
 * erschoepft), und ein Aufruf fuehrt beliebig viel JavaScript aus: gezaehlt werden Aufrufe, nicht
 * Arbeit. Kein Aufruf dient allein dem Nachsehen.
 *
 * Alle Operationen sind ZIELZUSTANDS-idempotent: eine Variable wird auf ihren Sollwert gesetzt,
 * gleich ob sie existiert; eine Bindung wird gesetzt, wo sie fehlt. Ein zweiter Lauf ist
 * folgenlos, ein Lauf nach einem Abbruch raeumt den Rest auf.
 */

/* Ein reiner Schau-Lauf braucht keine zweite Datei und keine Aenderung an dieser hier: Die
 * Hauptsession stellt dem Payload `globalThis.NUR_PRUEFEN = true;` voran. Der Schalter wird VOR
 * jeder Schreiboperation ausgewertet - siehe hauptlauf(). */
const SCHAU_LAUF = typeof globalThis.NUR_PRUEFEN !== 'undefined' && globalThis.NUR_PRUEFEN === true;

/* Statt eines Namens aus dem fremden Dokument. Eine Bindung an eine Variable, die das Register
 * nicht kennt, ist ein Abbruchgrund - ihr Name ist dafuer nicht noetig und waere Freitext aus
 * einem fremden System. */
const FREMDE_VARIABLE = 'Fremd/Unbekannt';

/* Geschlossene Fehlercodeliste. Der Ruecklauf traegt nie den Ausnahmetext des fremden Systems. */
const FEHLERCODES = {
  boardNichtGefunden: 'board-nicht-gefunden',
  falscheDatei: 'falsche-datei',
  sammlungNichtGefunden: 'sammlung-nicht-gefunden',
  modusNichtEindeutig: 'modus-nicht-eindeutig',
  variablenwertUnlesbar: 'variablenwert-unlesbar',
  beimLesen: 'fehler-beim-lesen',
  beimSetzen: 'fehler-beim-setzen',
  beimBinden: 'fehler-beim-binden',
  beimVersionZiehen: 'fehler-beim-version-ziehen'
};

function jetztInUtc() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function hexAusFarbe(farbe) {
  if (!farbe || typeof farbe.r !== 'number') {
    return null;
  }
  const kanaele = [farbe.r, farbe.g, farbe.b].map(function (anteil) {
    const stufe = Math.round(anteil * 255);
    return (stufe < 16 ? '0' : '') + stufe.toString(16).toUpperCase();
  });
  return '#' + kanaele.join('');
}

function farbeAusHex(hex) {
  return {
    r: parseInt(hex.slice(1, 3), 16) / 255,
    g: parseInt(hex.slice(3, 5), 16) / 255,
    b: parseInt(hex.slice(5, 7), 16) / 255
  };
}

/* Ein gesetzter Stil wird als Tatsache gemeldet, nie mit seiner Kennung: Eine Stil- oder
 * Bibliothekskennung gehoert zu dem, was ausdruecklich nicht ins Inventar aufzunehmen ist. */
function stilGesetzt(knoten, feld) {
  const wert = knoten[feld];
  if (wert === figma.mixed) {
    return 'gesetzt';
  }
  return typeof wert === 'string' && wert.length > 0 ? 'gesetzt' : '';
}

function bindungVon(paint, namenNachId) {
  if (!paint.boundVariables || !paint.boundVariables.color) {
    return { variable: null, variablenId: null };
  }
  const id = paint.boundVariables.color.id;
  const name = namenNachId.get(id);
  return { variable: name === undefined ? FREMDE_VARIABLE : name, variablenId: id };
}

/* Misst eine Eigenschaft (fills/strokes) eines Knotens.
 *
 * Nicht-Solid-Paints (Verlauf, Bild) und figma.mixed-Fills an Textknoten werden NICHT uebergangen,
 * sondern als eigener Eintrag gemessen - die Vorpruefung sieht sie und meldet sie. Ein
 * uebergangenes Vorkommen waere ein blinder Fleck in einer Zusage, die "418, sonst nichts" lautet.
 */
function messeEigenschaft(knoten, eigenschaft, namenNachId, gemessen) {
  const paints = knoten[eigenschaft];
  if (paints === undefined || paints === null) {
    return;
  }
  const stilId = stilGesetzt(knoten, eigenschaft === 'fills' ? 'fillStyleId' : 'strokeStyleId');
  if (paints === figma.mixed) {
    gemessen.push({
      knotenId: knoten.id,
      eigenschaft: eigenschaft,
      index: 0,
      art: 'MIXED',
      hex: null,
      deckkraft: 1,
      mischmodus: 'NORMAL',
      sichtbar: true,
      stilId: stilId,
      variable: null,
      variablenId: null
    });
    return;
  }
  for (let index = 0; index < paints.length; index += 1) {
    const paint = paints[index];
    const bindung = bindungVon(paint, namenNachId);
    gemessen.push({
      knotenId: knoten.id,
      eigenschaft: eigenschaft,
      index: index,
      art: paint.type,
      hex: paint.type === 'SOLID' ? hexAusFarbe(paint.color) : null,
      deckkraft: paint.opacity === undefined ? 1 : paint.opacity,
      mischmodus: paint.blendMode === undefined ? 'NORMAL' : paint.blendMode,
      sichtbar: paint.visible === undefined ? true : paint.visible,
      stilId: stilId,
      variable: bindung.variable,
      variablenId: bindung.variablenId
    });
  }
}

function messeBoard(board, namenNachId, knotenNachId, fehler) {
  const knoten = [board].concat(board.findAll(function () {
    return true;
  }));
  const gemessen = [];
  for (const einzelner of knoten) {
    knotenNachId.set(einzelner.id, einzelner);
    try {
      messeEigenschaft(einzelner, 'fills', namenNachId, gemessen);
      messeEigenschaft(einzelner, 'strokes', namenNachId, gemessen);
    } catch (ausnahme) {
      fehler.push({ code: FEHLERCODES.beimLesen, knotenId: einzelner.id });
    }
  }
  return { knotenGesamt: knoten.length, gemessen: gemessen };
}

async function messeVariablen(sammlung, modusId, fehler) {
  const eintraege = [];
  for (const id of sammlung.variableIds) {
    const variable = await figma.variables.getVariableByIdAsync(id);
    if (!variable || variable.resolvedType !== 'COLOR') {
      continue;
    }
    const hex = hexAusFarbe(variable.valuesByMode[modusId]);
    if (hex === null) {
      fehler.push({ code: FEHLERCODES.variablenwertUnlesbar, variablenId: variable.id });
    }
    eintraege.push({
      id: variable.id,
      name: variable.name,
      wert: hex,
      scopes: variable.scopes.slice(),
      beschreibung: variable.description
    });
  }
  eintraege.sort(function (links, rechts) {
    return links.name < rechts.name ? -1 : links.name > rechts.name ? 1 : 0;
  });
  return eintraege;
}

/* Aus den gemessenen Rohdaten das Inventar in genau der Form, die scripts/tests/
 * test_figma_farbregister.py als geschlossenes Schema prueft - kein Feld mehr, keines weniger.
 * Knoten-/Ebenennamen, Textinhalte, Kommentare, Stil- und Bibliothekskennungen kommen hier
 * ueberhaupt nicht vor: Die Injektionsflaeche ist damit nicht bewacht, sondern strukturell nicht
 * vorhanden. Die Knoten-ID adressiert den Knoten trotzdem exakt (?node-id=). */
function alsInventar(gemessen, variablen, knotenGesamt, boardVersion, mitBindung) {
  const farbvorkommen = gemessen.filter(function (eintrag) {
    return eintrag.art === 'SOLID' && !eintrag.stilId && eintrag.hex !== null;
  });
  farbvorkommen.sort(function (links, rechts) {
    const linksId = links.knotenId.split(':').map(Number);
    const rechtsId = rechts.knotenId.split(':').map(Number);
    if (linksId[0] !== rechtsId[0]) return linksId[0] - rechtsId[0];
    if (linksId[1] !== rechtsId[1]) return linksId[1] - rechtsId[1];
    if (links.eigenschaft !== rechts.eigenschaft) {
      return links.eigenschaft < rechts.eigenschaft ? -1 : 1;
    }
    return links.index - rechts.index;
  });
  const vorkommen = farbvorkommen.map(function (eintrag) {
    const zeile = {
      knotenId: eintrag.knotenId,
      eigenschaft: eintrag.eigenschaft,
      index: eintrag.index,
      hex: eintrag.hex,
      deckkraft: eintrag.deckkraft,
      mischmodus: eintrag.mischmodus,
      sichtbar: eintrag.sichtbar
    };
    if (mitBindung) {
      zeile.variable = eintrag.variable;
      zeile.variablenId = eintrag.variablenId;
    }
    return zeile;
  });
  return {
    kopf: {
      gemessenAm: jetztInUtc(),
      boardKnotenId: REGISTER.boardKnotenId,
      boardVersion: boardVersion,
      anzahlKnoten: knotenGesamt,
      anzahlVorkommen: vorkommen.length,
      anzahlFills: vorkommen.filter(function (zeile) {
        return zeile.eigenschaft === 'fills';
      }).length,
      anzahlStrokes: vorkommen.filter(function (zeile) {
        return zeile.eigenschaft === 'strokes';
      }).length,
      anzahlVariablen: variablen.length
    },
    variablen: variablen,
    vorkommen: vorkommen
  };
}

function uebersprungeneAus(gemessen) {
  return gemessen
    .filter(function (eintrag) {
      return eintrag.art !== 'SOLID' || eintrag.stilId || eintrag.hex === null;
    })
    .map(function (eintrag) {
      return {
        code: eintrag.art !== 'SOLID' ? 'nicht-solid' : 'stil-gesetzt',
        knotenId: eintrag.knotenId,
        eigenschaft: eintrag.eigenschaft,
        index: eintrag.index
      };
    });
}

/* M5 - der Wiederherstellungspunkt ist die ERSTE Schreiboperation nach bestandener Vorpruefung.
 * Er kostet keinen zusaetzlichen MCP-Aufruf und macht jeden Fehllauf mit einem Klick ruecknehmbar.
 * Die eine bewusste Ausnahme von "aendert nichts vor bestandener Vorpruefung": sie liegt danach,
 * und ein Checkpoint ist nicht destruktiv. */
async function setzeWiederherstellungspunkt() {
  await figma.saveVersionHistoryAsync(
    'Vor der Farbvariablen-Umstellung (' + REGISTER.versionVorher + ' -> '
      + REGISTER.versionNachher + ')'
  );
}

async function setzeVariablenAufSoll(sammlung, modusId, fehler) {
  const vorhandene = new Map();
  for (const id of sammlung.variableIds) {
    const variable = await figma.variables.getVariableByIdAsync(id);
    if (variable) {
      vorhandene.set(variable.name, variable);
    }
  }
  const nachName = new Map();
  for (const soll of REGISTER.variablen) {
    try {
      let variable = vorhandene.get(soll.name);
      if (!variable) {
        variable = figma.variables.createVariable(soll.name, sammlung, 'COLOR');
      }
      variable.setValueForMode(modusId, farbeAusHex(soll.wert));
      variable.scopes = soll.scopes.slice();
      variable.description = soll.beschreibung;
      nachName.set(soll.name, variable);
    } catch (ausnahme) {
      fehler.push({ code: FEHLERCODES.beimSetzen, variablenName: soll.name });
    }
  }
  return nachName;
}

/* Bindet je Knoten und Eigenschaft in EINEM Zug auf einer Kopie des Paint-Arrays. `opacity`,
 * `blendMode` und `visible` werden dabei nicht angefasst - deshalb ist die Zusage fuer die 370
 * unveraenderten Vorkommen eine gepruefte und keine gehoffte Aussage. Jede Knotenoperation liegt
 * in try/catch: Ein einzelner gesperrter Knoten darf den Lauf nicht abbrechen. */
function bindeAlle(gemessen, knotenNachId, nachHex, variablenNachName, fehler) {
  const gruppen = new Map();
  for (const eintrag of gemessen) {
    const schluessel = eintrag.knotenId + '|' + eintrag.eigenschaft;
    if (!gruppen.has(schluessel)) {
      gruppen.set(schluessel, []);
    }
    gruppen.get(schluessel).push(eintrag);
  }

  let gebunden = 0;
  for (const eintraege of gruppen.values()) {
    const knoten = knotenNachId.get(eintraege[0].knotenId);
    const eigenschaft = eintraege[0].eigenschaft;
    try {
      const paints = knoten[eigenschaft];
      if (paints === figma.mixed) {
        continue;
      }
      const kopie = paints.map(function (paint) {
        return Object.assign({}, paint);
      });
      let geaendert = false;
      for (const eintrag of eintraege) {
        if (eintrag.variable !== null || eintrag.art !== 'SOLID' || eintrag.hex === null) {
          continue;
        }
        const soll = nachHex.get(eintrag.hex);
        const variable = variablenNachName.get(soll.name);
        kopie[eintrag.index] = figma.variables.setBoundVariableForPaint(
          kopie[eintrag.index], 'color', variable
        );
        geaendert = true;
        gebunden += 1;
      }
      if (geaendert) {
        knoten[eigenschaft] = kopie;
      }
    } catch (ausnahme) {
      fehler.push({
        code: FEHLERCODES.beimBinden,
        knotenId: eintraege[0].knotenId,
        eigenschaft: eigenschaft
      });
    }
  }
  return gebunden;
}

async function ladeSchriften(knoten) {
  if (knoten.fontName === figma.mixed) {
    for (const abschnitt of knoten.getStyledTextSegments(['fontName'])) {
      await figma.loadFontAsync(abschnitt.fontName);
    }
    return;
  }
  await figma.loadFontAsync(knoten.fontName);
}

/* Idempotent: Steht die neue Versionsangabe schon da, findet die Suche nichts und es passiert
 * nichts. Falle: loadFontAsync muss dem Setzen von characters vorausgehen. */
async function zieheVersionHoch(board, fehler) {
  const treffer = board.findAll(function (knoten) {
    return knoten.type === 'TEXT'
      && typeof knoten.characters === 'string'
      && knoten.characters.indexOf(REGISTER.versionVorher) !== -1;
  });
  let geaendert = 0;
  for (const knoten of treffer) {
    try {
      await ladeSchriften(knoten);
      knoten.characters = knoten.characters
        .split(REGISTER.versionVorher)
        .join(REGISTER.versionNachher);
      geaendert += 1;
    } catch (ausnahme) {
      fehler.push({ code: FEHLERCODES.beimVersionZiehen, knotenId: knoten.id });
    }
  }
  return geaendert;
}

function abbruch(phase, code, zusatz) {
  return Object.assign(
    { ok: false, fertig: false, phase: phase, code: code, vorher: null, nachher: null,
      uebersprungen: [], fehler: [] },
    zusatz || {}
  );
}

async function hauptlauf() {
  const fehler = [];

  /* 1. Selbstverortung (M1). Trifft eines nicht zu: Rueckkehr ohne einen einzigen Schreibaufruf.
   * Gibt die Sandbox figma.fileKey nicht her, ist das kein Grund, den Rest wegzulassen - es ist
   * nur eine Pruefung weniger. */
  const board = await figma.getNodeByIdAsync(REGISTER.boardKnotenId);
  if (!board || board.name !== REGISTER.boardName) {
    return abbruch('selbstverortung', FEHLERCODES.boardNichtGefunden);
  }
  if (typeof figma.fileKey === 'string' && figma.fileKey !== REGISTER.fileKey) {
    return abbruch('selbstverortung', FEHLERCODES.falscheDatei);
  }
  const sammlungen = await figma.variables.getLocalVariableCollectionsAsync();
  const sammlung = sammlungen.filter(function (eine) {
    return eine.name === REGISTER.collection;
  })[0];
  if (!sammlung) {
    return abbruch('selbstverortung', FEHLERCODES.sammlungNichtGefunden);
  }
  if (sammlung.modes.length !== 1 || sammlung.modes[0].name !== REGISTER.modus) {
    return abbruch('selbstverortung', FEHLERCODES.modusNichtEindeutig);
  }
  const modusId = sammlung.modes[0].modeId;

  /* 2. Inventar messen. */
  const variablenVorher = await messeVariablen(sammlung, modusId, fehler);
  const namenNachId = new Map(variablenVorher.map(function (eintrag) {
    return [eintrag.id, eintrag.name];
  }));
  const knotenNachId = new Map();
  const messung = messeBoard(board, namenNachId, knotenNachId, fehler);
  const vorher = alsInventar(
    messung.gemessen, variablenVorher, messung.knotenGesamt, REGISTER.versionVorher, false
  );
  const uebersprungen = uebersprungeneAus(messung.gemessen);

  /* 3. Vorpruefung, Abbruch VOR jeder Aenderung. */
  const pruefung = pruefeVorkommen(messung.gemessen, REGISTER);
  if (!pruefung.ok) {
    return {
      ok: false,
      fertig: false,
      phase: 'vorpruefung',
      vorher: vorher,
      nachher: null,
      uebersprungen: uebersprungen,
      abbruchgruende: pruefung.abbruchgruende,
      fehler: fehler
    };
  }
  if (SCHAU_LAUF) {
    return {
      ok: true,
      fertig: false,
      phase: 'schau-lauf',
      vorher: vorher,
      nachher: null,
      uebersprungen: uebersprungen,
      abbruchgruende: [],
      fehler: fehler
    };
  }

  /* 4. bis 7. Ab hier wird geschrieben. */
  await setzeWiederherstellungspunkt();
  const variablenNachName = await setzeVariablenAufSoll(sammlung, modusId, fehler);
  const nachHex = variablenNachHex(REGISTER);
  const gebunden = bindeAlle(messung.gemessen, knotenNachId, nachHex, variablenNachName, fehler);
  const versionsknoten = await zieheVersionHoch(board, fehler);

  /* 8. Erneut messen und beides zurueckgeben. Die zweite Messung ist die Grenze der Zusage: Ein
   * Selbstbericht bleibt ein Selbstbericht, das gemessene Nach-Inventar ist der Nachweis. */
  const variablenNachher = await messeVariablen(sammlung, modusId, fehler);
  const namenNachIdNachher = new Map(variablenNachher.map(function (eintrag) {
    return [eintrag.id, eintrag.name];
  }));
  const knotenNachIdNachher = new Map();
  const messungNachher = messeBoard(board, namenNachIdNachher, knotenNachIdNachher, fehler);
  const nachher = alsInventar(
    messungNachher.gemessen,
    variablenNachher,
    messungNachher.knotenGesamt,
    REGISTER.versionNachher,
    true
  );

  return {
    ok: true,
    fertig: true,
    phase: 'abgeschlossen',
    vorher: vorher,
    nachher: nachher,
    uebersprungen: uebersprungen.concat(uebersprungeneAus(messungNachher.gemessen)),
    abbruchgruende: [],
    fehler: fehler,
    gebunden: gebunden,
    versionsknoten: versionsknoten
  };
}

/* --- Einstieg ------------------------------------------------------------------------------
 *
 * In Figma ist `figma` definiert und der Hauptlauf startet; sein Ergebnis ist der Ruecklauf. Unter
 * node ist `figma` undefiniert, dann landen die reinen Teile in globalThis.__PRUEFTEILE, damit
 * die Pruefung sie aufrufen kann. Der ausgefuehrte Pfad ist davon unberuehrt.
 */
typeof figma === 'undefined'
  ? (globalThis.__PRUEFTEILE = { pruefeVorkommen: pruefeVorkommen, REGISTER: REGISTER })
  : hauptlauf();
