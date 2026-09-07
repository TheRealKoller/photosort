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

/* --- Einstieg ------------------------------------------------------------------------------
 *
 * In Figma ist `figma` definiert und der Hauptlauf startet. Unter node ist es das nicht; dann
 * landen die reinen Teile in globalThis.__PRUEFTEILE, damit die Pruefung sie aufrufen kann.
 */
if (typeof figma === 'undefined') {
  globalThis.__PRUEFTEILE = { pruefeVorkommen: pruefeVorkommen, REGISTER: REGISTER };
}
