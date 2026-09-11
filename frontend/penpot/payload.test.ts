// @vitest-environment node
/*
 * Statische Regeln ueber die HANDGESCHRIEBENE Penpot-Nutzlast (specs/features/0352-penpot-als-
 * alleinige-design-quelle.md, Teststrategie Ebene 2; decisions/0066-penpot-stand-als-erzeugte-
 * idempotente-nutzlast.md Abschnitt 5 Punkt 6).
 *
 * WARUM DIESE EBENE EXISTIERT: `execute_code` fuehrt den Text der Aufbauskripte im Plugin-Kontext
 * einer ANGEMELDETEN Penpot-Sitzung aus, ohne Sandbox. CI kann die Skripte nicht ausfuehren - das
 * Review ist das einzige Gate zwischen einer Zeile im Repository und ihrer Ausfuehrung. Was
 * statisch pruefbar ist, wird deshalb hier geprueft.
 *
 * SUCHRAUM sind die sechs handgeschriebenen Dateien unter `design/penpot/`. Ausdruecklich NICHT
 * `tokens.json`/`icons.json`: sie sind erzeugt, sie MUESSEN Werte tragen, und genau deshalb sind
 * sie die Gegenprobe. `README.md` ist Prosa und bleibt aussen vor.
 *
 * `views.json` IST KEINE NUTZLAST (sie wird nie ausgefuehrt und an kein Skript uebergeben), tritt
 * dieser Liste aber SELBST bei statt einer daneben gestellten zweiten Liste: `NUTZLAST_DATEIEN`
 * speist beide Zusicherungsbloecke - Wertfreiheit UND die abschliessende Verbotsliste. Eine
 * zweite Liste bekaeme genau die Haelfte der Zusicherungen, die sie zu haben scheint.
 *
 * KEIN SELBSTAUSSCHLUSS NOETIG: Diese Datei liegt unter `frontend/penpot/` und damit ausserhalb
 * des eigenen Suchraums - der vorsorglich mitkopierte Selbstausschluss anderer Waechtertests
 * waere hier eine tote Zeile.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { parseAst } from 'vite'
import { describe, expect, it } from 'vitest'

const DESIGN_DIR = fileURLToPath(new URL('../../design/penpot/', import.meta.url))
const FRONTEND_DIR = fileURLToPath(new URL('../', import.meta.url))

/** Die sechs handgeschriebenen Dateien - NAMENTLICH behauptet, nicht "mindestens sechs Dateien
 * im Verzeichnis". Eine Verzeichnisaufzaehlung waere von einem kaputten Glob nicht zu
 * unterscheiden. */
const NUTZLAST_DATEIEN = [
  'seed-tokens.js',
  'seed-icons.js',
  'seed-components.js',
  'verify.js',
  'components.json',
  'views.json',
] as const

/** Die erzeugten Datendateien. Sie sind der POSITIVKORPUS der Gegenprobe: was in ihnen steht, muss
 * ein Erkenner finden, sonst prueft er nichts. */
const ERZEUGTE_DATEIEN = ['tokens.json', 'icons.json'] as const

// ---------------------------------------------------------------------------------------------
// Vorbehandlung - zeilentreu, beide Schritte mit eigenem Selbsttest
// ---------------------------------------------------------------------------------------------

/**
 * Streicht Kommentare und ersetzt sie durch Leerzeichen bzw. erhaltene Zeilenumbrueche. Ein Wert
 * in einem Kommentar erreicht Penpot nicht; die ZEILENZAHL muss dabei erhalten bleiben, sonst
 * zeigen alle Meldungen nach einem Blockkommentar auf die falsche Zeile - und eine
 * fundstellengenaue Freigabeliste waere damit wertlos.
 *
 * Ein Zeichenkettenscanner, kein Muster: `//` in einer Zeichenkette ist kein Kommentarbeginn.
 * Regulaere Ausdruecke als Literal werden bewusst NICHT unterstuetzt - die Nutzlast enthaelt
 * keine, und ein halbgarer Regex-Erkenner waere gefaehrlicher als seine Abwesenheit.
 */
export function streicheKommentare(text: string): string {
  let ergebnis = ''
  let i = 0
  while (i < text.length) {
    const zeichen = text[i]
    const naechstes = text[i + 1]
    if (zeichen === '/' && naechstes === '/') {
      while (i < text.length && text[i] !== '\n') {
        ergebnis += ' '
        i += 1
      }
      continue
    }
    if (zeichen === '/' && naechstes === '*') {
      while (i < text.length && !(text[i] === '*' && text[i + 1] === '/')) {
        ergebnis += text[i] === '\n' ? '\n' : ' '
        i += 1
      }
      ergebnis += '  '
      i += 2
      continue
    }
    if (zeichen === "'" || zeichen === '"' || zeichen === '`') {
      const anfuehrung = zeichen
      ergebnis += zeichen
      i += 1
      while (i < text.length && text[i] !== anfuehrung) {
        if (text[i] === '\\') {
          ergebnis += text[i] + (text[i + 1] ?? '')
          i += 2
          continue
        }
        ergebnis += text[i]
        i += 1
      }
      ergebnis += text[i] ?? ''
      i += 1
      continue
    }
    ergebnis += zeichen
    i += 1
  }
  return ergebnis
}

/** Das geschlossene Gruppenvokabular der Tokennamen. Eine neue Gruppe wird dadurch bewusst
 * eingetragen, statt als Tippfehler durchzulaufen. */
const TOKEN_GRUPPEN = ['color', 'radius', 'space', 'font-family', 'text'] as const

const TOKENNAME_MUSTER = new RegExp(`\\b(?:${TOKEN_GRUPPEN.join('|')})\\.[a-z0-9-]+`, 'g')

/**
 * Maskiert Tokennamen-Literale zeichen- und zeilentreu. OHNE DIESEN SCHRITT IST DIE REGEL EINE
 * FEHLALARM-MASCHINE: `space.3`, `space.16` und `text.2xl` schluegen als blanke Zahlen an,
 * und zwar ab dem ersten Lauf und in jeder Datei der Nutzlast.
 */
export function maskiereTokennamen(text: string): string {
  return text.replace(TOKENNAME_MUSTER, (treffer) => '·'.repeat(treffer.length))
}

function vorbehandeln(text: string): string {
  return maskiereTokennamen(streicheKommentare(text))
}

interface Datei {
  datei: string
  roh: string
  inhalt: string
}

function lies(verzeichnis: string, namen: readonly string[]): Datei[] {
  return namen.map((datei) => {
    const roh = readFileSync(`${verzeichnis}${datei}`, 'utf8')
    return { datei, roh, inhalt: vorbehandeln(roh) }
  })
}

const nutzlast = lies(DESIGN_DIR, NUTZLAST_DATEIEN)
const erzeugt = lies(DESIGN_DIR, ERZEUGTE_DATEIEN)

function dateiVon(name: string): Datei {
  const datei = nutzlast.find((kandidat) => kandidat.datei === name)
  if (datei === undefined) {
    throw new Error(`Nutzlastdatei ${name} fehlt.`)
  }
  return datei
}

// ---------------------------------------------------------------------------------------------
// Vier Musterfamilien
// ---------------------------------------------------------------------------------------------

interface Fund {
  datei: string
  zeile: number
  treffer: string
  text: string
}

/** Hex 3-8-stellig. Eine auf `{6}` verengte Suche waere genau das Loch, gegen das dieser Test
 * antritt: `#fff` und `#0b0c10ff` sind ebenso woertliche Farbwerte. */
const MUSTER_HEX = /#[0-9a-fA-F]{3,8}\b/g

/** Farbfunktionen. Wortgrenze UND oeffnende Klammer, sonst trifft `lab` in `label`. */
const MUSTER_FARBFUNKTION = /\b(?:color-mix|rgba|rgb|hsla|hsl|oklch|oklab|lch|lab)\s*\(/g

/** Laenge mit Einheit. */
const MUSTER_LAENGE = /(?<![\w.-])\d+(?:\.\d+)?\s*(?:px|rem|em|pt|vh|vw|%)(?![\w-])/g

/** Blanke Zahl. Die Freigabe erfolgt nicht hier, sondern fundstellengenau weiter unten. */
const MUSTER_BLANKE_ZAHL = /(?<![\w.$-])-?\d+(?:\.\d+)?(?![\w.-])/g

/**
 * FUENFTE FAMILIE, ausschliesslich fuer `views.json`: nach der Maskierung der Tokennamen bleibt
 * dort KEINE EINZIGE ZIFFER. Die Datei traegt per Bauart keine Zahl - kein Mass, keine Koordinate,
 * keine Fotoanzahl, kein Datumsbeispiel, kein Fortschrittswert.
 *
 * WARUM DIE VIER FAMILIEN HIER NICHT REICHEN (beide Luecken sind gemessen, nicht vermutet):
 * `MUSTER_BLANKE_ZAHL` endet auf `(?![\w.-])` und trifft `"360x740"` am nachfolgenden `x` NICHT;
 * `MUSTER_HEX` verlangt ein `#` und laesst `"0b0c10"` durch. Genau in diesen Schreibweisen rutscht
 * eine Koordinate oder ein Farbwert in eine JSON-Datei.
 *
 * BENANNTE RESTLUECKE: ein rein buchstabiger Hexwert (`"ffffff"`) bleibt unerkannt. Ohne `#` ist
 * er kein Wert, den Penpot annaehme, und eine Regel gegen sechs Buchstaben waere eine
 * Fehlalarm-Maschine.
 */
const MUSTER_ZIFFER = /[0-9]/g

/** Blanke Zahlen, die ueberall unverdaechtig sind: Zaehlanfang, Erstes, Zweites, "nicht
 * gefunden". Sie tragen keine Gestaltungsaussage. */
const UNVERDAECHTIGE_ZAHLEN = new Set(['0', '1', '2', '-1'])

/** Sucht ein Muster in bereits vorbehandelten Dateien. Die zu durchsuchenden Dateien sind ein
 * PARAMETER, damit die Mikrotests gegen literal geschriebene Eingaben pruefen koennen - kein
 * Dateisystem, keine Fixtures. */
export function suche(dateien: readonly Datei[], muster: RegExp): Fund[] {
  const funde: Fund[] = []
  for (const datei of dateien) {
    datei.inhalt.split('\n').forEach((text, index) => {
      for (const treffer of text.matchAll(new RegExp(muster.source, muster.flags))) {
        funde.push({ datei: datei.datei, zeile: index + 1, treffer: treffer[0], text })
      }
    })
  }
  return funde
}

function alsDateien(inhalt: string, datei = 'probe.js'): Datei[] {
  return [{ datei, roh: inhalt, inhalt: vorbehandeln(inhalt) }]
}

function meldung(funde: Fund[]): string {
  return funde
    .map((fund) => `${fund.datei}:${fund.zeile}: ${fund.treffer} | ${fund.text.trim()}`)
    .join('\n')
}

// ---------------------------------------------------------------------------------------------
// Selbsttests der Vorbehandlung
// ---------------------------------------------------------------------------------------------

describe('Vorbehandlung: Kommentarstreichung', () => {
  it('entfernt einen Zeilenkommentar', () => {
    expect(streicheKommentare('const a = 1 // #ffffff').includes('#ffffff')).toBe(false)
  })

  it('entfernt einen Blockkommentar', () => {
    expect(streicheKommentare('/* #ffffff */ const a = 1').includes('#ffffff')).toBe(false)
  })

  it('erhaelt die Zeilenzahl ueber einen Blockkommentar hinweg', () => {
    const text = 'a\n/* eins\nzwei\ndrei */\nb'
    expect(streicheKommentare(text).split('\n')).toHaveLength(text.split('\n').length)
    expect(streicheKommentare(text).split('\n')[4]).toBe('b')
  })

  it('haelt einen Schraegstrich in einer Zeichenkette nicht fuer einen Kommentar', () => {
    expect(streicheKommentare("const a = 'x // y'")).toContain('x // y')
  })

  it('laesst Code ausserhalb von Kommentaren unangetastet', () => {
    expect(streicheKommentare('const a = 1')).toBe('const a = 1')
  })
})

describe('Vorbehandlung: Maskierung der Tokennamen', () => {
  it('maskiert einen Tokennamen mit Zahl im Blatt', () => {
    expect(maskiereTokennamen('"space.3"')).not.toContain('3')
    expect(maskiereTokennamen('"text.2xl"')).not.toContain('2')
  })

  it('maskiert zeichentreu und damit zeilentreu', () => {
    const text = 'a: "space.16",\nb: 1'
    const maskiert = maskiereTokennamen(text)
    expect(maskiert).toHaveLength(text.length)
    expect(maskiert.split('\n')).toHaveLength(2)
  })

  it('maskiert keinen fremden Punktausdruck', () => {
    expect(maskiereTokennamen('penpot.library.local')).toBe('penpot.library.local')
  })

  it('ist der Grund, warum space.3 kein Fehlalarm ist', () => {
    expect(suche(alsDateien('const a = "space.3"'), MUSTER_BLANKE_ZAHL)).toEqual([])
    // Gegenprobe: dieselbe Zahl OHNE Tokennamen schlaegt sehr wohl an.
    expect(suche(alsDateien('const a = 3'), MUSTER_BLANKE_ZAHL)).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------------------------
// Mikrotests der vier Musterfamilien: Muss-Treffer UND Muss-Nicht-Treffer
// ---------------------------------------------------------------------------------------------

describe('Musterfamilien: tabellengetriebene Erkenner-Selbsttests', () => {
  const tabelle: { name: string; muster: RegExp; trifft: string[]; trifftNicht: string[] }[] = [
    {
      name: 'Hex',
      muster: MUSTER_HEX,
      trifft: ['const a = "#fff"', 'const a = "#0B0C10"', 'const a = "#0b0c10ff"'],
      trifftNicht: ['const a = "kein hex"', 'const a = "#zzzzzz"'],
    },
    {
      name: 'Farbfunktion',
      muster: MUSTER_FARBFUNKTION,
      trifft: [
        'const a = "rgb(1 2 3)"',
        'const a = "hsl(0 0% 0%)"',
        'const a = "lab(50% 0 0)"',
        'const a = "oklch(0.5 0 0)"',
        'const a = "color-mix(in srgb, a, b)"',
      ],
      // `lab` in `label` ist der Grund fuer die Wortgrenze, `rgb` ohne Klammer der fuer das `\(`.
      trifftNicht: ['const label = 1', 'const a = "rgb ohne klammer"', 'const collab = fn()'],
    },
    {
      name: 'Laenge mit Einheit',
      muster: MUSTER_LAENGE,
      trifft: ['const a = "12px"', 'const a = "1.5rem"', 'const a = "100%"'],
      trifftNicht: ['const a = "expression"', 'const a = 12'],
    },
    {
      name: 'Blanke Zahl',
      muster: MUSTER_BLANKE_ZAHL,
      trifft: ['const a = 12', 'const a = -3', 'const a = 1.25'],
      trifftNicht: ['const a = "text"', 'const a = b12', 'const a = obj.x1'],
    },
  ]

  for (const zeile of tabelle) {
    it(`erkennt ${zeile.name}`, () => {
      for (const eingabe of zeile.trifft) {
        expect(suche(alsDateien(eingabe), zeile.muster), eingabe).not.toEqual([])
      }
    })

    it(`meldet bei ${zeile.name} nicht das Aehnliche`, () => {
      for (const eingabe of zeile.trifftNicht) {
        expect(suche(alsDateien(eingabe), zeile.muster), eingabe).toEqual([])
      }
    })
  }
})

// ---------------------------------------------------------------------------------------------
// Suchraum
// ---------------------------------------------------------------------------------------------

describe('Suchraum der Abwesenheits-Zusicherung', () => {
  it('umfasst genau die sechs namentlich behaupteten Dateien', () => {
    expect(nutzlast.map((datei) => datei.datei)).toEqual([...NUTZLAST_DATEIEN])
  })

  /* Je Datei eine Mindest-Zeichenzahl. Am Bestand gemessen (2026-09-08) und nach unten gerundet -
     eine leergeraeumte oder halb geschriebene Nutzlast bestuende sonst jede Abwesenheitszusage. */
  const MINDESTZEICHEN: Record<string, number> = {
    'seed-tokens.js': 2000,
    'seed-icons.js': 2500,
    'seed-components.js': 5000,
    'verify.js': 4000,
    'components.json': 10000,
    'views.json': 10000,
  }

  /* Mindestzahl gescannter Zeilen NACH der Vorbehandlung. Ohne sie ist ein kaputter
     Vorbehandlungsschritt (der alles wegstreicht) von einem sauberen Bestand nicht zu
     unterscheiden: beide melden null Funde. Mit `views.json` im Suchraum neu gemessen (1237),
     eingefroren auf 1100. */
  const MINDESTZEILEN = 1100

  it('hat je Datei ueberhaupt Inhalt', () => {
    for (const datei of nutzlast) {
      expect(datei.roh.length, datei.datei).toBeGreaterThanOrEqual(MINDESTZEICHEN[datei.datei])
    }
  })

  it('scannt nach der Vorbehandlung noch genug Zeilen', () => {
    const zeilen = nutzlast.reduce(
      (summe, datei) =>
        summe + datei.inhalt.split('\n').filter((zeile) => zeile.trim().length > 0).length,
      0,
    )
    expect(zeilen).toBeGreaterThanOrEqual(MINDESTZEILEN)
  })
})

// ---------------------------------------------------------------------------------------------
// Die tragende Zusicherung: kein woertlicher Farb-/Groessenwert
// ---------------------------------------------------------------------------------------------

/*
 * FUNDSTELLENGENAUE FREIGABELISTE, bewusst NICHT dateiweise: `verify.js` braucht legitim seine
 * Kardinalitaeten, und eine dateiweise Freigabe waere ein stiller Selbstausschalter - ab dann
 * duerfte dort jeder Farbwert stehen. Eine Freigabe nennt Datei, Zeile, Wert und einen AUSSCHNITT
 * der Zeile; verschiebt sich die Fundstelle, faellt die Freigabe.
 *
 * ⚠ SIE IST AN ZEILENNUMMERN GEBUNDEN: Jede in `verify.js` OBERHALB der Kardinalitaeten eingefuegte
 * Zeile verschiebt alle Eintraege. Das ist kein Nebenschaden, sondern der eingebaute Waechter -
 * neue Konstanten gehoeren deshalb UNTER die bestehenden.
 *
 * `views.json` bekommt hier keine einzige Freigabe: die Datei traegt per Bauart keine Zahl.
 */
const FREIGABEN: { datei: string; zeile: number; wert: string; ausschnitt: string }[] = [
  { datei: 'verify.js', zeile: 54, wert: '12', ausschnitt: 'ERWARTETE_SYMBOLE = 12' },
  { datei: 'verify.js', zeile: 55, wert: '12', ausschnitt: 'ERWARTETE_BAUSTEINE = 12' },
  { datei: 'verify.js', zeile: 56, wert: '13', ausschnitt: 'ERWARTETE_KATEGORIEN = 13' },
  { datei: 'verify.js', zeile: 57, wert: '64', ausschnitt: 'ERWARTETE_FARBEN = 64' },
  { datei: 'verify.js', zeile: 58, wert: '6', ausschnitt: 'ERWARTETE_ANSICHTEN = 6' },
  { datei: 'verify.js', zeile: 59, wert: '24', ausschnitt: 'ERWARTETE_ANSICHTSBRETTER = 24' },
  { datei: 'verify.js', zeile: 60, wert: '4', ausschnitt: 'ERWARTETE_ANSICHTSBEHAELTER = 4' },
]

describe('Kein woertlicher Farb-/Groessenwert in der handgeschriebenen Nutzlast', () => {
  it('enthaelt keinen Hexwert', () => {
    const funde = suche(nutzlast, MUSTER_HEX)
    expect(meldung(funde)).toBe('')
  })

  /* DIESE FAMILIE HAT KEINE REPO-SEITIGE GEGENPROBE: das Design-System fuehrt ausschliesslich Hex,
     in keiner erzeugten Datei steht je eine Farbfunktion. Sie wird deshalb namentlich benannt und
     traegt oben einen synthetischen Erkenner-Selbsttest - ein Muster ohne moegliche Gegenprobe
     wird nicht heimlich mitgefuehrt. */
  it('enthaelt keine Farbfunktion', () => {
    const funde = suche(nutzlast, MUSTER_FARBFUNKTION)
    expect(meldung(funde)).toBe('')
  })

  it('enthaelt keine Laengenangabe mit Einheit', () => {
    const funde = suche(nutzlast, MUSTER_LAENGE)
    expect(meldung(funde)).toBe('')
  })

  function freigabeFuer(fund: Fund): (typeof FREIGABEN)[number] | undefined {
    return FREIGABEN.find(
      (freigabe) =>
        freigabe.datei === fund.datei &&
        freigabe.zeile === fund.zeile &&
        freigabe.wert === fund.treffer &&
        fund.text.includes(freigabe.ausschnitt),
    )
  }

  const blankeZahlen = suche(nutzlast, MUSTER_BLANKE_ZAHL).filter(
    (fund) => !UNVERDAECHTIGE_ZAHLEN.has(fund.treffer),
  )

  it('enthaelt keine unfreigegebene blanke Zahl', () => {
    const offen = blankeZahlen.filter((fund) => freigabeFuer(fund) === undefined)
    expect(meldung(offen)).toBe('')
  })

  /* Verwaiste Freigaben sind der stille Verfall dieser Liste: eine Zeile, die nichts mehr
     freigibt, ist eine Erlaubnis auf Vorrat. */
  it('fuehrt keine verwaiste Freigabe', () => {
    const verwaist = FREIGABEN.filter(
      (freigabe) => !blankeZahlen.some((fund) => freigabeFuer(fund) === freigabe),
    )
    expect(verwaist).toEqual([])
  })

  /* Ein Ausschnitt, der nur aus dem Suchbegriff besteht, gaebe die Zahl ueberall in der Zeile
     frei und waere damit keine Fundstellenangabe mehr. */
  it('verlangt einen aussagekraeftigen Ausschnitt je Freigabe', () => {
    for (const freigabe of FREIGABEN) {
      expect(freigabe.ausschnitt.length, freigabe.ausschnitt).toBeGreaterThanOrEqual(6)
      expect(
        freigabe.ausschnitt.replace(/[0-9]/g, '').trim().length,
        freigabe.ausschnitt,
      ).toBeGreaterThan(0)
    }
  })
})

// ---------------------------------------------------------------------------------------------
// Gegenprobe an den erzeugten Datendateien
// ---------------------------------------------------------------------------------------------

describe('Gegenprobe: die erzeugten Datendateien schlagen an', () => {
  it('findet Hexwerte in tokens.json', () => {
    expect(suche(erzeugt, MUSTER_HEX).length).toBeGreaterThan(0)
  })

  it('findet Laengenangaben in tokens.json', () => {
    expect(suche(erzeugt, MUSTER_LAENGE).length).toBeGreaterThan(0)
  })

  it('findet blanke Zahlen in den erzeugten Dateien', () => {
    const funde = suche(erzeugt, MUSTER_BLANKE_ZAHL).filter(
      (fund) => !UNVERDAECHTIGE_ZAHLEN.has(fund.treffer),
    )
    expect(funde.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------------------------
// Die Ziffernregel ueber views.json
// ---------------------------------------------------------------------------------------------

describe('Wertfreiheit von views.json, scharf gefasst', () => {
  it('traegt nach der Maskierung der Tokennamen keine einzige Ziffer', () => {
    const funde = suche([dateiVon('views.json')], MUSTER_ZIFFER)
    expect(meldung(funde)).toBe('')
  })

  /* ERSTE SYNTHETISCHE GEGENPROBE: die vier Familien SCHWEIGEN an genau den zwei Schreibweisen,
     wegen derer diese fuenfte Familie existiert. Ohne sie waere die Ziffernregel eine Behauptung
     ueber eine Luecke, die niemand nachgemessen hat. */
  it('zeigt, dass die vier Familien an "360x740" und "0b0c10" schweigen', () => {
    const probe = alsDateien('{ "stelle": "360x740", "grund": "0b0c10" }', 'views.json')
    expect(suche(probe, MUSTER_HEX)).toEqual([])
    expect(suche(probe, MUSTER_FARBFUNKTION)).toEqual([])
    expect(suche(probe, MUSTER_LAENGE)).toEqual([])
    expect(suche(probe, MUSTER_BLANKE_ZAHL)).toEqual([])
  })

  /* ZWEITE SYNTHETISCHE GEGENPROBE: die Ziffernregel schlaegt an derselben Probe an. */
  it('schlaegt an derselben Probe an', () => {
    const probe = alsDateien('{ "stelle": "360x740", "grund": "0b0c10" }', 'views.json')
    expect(suche(probe, MUSTER_ZIFFER).length).toBeGreaterThan(0)
  })

  /* Und sie ist trotzdem kein Fehlalarm auf einen Tokennamen: die Maskierung laeuft vorher. */
  it('haelt einen Tokennamen mit Zahl im Blatt aus', () => {
    expect(suche(alsDateien('{ "grund": "space.3" }', 'views.json'), MUSTER_ZIFFER)).toEqual([])
  })
})

// ---------------------------------------------------------------------------------------------
// Struktur der Nutzlast
// ---------------------------------------------------------------------------------------------

const tokens = JSON.parse(readFileSync(`${DESIGN_DIR}tokens.json`, 'utf8')) as {
  name: string
  type: string
  /** Die sieben Schriftstufen tragen einen VERBUNDWERT (Groesse, Zeilenhoehe, Schnitt,
   * Laufweite); alles andere einen Einzelwert. */
  value: string | Record<string, string>
}[]
const tokennamen = new Set(tokens.map((token) => token.name))

const komponenten = JSON.parse(dateiVon('components.json').roh) as {
  bausteine: {
    schluessel: string
    name: string
    quellen: string[]
    varianten: Record<string, string[]>
    tokens: Record<string, string>
    tokensProAuspraegung?: Record<string, Record<string, Record<string, string>>>
  }[]
}

/**
 * Alle Stellen in `components.json`, die per Bauart einen Tokennamen tragen: die Rollen-Tabelle
 * je Baustein und die je Auspraegung.
 *
 * ERKANNT WIRD UEBER DEN PLATZ, NICHT UEBER DAS MUSTER - und das ist der Kern dieser Zusicherung.
 * Ein Erkenner, der Tokennamen am GRUPPENVOKABULAR erkennt, kann einen Tippfehler IM
 * Gruppennamen prinzipiell nicht finden: `line-height.xs` sieht fuer ihn wie gar kein Tokenname
 * aus und liefe still durch. Genau deshalb liest diese Funktion die Slots und prueft erst danach,
 * ob der Wert die Namensform haelt.
 */
function tokenSlots(): { pfad: string; wert: string }[] {
  const slots: { pfad: string; wert: string }[] = []
  for (const baustein of komponenten.bausteine) {
    for (const [rolle, wert] of Object.entries(baustein.tokens)) {
      slots.push({ pfad: `${baustein.schluessel}.tokens.${rolle}`, wert })
    }
    for (const [achse, auspraegungen] of Object.entries(baustein.tokensProAuspraegung ?? {})) {
      for (const [auspraegung, rollen] of Object.entries(auspraegungen)) {
        for (const [rolle, wert] of Object.entries(rollen)) {
          slots.push({ pfad: `${baustein.schluessel}.${achse}.${auspraegung}.${rolle}`, wert })
        }
      }
    }
  }
  return slots
}

/** Zeichenketten-Literale aus einer Skriptdatei, die wie ein punktierter Bezeichner aussehen.
 * In `seed-components.js` traegt kein legitimes Literal einen Punkt (die Namen kommen alle aus
 * der Datendatei) - jedes punktierte Literal dort MUSS also ein Tokenname sein. */
function punktierteLiteraleAus(quelltext: string): string[] {
  return [...streicheKommentare(quelltext).matchAll(/'([a-z][a-z0-9-]*\.[a-z0-9-]+)'/g)].map(
    (treffer) => treffer[1],
  )
}

describe('Referentielle Integritaet', () => {
  it('nennt in components.json und seed-components.js nur Tokens, die es gibt', () => {
    const genannt = [
      ...tokenSlots().map((slot) => slot.wert),
      ...punktierteLiteraleAus(dateiVon('seed-components.js').roh),
    ]
    expect(genannt.length).toBeGreaterThan(0)
    const unbekannt = [...new Set(genannt)].filter((name) => !tokennamen.has(name))
    expect(unbekannt).toEqual([])
  })

  /* Selbsttest des Erkenners: er findet die Slots ueberhaupt, und zwar in beiden Tabellen. */
  it('findet die Tokenslots in beiden Tabellen', () => {
    const pfade = tokenSlots().map((slot) => slot.pfad)
    expect(pfade.length).toBeGreaterThanOrEqual(50)
    expect(pfade.some((pfad) => pfad === 'button.tokens.radius')).toBe(true)
    expect(pfade.some((pfad) => pfad === 'chip.kategorie.menschen.flaeche')).toBe(true)
  })

  /*
   * DIE GEGENRICHTUNG WIRD NICHT GEPRUEFT: sie zwaenge zum Ausduennen eines bewusst vollstaendigen
   * Tokensatzes. An ihre Stelle tritt eine GRUPPEN-Zusicherung: jede Gruppe, die es in der
   * erzeugten Tokenliste gibt, wird von mindestens einem Baustein verwendet. Die Sollmenge kommt
   * aus `tokens.json` und ist damit erzeugt, nicht getippt - eine neue Gruppe faellt hier auf,
   * statt unbenutzt mitzulaufen.
   */
  it('verwendet jede Tokengruppe in mindestens einem Baustein', () => {
    const vorhanden = new Set(tokens.map((token) => token.name.split('.')[0]))
    const verwendet = new Set(tokenSlots().map((slot) => slot.wert.split('.')[0]))
    expect([...vorhanden].sort()).toEqual(['color', 'font-family', 'radius', 'space', 'text'])
    for (const gruppe of vorhanden) {
      expect(verwendet.has(gruppe), gruppe).toBe(true)
    }
  })

  /* Das Gruppenvokabular ist ERSCHOEPFEND - genau die fuenf Gruppen, die `tokens.json` fuehrt,
     keine auf Vorrat. Eine erlaubte, aber unbenutzte Gruppe waere eine Zusicherung, die nichts
     zusichert. Geprueft wird gegen die SLOTS (siehe oben), damit auch ein Tippfehler im
     Gruppennamen anschlaegt und nicht bloss unsichtbar wird. */
  it('haelt die Namensform an jedem Tokenslot ein', () => {
    const form = new RegExp(`^(?:${TOKEN_GRUPPEN.join('|')})\\.[a-z0-9-]+$`)
    for (const slot of tokenSlots()) {
      expect(form.test(slot.wert), `${slot.pfad}: ${slot.wert}`).toBe(true)
    }
    for (const name of punktierteLiteraleAus(dateiVon('seed-components.js').roh)) {
      expect(form.test(name), name).toBe(true)
    }
  })

  it('erkennt einen Tippfehler im Gruppennamen als solchen', () => {
    // Gegenprobe zur Bauart: der Erkenner haengt am Platz, nicht am Vokabular.
    const form = new RegExp(`^(?:${TOKEN_GRUPPEN.join('|')})\\.[a-z0-9-]+$`)
    expect(form.test('line-height.xs')).toBe(false)
    expect(form.test('text.xs')).toBe(true)
    expect(punktierteLiteraleAus("const a = 'line-height.xs'")).toEqual(['line-height.xs'])
  })
})

describe('Die zwoelf Bausteine', () => {
  /*
   * GESCHLOSSENE NAMENSMENGE, nicht Kardinalitaet: "genau zwoelf" bestuenden auch zwoelf beliebige. Die
   * Menge ist seit der Aufnahme des Platzhalters nicht mehr eingefroren, sondern REGELGEBUNDEN
   * OFFEN - fortgeschrieben wird trotzdem die Namensliste samt REIHENFOLGE, nicht die Anzahl: die
   * Bausteine aus `components/ui/` stehen zusammen, der Kategorie-Chip als einziger aus
   * `components/` am Ende. Ein Anhaengen ans Ende zerrisse diese Ordnung still.
   */
  it('traegt genau die zwoelf maschinellen Schluessel', () => {
    expect(komponenten.bausteine.map((baustein) => baustein.schluessel)).toEqual([
      'button',
      'input',
      'badge',
      'card',
      'alert',
      'checkbox',
      'switch',
      'progress',
      'dialog',
      'skeleton',
      'chip',
      'step-marker',
    ])
  })

  it('traegt die deutschen Anzeigenamen', () => {
    expect(komponenten.bausteine.map((baustein) => baustein.name)).toEqual([
      'Schaltfläche',
      'Eingabefeld',
      'Kennzeichen',
      'Karte',
      'Hinweis',
      'Auswahlkästchen',
      'Schalter',
      'Fortschrittsanzeige',
      'Dialog',
      'Platzhalter',
      'Kategorie-Chip',
      'Schrittmarke',
    ])
  })

  it('nennt je Baustein mindestens eine vorhandene Produktdatei', () => {
    for (const baustein of komponenten.bausteine) {
      expect(baustein.quellen.length, baustein.schluessel).toBeGreaterThan(0)
      for (const quelle of baustein.quellen) {
        expect(() => readFileSync(`${FRONTEND_DIR}${quelle}`, 'utf8'), quelle).not.toThrow()
      }
    }
  })

  /*
   * GLEICHHEIT, NICHT "ENTHAELT" (specs/features/0387-schrittleiste-fortschritt.md): Der
   * Zustandstraeger der Schrittmarke ist seit dieser Spec ueber zwei Dateien verteilt - `group`
   * sitzt am Bedienelement in Stepper.tsx, die `group-*`-Varianten am Marker in StepMarker.tsx.
   * Der Zustandsscanner unten liest ausschliesslich die Dateien aus `quellen`; ein
   * stehengebliebener Alteintrag liesse ihn weiter die falsche Datei lesen und waere STILL GRUEN.
   * Deshalb ist die Zuordnung hier keine Kosmetik, sondern die tragende Angabe.
   */
  it('zeigt die Quelle der Schrittmarke genau auf die Marker-Datei', () => {
    const schrittmarke = komponenten.bausteine.find(
      (baustein) => baustein.schluessel === 'step-marker',
    )
    expect(schrittmarke, 'Baustein step-marker nicht gefunden').toBeDefined()
    expect(schrittmarke!.quellen).toEqual(['src/components/StepMarker.tsx'])
  })

  /* Die Zuordnungstabelle spannt ZWEI Verzeichnisse: zehn der elf liegen unter
     `src/components/ui/`, der Kategorie-Chip als `src/components/CategoryBadge.tsx`. Wer nur `ui/`
     aufzaehlt, verliert den elften still. */
  it('spannt beide Verzeichnisse auf', () => {
    const quellen = komponenten.bausteine.flatMap((baustein) => baustein.quellen)
    expect(quellen).toContain('src/components/CategoryBadge.tsx')
    expect(
      quellen.filter((quelle) => quelle.startsWith('src/components/ui/')).length,
    ).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------------------------
// Die Achsen der Bausteine
// ---------------------------------------------------------------------------------------------

/**
 * Achsen, die bewusst KEINE eigenen Tokens tragen - eingefroren, je mit Grund.
 *
 * Die Liste ist die Ausnahme zur Regel darunter, und sie ist absichtlich unbequem: Wer eine neue
 * tokenlose Achse einfuehrt, muss sie hier eintragen und begruenden. Die Phantom-Achse
 * `badge.zustand` (`normal`/`unbewertet`, ohne einen einzigen Token und ohne Entsprechung im
 * Produkt) haette genau daran auffallen muessen.
 */
const ACHSEN_OHNE_EIGENE_TOKENS: Record<string, string> = {
  'button.groesse':
    'Die drei Groessen unterscheiden sich in Hoehe und Polsterung. Die Werte stehen im Produkt ' +
    'als Utilities (h-8, px-4, px-3, size-8) und sind hier bewusst nicht je Groesse ' +
    'ausgeschrieben - der Baustein traegt sie als Grundmasse.',
  'dialog.zustand':
    'offen/geschlossen ist Verhalten, kein Wert: der geschlossene Dialog zeigt nichts, und es ' +
    'gibt keine Eigenschaft, die sich dabei aendert.',
  'dialog.abbrechen':
    'cancelDisabled schaltet den deaktivierten Zustand der Abbrechen-Schaltflaeche. Den traegt ' +
    'die Schaltflaeche (Baustein `button`, Zustand `disabled`), nicht der Dialog.',
  'card.vorschlag':
    'ohne/mit schaltet das Kennzeichen auf der Kachel um. Dessen Werte traegt der Baustein ' +
    '`badge` (Auspraegungen `*-solid` gegen `*-suggested`); die Karte selbst aendert dabei ' +
    'keine Eigenschaft.',
}

interface AchsenBaustein {
  schluessel: string
  varianten: Record<string, string[]>
  tokensProAuspraegung?: Record<string, Record<string, Record<string, string>>>
}

/** Reine Funktion: Achsen, die weder eigene Tokens tragen noch als Ausnahme gefuehrt sind. */
export function achsenOhneTokens(
  bausteine: AchsenBaustein[],
  ausnahmen: Record<string, string>,
): string[] {
  const befunde: string[] = []
  for (const baustein of bausteine) {
    for (const achse of Object.keys(baustein.varianten)) {
      const eintrag = baustein.tokensProAuspraegung?.[achse]
      const traegtTokens =
        eintrag !== undefined &&
        Object.values(eintrag).some((rollen) => Object.keys(rollen).length > 0)
      const pfad = `${baustein.schluessel}.${achse}`
      if (!traegtTokens && ausnahmen[pfad] === undefined) {
        befunde.push(pfad)
      }
    }
  }
  return befunde
}

describe('Die Achsen der Bausteine', () => {
  /*
   * JEDE ACHSE MUSS UNABHAENGIG VON DEN UEBRIGEN WAEHLBAR SEIN; wo zwei Dinge nicht orthogonal
   * sind, gehoeren sie in EINE Achse. Mechanisch greifbar ist davon die untere Haelfte: Eine
   * Achse, die gar keine Tokens traegt, beschreibt nichts Sichtbares und multipliziert das
   * Kreuzprodukt nur auf. Genau so entstand `badge.zustand` mit `normal`/`unbewertet` - eine
   * Kombination "favorite und zugleich unbewertet" gibt es im Produkt nicht.
   */
  it('fuehrt keine Achse ohne Tokens', () => {
    expect(achsenOhneTokens(komponenten.bausteine, ACHSEN_OHNE_EIGENE_TOKENS)).toEqual([])
  })

  it('erkennt eine Phantom-Achse an einer synthetischen Probe', () => {
    const probe = [
      {
        schluessel: 'probe',
        varianten: { zustand: ['normal', 'unbewertet'], ton: ['a'] },
        tokensProAuspraegung: { ton: { a: { flaeche: 'color.bg' } } },
      },
    ]
    expect(achsenOhneTokens(probe, {})).toEqual(['probe.zustand'])
    // Gegenprobe: die Achse mit Tokens wird nicht gemeldet, und eine gefuehrte Ausnahme schweigt.
    expect(achsenOhneTokens(probe, { 'probe.zustand': 'begruendet' })).toEqual([])
  })

  it('fuehrt keine verwaiste Ausnahme', () => {
    const achsen = komponenten.bausteine.flatMap((baustein) =>
      Object.keys(baustein.varianten).map((achse) => `${baustein.schluessel}.${achse}`),
    )
    for (const pfad of Object.keys(ACHSEN_OHNE_EIGENE_TOKENS)) {
      expect(achsen, pfad).toContain(pfad)
      expect(achsenOhneTokens(komponenten.bausteine, {}), pfad).toContain(pfad)
      expect(ACHSEN_OHNE_EIGENE_TOKENS[pfad].length, pfad).toBeGreaterThan(40)
    }
  })

  /*
   * Beim Zusammenlegen zweier Achsen kollidieren gleichnamige Auspraegungen STILL: `success` hiess
   * beim Hinweis und beim Statuskennzeichen zweierlei, ein unbedachtes Verschmelzen haette den
   * einen Tokensatz vom anderen verdeckt. Die Regel gilt deshalb JE ACHSE - genau dort, wo eine
   * Verschmelzung landet.
   *
   * Bewusst NICHT ueber die Achsen eines Bausteins hinweg: Die Schaltflaeche traegt `default`
   * legitim zweimal (Auspraegung und Groesse), und Penpot schluesselt Varianteneigenschaften
   * ohnehin je Achse. Eine achsenuebergreifende Regel waere hier ein Fehlalarm.
   */
  it('vergibt je Achse jeden Auspraegungsnamen genau einmal', () => {
    for (const baustein of komponenten.bausteine) {
      for (const [achse, werte] of Object.entries(baustein.varianten)) {
        expect(new Set(werte).size, `${baustein.schluessel}.${achse}`).toBe(werte.length)
      }
    }
  })

  /*
   * `/` IST IN PENPOT EIN PFADTRENNER, KEIN NAMENSBESTANDTEIL: `symbol/star` wird beim Anlegen zu
   * `{ name: "star", path: "symbol" }` (gemessen). Wer einen Baustein oder eine Auspraegung mit
   * Schraegstrich benennt, bekommt still einen anderen Namen zurueck, als er gesetzt hat - und
   * jeder Vergleich am Namen geht danach ins Leere.
   */
  it('vergibt keinen Namen mit Schraegstrich', () => {
    for (const baustein of komponenten.bausteine) {
      const namen = [
        baustein.schluessel,
        baustein.name,
        ...Object.keys(baustein.varianten),
        ...Object.values(baustein.varianten).flat(),
      ]
      for (const name of namen) {
        expect(name, `${baustein.schluessel}: ${name}`).not.toContain('/')
      }
    }
  })

  /*
   * Die Zahl der Varianten, die `seed-components.js` aufbaut: das Kreuzprodukt der Achsen je
   * Baustein. Eingefroren, weil eine versehentlich hinzugefuegte Achse sie sprunghaft vervielfacht
   * und das sonst niemandem auffiele. 90 + 5 + 9 + 8 + 7 + 3 + 3 + 2 + 4 + 2 + 13 + 12.
   */
  it('baut genau 158 Varianten auf', () => {
    const gesamt = komponenten.bausteine.reduce(
      (summe, baustein) =>
        summe +
        Object.values(baustein.varianten).reduce((produkt, werte) => produkt * werte.length, 1),
      0,
    )
    expect(gesamt).toBe(158)
  })
})

// ---------------------------------------------------------------------------------------------
// Zustandsabdeckung gegen den Produktcode
// ---------------------------------------------------------------------------------------------

/** Geschlossenes Zustandsvokabular. Breakpoint- und Layout-Varianten (`sm:`, `lg:`,
 * `motion-reduce:`) sind bewusst NICHT enthalten - sonst ist die Regel eine Fehlalarm-Maschine. */
const ZUSTANDSVOKABULAR = [
  'hover',
  'active',
  'focus-visible',
  'disabled',
  'aria-disabled',
  'data-[state=checked]',
  'data-[state=open]',
  'indeterminate',
] as const

/** Findet Zustaende als TAILWIND-VARIANTE (Name gefolgt von `:`), optional mit `group-`/`peer-`
 * davor. `aria-disabled:` faellt dadurch nicht faelschlich unter `disabled`, und ein blosses
 * JSX-Attribut `aria-disabled={…}` loest nichts aus - es ist keine Variante. */
export function zustaendeIn(quelltext: string): string[] {
  const ohneKommentare = streicheKommentare(quelltext)
  const gefunden: string[] = []
  for (const zustand of ZUSTANDSVOKABULAR) {
    if (zustand.startsWith('data-')) {
      if (ohneKommentare.includes(zustand)) gefunden.push(zustand)
      continue
    }
    const variante = new RegExp(`(?:^|[^\\w-])(?:(?:group|peer)-)?${zustand}:`)
    // `has-[:disabled]:` ist dieselbe Aussage in anderer Schreibweise.
    const eingebettet = zustand === 'disabled' ? /\[:disabled\]/ : null
    if (
      variante.test(ohneKommentare) ||
      (eingebettet !== null && eingebettet.test(ohneKommentare))
    ) {
      gefunden.push(zustand)
    }
  }
  return gefunden
}

describe('Zustandsabdeckung gegen den Produktcode', () => {
  it('erkennt Zustaende als Variante, nicht als Wort', () => {
    expect(zustaendeIn('className="hover:bg-accent"')).toEqual(['hover'])
    expect(zustaendeIn('className="group-disabled:bg-surface"')).toEqual(['disabled'])
    expect(zustaendeIn('className="has-[:disabled]:text-text-disabled"')).toEqual(['disabled'])
    expect(zustaendeIn('aria-disabled={true}')).toEqual([])
    expect(zustaendeIn('className="aria-disabled:opacity-40"')).toEqual(['aria-disabled'])
    expect(zustaendeIn('className="sm:p-3 lg:p-4 motion-reduce:animate-none"')).toEqual([])
    // Ein Zustand, der nur im Kommentar vorkommt, loest nichts aus - sonst erbte die Regel jede
    // Erlaeuterung als Anforderung.
    expect(zustaendeIn('/* frueher stand hier hover:bg-accent */')).toEqual([])
  })

  it('fuehrt in components.json jeden im Produktcode getragenen Zustand', () => {
    for (const baustein of komponenten.bausteine) {
      const gefuehrt = new Set(baustein.varianten.zustand ?? [])
      for (const quelle of baustein.quellen) {
        const quelltext = readFileSync(`${FRONTEND_DIR}${quelle}`, 'utf8')
        for (const zustand of zustaendeIn(quelltext)) {
          expect(gefuehrt.has(zustand), `${baustein.schluessel} <- ${quelle}: ${zustand}`).toBe(
            true,
          )
        }
      }
    }
  })

  /* UNTERGRENZE FUER DAS, WAS DER TEST GESEHEN HAT. Ohne sie waere ein kaputter Scanner von einem
     sauberen Bestand nicht zu unterscheiden: "kein Zustand gefunden" bestuende immer. */
  it('hat im Bestand ueberhaupt Zustaende gesehen', () => {
    const gesehen = komponenten.bausteine.flatMap((baustein) =>
      baustein.quellen.flatMap((quelle) =>
        zustaendeIn(readFileSync(`${FRONTEND_DIR}${quelle}`, 'utf8')),
      ),
    )
    expect(new Set(gesehen).size).toBeGreaterThanOrEqual(4)
    expect(gesehen.length).toBeGreaterThanOrEqual(6)
  })
})

// ---------------------------------------------------------------------------------------------
// Der Kategorie-Chip
// ---------------------------------------------------------------------------------------------

describe('Der Kategorie-Chip', () => {
  /* ERZEUGT, NICHT GETIPPT: die Sollmenge entsteht aus der erzeugten tokens.json und damit
     mittelbar aus index.css - dieselbe Kette, die der Design-Vertragstest gegen das
     Kategorien-Set des Backends bindet. */
  const chipSchluessel = tokens
    .map((token) => /^color\.chip-(.+)-bg$/.exec(token.name))
    .filter((treffer) => treffer !== null)
    .map((treffer) => treffer![1])

  it('traegt dreizehn Auspraegungen, deckungsgleich mit dem Kategorien-Set', () => {
    expect(chipSchluessel).toHaveLength(13)
    const chip = komponenten.bausteine.find((baustein) => baustein.schluessel === 'chip')
    expect(chip).toBeDefined()
    expect(chip!.varianten.kategorie).toEqual(chipSchluessel)
  })

  it('bindet je Auspraegung das Flaechen- und das Schrifttoken der Kategorie', () => {
    const chip = komponenten.bausteine.find((baustein) => baustein.schluessel === 'chip')!
    for (const schluessel of chipSchluessel) {
      const paar = chip.tokensProAuspraegung?.kategorie?.[schluessel]
      expect(paar, schluessel).toBeDefined()
      expect(paar!.flaeche, schluessel).toBe(`color.chip-${schluessel}-bg`)
      expect(paar!.schrift, schluessel).toBe(`color.chip-${schluessel}-fg`)
    }
  })
})

// ---------------------------------------------------------------------------------------------
// Der elfte Baustein: Platzhalter
// ---------------------------------------------------------------------------------------------

describe('Der Platzhalter', () => {
  const platzhalter = () =>
    komponenten.bausteine.find((baustein) => baustein.schluessel === 'skeleton')!

  /*
   * DIE ZWEI AUSPRAEGUNGEN SIND AUS DEM PRODUKTCODE ABGELEITET, NICHT ERFUNDEN: `zeile` ist die
   * Listenzeile der Projektliste (`rounded-lg`), `kachel` die quadratische bzw. bildfuellende
   * Flaeche (`rounded-md`, der Grundwert des Bausteins). Die Produktdateien stehen hier NAMENTLICH
   * - und genau deshalb NICHT in `quellen`:
   *
   * ⚠ `src/pages/ProjectListPage.tsx` GEHOERT NICHT IN `quellen`. Der Test "fuehrt in
   * components.json jeden im Produktcode getragenen Zustand" liest jede Datei aus `quellen` und
   * verlangt jede dort getragene Tailwind-Zustandsvariante als Auspraegung; eine SEITE dort
   * einzutragen erzwaenge genau die Zustandsachse, die der Platzhalter bewusst nicht hat.
   */
  it('bindet seine zwei Auspraegungen an die Radien aus dem Produktcode', () => {
    const radien = platzhalter().tokensProAuspraegung?.auspraegung
    expect(Object.keys(platzhalter().varianten)).toEqual(['auspraegung'])
    expect(platzhalter().varianten.auspraegung).toEqual(['zeile', 'kachel'])
    expect(radien?.zeile?.radius).toBe('radius.lg')
    expect(radien?.kachel?.radius).toBe('radius.md')
    expect(readFileSync(`${FRONTEND_DIR}src/pages/ProjectListPage.tsx`, 'utf8')).toContain(
      'rounded-lg',
    )
    expect(readFileSync(`${FRONTEND_DIR}src/components/ui/skeleton.tsx`, 'utf8')).toContain(
      'rounded-md',
    )
  })

  it('traegt die Flaeche als Token und keine Seite in den Quellen', () => {
    expect(platzhalter().tokens.flaeche).toBe('color.text-disabled')
    expect(platzhalter().quellen).toEqual(['src/components/ui/skeleton.tsx'])
    for (const quelle of platzhalter().quellen) {
      expect(quelle.startsWith('src/pages/'), quelle).toBe(false)
    }
  })

  /* Der Verzicht auf die Zustandsachse ist MECHANISCH gedeckt: die Produktdatei traegt keinen
     Zustand aus dem geschlossenen Vokabular (`motion-reduce:` ist keiner). Ohne diese Zeile waere
     "keine Zustandsachse" eine Behauptung ueber eine Abwesenheit, die niemand nachgesehen hat. */
  it('traegt im Produktcode keinen Zustand aus dem Vokabular', () => {
    const quelltext = readFileSync(`${FRONTEND_DIR}src/components/ui/skeleton.tsx`, 'utf8')
    expect(zustaendeIn(quelltext)).toEqual([])
    expect(quelltext).toContain('motion-reduce:')
    expect(platzhalter().varianten.zustand).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------------------------
// Die Kardinalitaeten von verify.js
// ---------------------------------------------------------------------------------------------

/**
 * Liest die `ERWARTETE_*`-Konstanten aus dem GEPARSTEN Baum von `verify.js`. Ueber den Baum und
 * nicht ueber eine Zeichenkettensuche: eine Erwaehnung im Kommentar ist keine Konstante.
 */
export function erwarteteKonstanten(quelltext: string): Record<string, number> {
  const gefunden: Record<string, number> = {}
  for (const eintrag of knoten(quelltext, (kandidat) => kandidat.type === 'VariableDeclarator')) {
    const bezeichner = eintrag.id as Record<string, unknown> | null
    const wert = eintrag.init as Record<string, unknown> | null
    if (
      bezeichner?.type === 'Identifier' &&
      typeof bezeichner.name === 'string' &&
      bezeichner.name.startsWith('ERWARTETE_') &&
      wert?.type === 'Literal' &&
      typeof wert.value === 'number'
    ) {
      gefunden[bezeichner.name] = wert.value
    }
  }
  return gefunden
}

const ERWARTET = erwarteteKonstanten(dateiVon('verify.js').roh)

describe('Die Kardinalitaeten von verify.js', () => {
  it('findet die Konstanten ueberhaupt, und zwar im Baum statt im Kommentar', () => {
    expect(Object.keys(ERWARTET).length).toBeGreaterThanOrEqual(6)
    expect(erwarteteKonstanten('const ERWARTETE_PROBE = 7')).toEqual({ ERWARTETE_PROBE: 7 })
    expect(erwarteteKonstanten('/* ERWARTETE_PROBE = 7 */')).toEqual({})
  })

  /*
   * BIDIREKTIONALITAET KONSTANTE <-> FREIGABE. Ohne sie kann eine neue Kardinalitaet mit einem
   * Wert aus `UNVERDAECHTIGE_ZAHLEN` still ohne Freigabe existieren - die blanke-Zahl-Regel
   * schwiege dazu, und die Freigabeliste waere ab dann unvollstaendig, ohne rot zu werden.
   *
   * Eine zusaetzliche "die Zeilennummern stimmen"-Pruefung gibt es bewusst NICHT: sie waere eine
   * zweite Fassung derselben Aussage und alterte getrennt. Der Umbau WIRD garantiert rot.
   */
  it('haelt Konstante und Freigabe deckungsgleich', () => {
    const freigegeben = FREIGABEN.filter((freigabe) => freigabe.datei === 'verify.js').map(
      (freigabe) => /ERWARTETE_[A-Z_]+/.exec(freigabe.ausschnitt)?.[0] ?? freigabe.ausschnitt,
    )
    /*
     * VERGLICHEN WIRD GEGEN DIE KONSTANTEN, DIE UEBERHAUPT EINE FREIGABE BRAUCHEN. Eine
     * Kardinalitaet mit einem Wert aus `UNVERDAECHTIGE_ZAHLEN` erzeugt keinen Fund der
     * blanke-Zahl-Regel; eine Freigabe dafuer waere zwangslaeufig VERWAIST, und der Test darueber
     * wuerde rot. Ohne diese Unterscheidung widersprechen sich die beiden Zusicherungen fuer jeden
     * Wert aus {0, 1, 2, -1} - aufgefallen an `ERWARTETE_ANSICHTSBEHAELTER = 2`.
     *
     * Der Zweck der Bidirektionalitaet bleibt vollstaendig erhalten: Genau die Konstanten, die
     * ohne Freigabe still durchrutschen KOENNTEN, muessen eine haben. Dass auch die uebrigen nicht
     * blosse Dekoration sind, sichert der Test darunter ("gibt jede Kardinalitaet auch zurueck") -
     * und der gilt ausnahmslos fuer alle.
     */
    const brauchtFreigabe = Object.keys(ERWARTET).filter(
      (name) => !UNVERDAECHTIGE_ZAHLEN.has(String(ERWARTET[name])),
    )
    expect([...freigegeben].sort()).toEqual(brauchtFreigabe.sort())
  })

  /* Eine Kardinalitaet, die deklariert, aber nie zurueckgegeben wird, ist Dekoration - und fiele
     ausgerechnet an dem Instanzverlust nicht auf, den sie verhindern soll. */
  it('gibt jede Kardinalitaet auch zurueck', () => {
    const quelltext = dateiVon('verify.js').roh
    const haupt = knoten(
      quelltext,
      (eintrag) =>
        eintrag.type === 'FunctionDeclaration' &&
        (eintrag.id as Record<string, unknown> | null)?.name === 'main',
    )
    expect(haupt).toHaveLength(1)
    const rueckgaben = knoten(
      quelltext,
      (eintrag) =>
        eintrag.type === 'ReturnStatement' &&
        (eintrag.argument as Record<string, unknown> | null)?.type === 'ObjectExpression' &&
        (eintrag.start as number) > (haupt[0]!.start as number) &&
        (eintrag.start as number) < (haupt[0]!.end as number),
    )
    expect(rueckgaben.length).toBeGreaterThan(0)
    for (const name of Object.keys(ERWARTET)) {
      expect(
        rueckgaben.some((rueckgabe) => enthaeltBezeichner(rueckgabe, name)),
        name,
      ).toBe(true)
    }
  })
})

// ---------------------------------------------------------------------------------------------
// Die Soll-Struktur der Ansichten: views.json
// ---------------------------------------------------------------------------------------------

const E2E_DIR = fileURLToPath(new URL('../../e2e/', import.meta.url))

/**
 * Die beiden Brettbreiten werden GELESEN, nicht getippt: sie sind die zwei Pruefbreiten des
 * Projekts. Zwei getippte Namen daneben waeren ab der ersten Umbenennung eine zweite Wahrheit -
 * und ein Entwurf in einer dritten, nur hier gueltigen Breite waere mit dem spaeteren
 * Browser-Nachweis nicht mehr vergleichbar.
 */
export function breitenNamenAus(quelltext: string): string[] {
  const block = /const VIEWPORTS = \{([\s\S]*?)\n\}/.exec(streicheKommentare(quelltext))
  if (block === null) {
    return []
  }
  return [...block[1]!.matchAll(/^\s+([a-z][a-zA-Z0-9-]*)\s*:/gm)].map((treffer) => treffer[1]!)
}

const viewportQuelle = readFileSync(`${E2E_DIR}lib/viewports.ts`, 'utf8')
const BREITEN = breitenNamenAus(viewportQuelle)

/** Geschlossenes Zustandsvokabular der Ansichten. `standard` traegt die Ansicht, die genau EINEN
 * Zustand fuehrt - eine Variantenachse mit einem Wert beschriebe nichts. */
const ANSICHTSZUSTAENDE = ['standard', 'gefuellt', 'leer', 'ladend', 'fehler'] as const

/** Die zwei absehbaren Luecken sind MUSS-Eintraege: ohne sie waere "Luecken werden ausgewiesen"
 * eine Zusage, die eine leere Liste erfuellte. */
const MUSS_LUECKEN = ['bewegung', 'breakpoint'] as const

const ansichtsdatei = JSON.parse(dateiVon('views.json').roh) as {
  datei: string
  ansichten: {
    schluessel: string
    anzeigename: string
    seite: string
    produktdateien: string[]
    breiten: string[]
    zustaende: string[]
    variantenachse: string | null
    bausteine: string[]
    luecken: { schluessel: string; stelle: string; grund: string }[]
  }[]
}

describe('Die Breiten kommen aus der Pruefbreiten-Datei', () => {
  it('liest die Namen aus dem Objekt, aus dem auch VIEWPORT_NAMES entsteht', () => {
    expect(BREITEN).toEqual(['mobile', 'desktop'])
    // Ohne diese Zeile laese der Test ein Objekt, das mit der exportierten Namensliste nichts zu
    // tun haben muesste.
    expect(streicheKommentare(viewportQuelle)).toContain('Object.keys(VIEWPORTS)')
  })

  it('erkennt die Namen an einer synthetischen Probe', () => {
    expect(
      breitenNamenAus(
        'export const VIEWPORTS = {\n  schmal: { width: 1 },\n  breit: { width: 2 },\n} as const',
      ),
    ).toEqual(['schmal', 'breit'])
    expect(breitenNamenAus('const ANDERES = {\n  schmal: 1,\n}')).toEqual([])
  })
})

describe('views.json: die Soll-Struktur der Ansichten', () => {
  const ansichten = ansichtsdatei.ansichten

  /* GESCHLOSSENE NAMENSMENGE INKLUSIVE REIHENFOLGE, nicht blosse Kardinalitaet - dieselbe Bauart
     wie bei den Bausteinen. */
  it('fuehrt genau die sechs Ansichten in dieser Reihenfolge', () => {
    expect(ansichten.map((ansicht) => ansicht.schluessel)).toEqual([
      'uebersicht',
      'anlegen',
      'pflegen',
      'loeschen',
      'schrittleiste',
      'fotos',
    ])
    expect(ansichten.map((ansicht) => ansicht.anzeigename)).toEqual([
      'Projektübersicht',
      'Projekt anlegen',
      'Projekt pflegen',
      'Projekt löschen',
      'Schrittleiste',
      'Fotos',
    ])
  })

  /* Der Seitenname ist eine ABLEITUNG, kein zweiter getippter Wert. */
  it('leitet den Seitennamen aus dem Anzeigenamen ab', () => {
    for (const ansicht of ansichten) {
      expect(ansicht.seite, ansicht.schluessel).toBe(`Ansicht — ${ansicht.anzeigename}`)
    }
  })

  /* `/` ist in Penpot ein PFADTRENNER: ein Name mit Schraegstrich kommt anders zurueck, als er
     gesetzt wurde, und jeder Vergleich am Namen geht danach ins Leere. */
  it('vergibt keinen Namen mit Schraegstrich', () => {
    for (const ansicht of ansichten) {
      for (const name of [ansicht.schluessel, ansicht.anzeigename, ansicht.seite]) {
        expect(name, name).not.toContain('/')
      }
    }
  })

  it('fuehrt je Ansicht genau die zwei Pruefbreiten', () => {
    expect(BREITEN.length).toBe(2)
    for (const ansicht of ansichten) {
      expect(ansicht.breiten, ansicht.schluessel).toEqual(BREITEN)
    }
  })

  it('fuehrt Zustaende nur aus dem geschlossenen Vokabular, ohne Dublette', () => {
    for (const ansicht of ansichten) {
      expect(ansicht.zustaende.length, ansicht.schluessel).toBeGreaterThan(0)
      expect(new Set(ansicht.zustaende).size, ansicht.schluessel).toBe(ansicht.zustaende.length)
      for (const zustand of ansicht.zustaende) {
        expect(ANSICHTSZUSTAENDE, `${ansicht.schluessel}: ${zustand}`).toContain(zustand)
      }
    }
  })

  /*
   * DIE KOPPLUNG, die Akzeptanzkriterium 8 traegt: mehr als ein Zustand GENAU DANN, wenn die
   * Ansicht die Variantenachse `zustand` fuehrt. Damit ist beides ausgeschlossen - eine Achse mit
   * einem Wert (sie beschriebe nichts) und vier nebeneinandergestellte Bretter (sie ergaeben mehr
   * Bretter als die Summe unten zulaesst). Die Breite ist ausdruecklich KEINE Achse.
   */
  it('koppelt mehr als einen Zustand an die Variantenachse zustand', () => {
    for (const ansicht of ansichten) {
      if (ansicht.zustaende.length > 1) {
        expect(ansicht.variantenachse, ansicht.schluessel).toBe('zustand')
      } else {
        expect(ansicht.variantenachse, ansicht.schluessel).toBeNull()
      }
      expect(ansicht.variantenachse, ansicht.schluessel).not.toBe('breite')
    }
  })

  /* DIE BRETTZAHL ALS SUMME, nicht als getippte Zahl - und gebunden gegen die Kardinalitaet, mit
     der `verify.js` denselben Stand zurueckliest. */
  it('ergibt in der Summe die zurueckgelesene Zahl an Ansichtsbrettern', () => {
    const bretter = ansichten.reduce(
      (summe, ansicht) => summe + ansicht.breiten.length * ansicht.zustaende.length,
      0,
    )
    expect(ansichten.length).toBe(ERWARTET.ERWARTETE_ANSICHTEN)
    expect(bretter).toBe(ERWARTET.ERWARTETE_ANSICHTSBRETTER)
  })

  /*
   * UND DIE BEHAELTERZAHL EBENSO. Ohne diese Zeile waere `ERWARTETE_ANSICHTSBEHAELTER` als
   * einzige der drei Ansichts-Kardinalitaeten an nichts gebunden: Der Test darueber sichert nur,
   * dass sie im Rueckgabeobjekt vorkommt, nicht WELCHEN Wert sie hat. Sie liesse sich auf eine
   * beliebige Zahl setzen, ohne dass etwas rot wird - und faellt dann ausgerechnet an dem
   * Instanzverlust nicht auf, den sie verhindern soll.
   *
   * Ein Behaelter entsteht je Breite genau dann, wenn die Ansicht mehr als einen Zustand fuehrt;
   * das ist dieselbe Bedingung, die den Test "koppelt mehr als einen Zustand an die
   * Variantenachse zustand" traegt, und sie wird hier abgeleitet statt getippt.
   */
  it('ergibt in der Summe die zurueckgelesene Zahl an Ansichts-Behaeltern', () => {
    const behaelter = ansichten.reduce(
      (summe, ansicht) => summe + (ansicht.zustaende.length > 1 ? ansicht.breiten.length : 0),
      0,
    )
    expect(behaelter).toBe(ERWARTET.ERWARTETE_ANSICHTSBEHAELTER)
  })

  it('nennt je Ansicht nur Bausteine, die es gibt, und mindestens einen', () => {
    const bekannt = new Set(komponenten.bausteine.map((baustein) => baustein.schluessel))
    for (const ansicht of ansichten) {
      expect(ansicht.bausteine.length, ansicht.schluessel).toBeGreaterThan(0)
      expect(new Set(ansicht.bausteine).size, ansicht.schluessel).toBe(ansicht.bausteine.length)
      for (const schluessel of ansicht.bausteine) {
        expect(bekannt.has(schluessel), `${ansicht.schluessel}: ${schluessel}`).toBe(true)
      }
    }
  })

  /* Ohne diese Zeile bliebe die Aufnahmebedingung des elften Bausteins unbelegt: er waere ein
     Vorratsbaustein, den kein Entwurf braucht. */
  it('verwendet den Platzhalter in mindestens einer Ansicht', () => {
    expect(ansichten.some((ansicht) => ansicht.bausteine.includes('skeleton'))).toBe(true)
  })

  it('weist jede Luecke mit Stelle und Grund aus', () => {
    for (const ansicht of ansichten) {
      expect(ansicht.luecken.length, ansicht.schluessel).toBeGreaterThan(0)
      const schluessel = ansicht.luecken.map((luecke) => luecke.schluessel)
      expect(new Set(schluessel).size, ansicht.schluessel).toBe(schluessel.length)
      for (const luecke of ansicht.luecken) {
        const pfad = `${ansicht.schluessel}.${luecke.schluessel}`
        expect(luecke.schluessel.length, pfad).toBeGreaterThan(0)
        expect(luecke.stelle.length, pfad).toBeGreaterThanOrEqual(12)
        expect(luecke.grund.length, pfad).toBeGreaterThanOrEqual(40)
      }
    }
  })

  it('fuehrt die zwei absehbaren Luecken als Muss-Eintraege', () => {
    const gefuehrt = new Set(
      ansichten.flatMap((ansicht) => ansicht.luecken.map((luecke) => luecke.schluessel)),
    )
    for (const muss of MUSS_LUECKEN) {
      expect(gefuehrt.has(muss), muss).toBe(true)
    }
  })

  /* BEDINGT: heute ist die Liste leer (die Ansichten sind noch nicht gebaut). Wird sie gefuellt,
     muss jede genannte Datei tatsaechlich lesbar sein - sonst waere sie eine Behauptung. */
  it('nennt nur Produktdateien, die es gibt', () => {
    for (const ansicht of ansichten) {
      for (const quelle of ansicht.produktdateien) {
        expect(() => readFileSync(`${FRONTEND_DIR}${quelle}`, 'utf8'), quelle).not.toThrow()
      }
    }
  })

  /* Wo `views.json` einen Tokennamen nennt, gilt dieselbe referentielle Integritaet wie fuer
     `components.json`. Der Erkenner selbst wird an einer synthetischen Probe belegt - eine
     Zusicherung, die auf einer leeren Fundmenge bestuende, pruefte nichts. */
  it('nennt nur Tokens, die es gibt', () => {
    const genannt = [...dateiVon('views.json').roh.matchAll(TOKENNAME_MUSTER)].map(
      (treffer) => treffer[0],
    )
    expect([...new Set(genannt)].filter((name) => !tokennamen.has(name))).toEqual([])
    expect([...'color.erfunden-gibt-es-nicht'.matchAll(TOKENNAME_MUSTER)]).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------------------------
// Die Idempotenz-Asymmetrie als FORM
// ---------------------------------------------------------------------------------------------

/** Eingefrorene Zuordnung Datei -> Laufregel. `verify.js` liest nur zurueck und ist keine
 * Aufbaudatei; es traegt deshalb KEINE Laufregel - auch das ist eingefroren, sonst waere eine
 * ueberzaehlige Zeile nicht von einer beabsichtigten zu unterscheiden. */
const LAUFREGELN: Record<string, string | null> = {
  'seed-tokens.js': 'jederzeit-wiederholbar',
  'seed-icons.js': 'jederzeit-wiederholbar',
  'seed-components.js': 'nur-auf-leerer-datei',
  'verify.js': null,
  /* `views.json` laeuft NICHT: sie ist eine Soll-Struktur, keine Nutzlast, und bekommt in der
     Schritttabelle keinen Einfuegenamen. Hier eingefroren, damit das eine GEPRUEFTE Aussage ist
     statt einer Absicht - genau wie bei `verify.js`. */
  'views.json': null,
}

const LAUFREGEL_ZEILE = /^\s*\/\/ LAUFREGEL: (\S+)\s*$/

describe('Idempotenz-Asymmetrie: die Laufregel als Form', () => {
  it('traegt je Aufbaudatei genau eine Laufregel-Zeile, aus geschlossenem Vokabular', () => {
    for (const [datei, regel] of Object.entries(LAUFREGELN)) {
      const zeilen = dateiVon(datei).roh.split('\n')
      const treffer = zeilen
        .map((zeile) => LAUFREGEL_ZEILE.exec(zeile))
        .filter((gefunden) => gefunden !== null)
      if (regel === null) {
        expect(treffer, datei).toHaveLength(0)
        continue
      }
      expect(treffer, datei).toHaveLength(1)
      expect(treffer[0]![1], datei).toBe(regel)
    }
  })

  /* AN FESTER STELLE: Zeile 1. Eine Erwaehnung im Fliesstext des Dateikopfs loest nichts aus und
     erfuellt nichts - ein Kopftext darf ueber seinen eigenen frueheren Zustand reden. */
  it('stellt die Laufregel in die erste Zeile', () => {
    for (const [datei, regel] of Object.entries(LAUFREGELN)) {
      if (regel === null) continue
      expect(dateiVon(datei).roh.split('\n')[0], datei).toBe(`// LAUFREGEL: ${regel}`)
    }
  })

  it('erkennt eine Erwaehnung im Fliesstext nicht als Laufregel', () => {
    expect(LAUFREGEL_ZEILE.test(' * frueher galt hier LAUFREGEL: jederzeit-wiederholbar')).toBe(
      false,
    )
    expect(LAUFREGEL_ZEILE.test('// LAUFREGEL: jederzeit-wiederholbar')).toBe(true)
  })
})

// ---------------------------------------------------------------------------------------------
// Die Vorbedingung von seed-components.js
// ---------------------------------------------------------------------------------------------

/** Aufrufe, die in Penpot etwas ANLEGEN oder AENDERN. Die Liste ist die Grundlage der
 * Reihenfolge-Zusicherung; sie muss im Bestand anschlagen, sonst prueft die Zusicherung nichts. */
const SCHREIBAUFRUFE = [
  'addSet',
  'addToken',
  'addFlexLayout',
  'applyToken',
  'applyToShapes',
  'createComponent',
  'createVariantContainer',
  'createBoard',
  'createRectangle',
  'createText',
  'createEllipse',
  'createShapeFromSvg',
  'appendChild',
  'setPluginData',
  'switchVariant',
  'instance',
]

interface Aufruf {
  name: string
  start: number
  argumente: Record<string, unknown>[]
}

/**
 * Parst eine Nutzlastdatei so, wie `execute_code` sie ausfuehrt: als FUNKTIONSRUMPF. Das ist kein
 * Kniff, sondern die Ausfuehrungsform - die Dateien enden auf ein `return` auf oberster Ebene,
 * das als Programm ein Syntaxfehler waere und als Funktionsrumpf genau richtig ist.
 */
function geparst(quelltext: string): unknown {
  return parseAst(`function __rumpf() {\n${quelltext}\n}`)
}

function aufrufe(quelltext: string): Aufruf[] {
  const gefunden: Aufruf[] = []
  const gehe = (knoten: unknown): void => {
    if (knoten === null || typeof knoten !== 'object') return
    if (Array.isArray(knoten)) {
      for (const kind of knoten) gehe(kind)
      return
    }
    const eintrag = knoten as Record<string, unknown>
    if (eintrag.type === 'CallExpression') {
      const callee = eintrag.callee as Record<string, unknown>
      const name =
        callee.type === 'Identifier'
          ? (callee.name as string)
          : callee.type === 'MemberExpression' &&
              (callee.property as Record<string, unknown>).type === 'Identifier'
            ? ((callee.property as Record<string, unknown>).name as string)
            : ''
      gefunden.push({
        name,
        start: eintrag.start as number,
        argumente: (eintrag.arguments as Record<string, unknown>[]) ?? [],
      })
    }
    for (const wert of Object.values(eintrag)) gehe(wert)
  }
  gehe(geparst(quelltext))
  return gefunden.sort((a, b) => a.start - b.start)
}

function schluesselVon(knoten: Record<string, unknown>): string[] {
  return ((knoten.properties as Record<string, unknown>[]) ?? [])
    .map((eigenschaft) => (eigenschaft.key as Record<string, unknown>)?.name as string)
    .filter((name) => typeof name === 'string')
    .sort()
}

describe('Vorbedingung von seed-components.js', () => {
  const quelltext = dateiVon('seed-components.js').roh
  const geparst = aufrufe(quelltext)

  it('ruft ueberhaupt Schreibaufrufe auf', () => {
    const schreibend = geparst.filter((aufruf) => SCHREIBAUFRUFE.includes(aufruf.name))
    expect(schreibend.length).toBeGreaterThan(0)
  })

  /* UEBER DIE GEPARSTE AUFRUFSTELLE, NIE UEBER text.index: eine Zeichenkettensuche faende die
     Vorbedingung auch in einem Kommentar oder in einer Zeichenkette. */
  it('steht vor dem ersten Schreibzugriff', () => {
    const wache = geparst.find((aufruf) => aufruf.name === 'pruefeLeereDatei')
    const ersterSchreibzugriff = geparst.find((aufruf) => SCHREIBAUFRUFE.includes(aufruf.name))
    expect(wache).toBeDefined()
    expect(ersterSchreibzugriff).toBeDefined()
    expect(wache!.start).toBeLessThan(ersterSchreibzugriff!.start)
  })

  it('bricht in der Vorbedingung fail-closed ab', () => {
    // Eine Vorbedingung, die nur meldet statt abzubrechen, ist keine. Nach ADR 0065 ist der
    // Penpot-Stand die normative Design-Quelle - ein versehentlicher zweiter Lauf vernichtet
    // nicht eine Kopie, sondern das Original.
    const ohneKommentare = streicheKommentare(quelltext)
    expect(ohneKommentare).toMatch(/function pruefeLeereDatei\s*\([^)]*\)\s*\{/)
    // Nur der Koerper der Wache selbst, nicht "irgendwo weiter unten steht auch ein throw".
    const koerper = ohneKommentare.split('function pruefeLeereDatei')[1].split('\nfunction ')[0]
    expect(koerper).toContain('throw new Error')
  })
})

// ---------------------------------------------------------------------------------------------
// Die Form der Plugin-API-Aufrufe
// ---------------------------------------------------------------------------------------------

/**
 * WARUM ES DIESE TABELLE GIBT: Die Nutzlast ist unausgefuehrter Code, und die Plugin-API weicht an
 * mehreren Stellen von ihrer eigenen Doku ab. Eine Review-Runde hat genau in dieser Klasse sieben
 * Fehler gefunden - falsche Argumentform bei `addSet`/`addToken`, ein nicht existierender
 * Eigenschaftsname, ein fehlendes `return`, blanke Boards statt Variantenpaaren. Keine der
 * bisherigen Regeln (Wertfreiheit, Benennung, Reihenfolge, verbotene Bezeichner) konnte davon
 * etwas sehen. Diese Tabelle ist die Regel, die diese Fehlerklasse faengt.
 *
 * Geprueft wird ueber die GEPARSTE Aufrufstelle, nicht ueber eine Textsuche - eine Zeichenkette in
 * einem Kommentar oder in einem Literal ist kein Aufruf.
 *
 * Sie ersetzt keinen echten Lauf: Sie sichert die FORM zu, nicht die Wirkung.
 */
const AUFRUFFORMEN: {
  name: string
  erwartung: string
  haelt: (argumente: Record<string, unknown>[]) => boolean
}[] = [
  {
    name: 'addSet',
    erwartung: 'genau ein Objektliteral mit dem Schluessel name',
    haelt: (argumente) =>
      argumente.length === 1 &&
      argumente[0].type === 'ObjectExpression' &&
      schluesselVon(argumente[0]).join(',') === 'name',
  },
  {
    name: 'addToken',
    erwartung: 'genau ein Objektliteral mit den Schluesseln name, type, value',
    haelt: (argumente) =>
      argumente.length === 1 &&
      argumente[0].type === 'ObjectExpression' &&
      schluesselVon(argumente[0]).join(',') === 'name,type,value',
  },
  {
    // Das erste Argument ist eine Formen-MENGE, nie eine Einzelform (gemessen). Statisch
    // greifbar ist hier nur die Stelligkeit - dass es tatsaechlich eine Menge ist, sichert die
    // dateispezifische Regel weiter unten ("auf die Blattformen, nicht auf die Gruppe").
    name: 'applyToShapes',
    erwartung: 'zwei Argumente (Formenmenge und Eigenschaft)',
    haelt: (argumente) => argumente.length === 2,
  },
  {
    name: 'createComponent',
    erwartung: 'genau ein Formen-Array',
    haelt: (argumente) => argumente.length === 1 && argumente[0].type === 'ArrayExpression',
  },
  {
    name: 'createVariantContainer',
    erwartung: 'genau ein Argument (die Liste der Varianteneintraege)',
    haelt: (argumente) => argumente.length === 1,
  },
  {
    name: 'createShapeFromSvg',
    erwartung: 'genau ein Argument (das Markup)',
    haelt: (argumente) => argumente.length === 1,
  },
  {
    name: 'setPluginData',
    erwartung: 'zwei Argumente (Schluessel und Wert)',
    haelt: (argumente) => argumente.length === 2,
  },
  {
    name: 'getPluginData',
    erwartung: 'genau ein Argument (der Schluessel)',
    haelt: (argumente) => argumente.length === 1,
  },
]

const JS_NUTZLAST = ['seed-tokens.js', 'seed-icons.js', 'seed-components.js', 'verify.js'] as const

describe('Die Form der Plugin-API-Aufrufe', () => {
  const alleAufrufe = JS_NUTZLAST.flatMap((datei) =>
    aufrufe(dateiVon(datei).roh).map((aufruf) => ({ datei, aufruf })),
  )

  for (const form of AUFRUFFORMEN) {
    it(`ruft ${form.name} auf als: ${form.erwartung}`, () => {
      const stellen = alleAufrufe.filter(({ aufruf }) => aufruf.name === form.name)
      // Ohne diese Untergrenze bestuende die Zusage auch dann, wenn der Aufruf ganz verschwaende.
      expect(stellen.length, `${form.name} kommt in der Nutzlast nicht vor`).toBeGreaterThan(0)
      const falsch = stellen.filter(({ aufruf }) => !form.haelt(aufruf.argumente))
      expect(falsch.map(({ datei }) => `${datei}: ${form.name}`)).toEqual([])
    })
  }

  /* Der Varianteneintrag traegt gemessen genau `shape` und `properties`. Er entsteht dynamisch,
     ist als Literal aber genau einmal im Quelltext sichtbar - dort wird er festgehalten. */
  it('baut den Varianteneintrag aus shape und properties', () => {
    const formen: string[] = []
    const gehe = (knoten: unknown): void => {
      if (knoten === null || typeof knoten !== 'object') return
      if (Array.isArray(knoten)) {
        for (const kind of knoten) gehe(kind)
        return
      }
      const eintrag = knoten as Record<string, unknown>
      if (eintrag.type === 'ObjectExpression') {
        const schluessel = schluesselVon(eintrag).join(',')
        if (schluessel.includes('shape')) formen.push(schluessel)
      }
      for (const wert of Object.values(eintrag)) gehe(wert)
    }
    gehe(geparst(dateiVon('seed-components.js').roh))
    expect(formen).toEqual(['properties,shape'])
  })

  /* `execute_code` fuehrt den Text als Funktionsrumpf aus und liefert NUR zurueck, was ein
     `return` zurueckgibt (gemessen). Ein blanker Ausdruck am Dateiende ginge still verloren - bei
     `verify.js` waere das der gesamte nachpruefbare Abschluss der Story. */
  it('gibt in jeder Nutzlastdatei ein Ergebnis zurueck', () => {
    for (const datei of JS_NUTZLAST) {
      const zeilen = streicheKommentare(dateiVon(datei).roh)
        .split('\n')
        .map((zeile) => zeile.trim())
        .filter((zeile) => zeile.length > 0)
      expect(zeilen[zeilen.length - 1], datei).toMatch(/^return /)
    }
  })

  it('erkennt eine falsche Aufrufform an synthetischen Proben', () => {
    const form = (name: string) => AUFRUFFORMEN.find((eintrag) => eintrag.name === name)!
    const argumenteVon = (quelltext: string, name: string) =>
      aufrufe(quelltext).find((aufruf) => aufruf.name === name)!.argumente

    expect(form('addSet').haelt(argumenteVon("katalog.addSet('photosort')", 'addSet'))).toBe(false)
    expect(form('addSet').haelt(argumenteVon("katalog.addSet({ name: 'x' })", 'addSet'))).toBe(true)
    expect(form('addToken').haelt(argumenteVon('satz.addToken(a, b, c)', 'addToken'))).toBe(false)
    expect(
      form('addToken').haelt(
        argumenteVon('satz.addToken({ type: t, name: n, value: v })', 'addToken'),
      ),
    ).toBe(true)
    expect(
      form('applyToShapes').haelt(argumenteVon('token.applyToShapes(formen)', 'applyToShapes')),
    ).toBe(false)
    expect(
      form('applyToShapes').haelt(
        argumenteVon("token.applyToShapes(formen, 'fill')", 'applyToShapes'),
      ),
    ).toBe(true)
    expect(
      form('createComponent').haelt(argumenteVon('bib.createComponent(brett)', 'createComponent')),
    ).toBe(false)
  })
})

// ---------------------------------------------------------------------------------------------
// Die Penpot-Eigenschaften, auf die Tokens angewandt werden
// ---------------------------------------------------------------------------------------------

/**
 * Geschlossene Liste der Eigenschaftsnamen, die `applyToShapes` annimmt.
 *
 * WARUM ES SIE GIBT: Der Eigenschaftsname war zweimal die Fehlerquelle - erst `stroke` (existiert
 * nicht, heisst `strokeColor`), dann `border-radius` und `padding` (Sammelnamen, die es nicht
 * gibt; Penpot kennt nur die vier Ecken bzw. die vier Seiten einzeln). Beide Male fiel es erst
 * beim Lauf an der Instanz auf. Ein ERFUNDENER Name faellt ab jetzt in CI auf.
 *
 * HERKUNFT: aus der API-Doku, **nicht vollstaendig gemessen**. Gemessen sind `fill`,
 * `strokeColor`, `height`, `paddingLeft`/`paddingTop` (auch in Kebab-Schreibweise), `rowGap` und
 * `borderRadiusTopLeft`; die uebrigen stehen hier auf Grundlage der Doku. Die Liste ist damit
 * keine Garantie, dass ein Name funktioniert - wohl aber eine, dass keiner frei erfunden ist.
 */
const PENPOT_EIGENSCHAFTEN = [
  'fill',
  'strokeColor',
  'strokeWidth',
  'opacity',
  'rotation',
  'x',
  'y',
  'width',
  'height',
  'borderRadiusTopLeft',
  'borderRadiusTopRight',
  'borderRadiusBottomRight',
  'borderRadiusBottomLeft',
  'paddingLeft',
  'paddingRight',
  'paddingTop',
  'paddingBottom',
  'marginLeft',
  'marginRight',
  'marginTop',
  'marginBottom',
  'rowGap',
  'columnGap',
  'fontSize',
  'fontFamily',
  'fontWeight',
  'letterSpacing',
  'typography',
  'textCase',
  'textDecoration',
] as const

/**
 * Liest eine als Objektliteral geschriebene Konstante der Nutzlast aus dem geparsten Baum.
 *
 * Wirft statt zu behaupten - und wird in jedem Testfall neu aufgerufen, damit ein Fehler in der
 * Tabelle einen BENANNTEN Test rot faerbt statt die ganze Datei beim Einsammeln.
 */
function objektKonstante(quelltext: string, name: string): Record<string, string[]> {
  const deklaration = knoten(
    quelltext,
    (eintrag) =>
      eintrag.type === 'VariableDeclarator' &&
      (eintrag.id as Record<string, unknown>)?.name === name,
  )[0]
  if (deklaration === undefined) {
    throw new Error(`${name} nicht gefunden.`)
  }
  const literal = deklaration.init as Record<string, unknown>
  if (literal?.type !== 'ObjectExpression') {
    throw new Error(`${name} ist kein Objektliteral.`)
  }

  const ergebnis: Record<string, string[]> = {}
  for (const eigenschaft of (literal.properties as Record<string, unknown>[]) ?? []) {
    const schluessel = eigenschaft.key as Record<string, unknown>
    const wert = eigenschaft.value as Record<string, unknown>
    const rolle = (schluessel.name ?? schluessel.value) as string
    if (wert.type !== 'ArrayExpression') {
      throw new Error(`${name}.${rolle} bildet nicht auf eine Liste ab, sondern auf ${wert.type}.`)
    }
    ergebnis[rolle] = ((wert.elements as Record<string, unknown>[]) ?? []).map(
      (element) => element.value as string,
    )
  }
  return ergebnis
}

const rollenTabelle = () =>
  objektKonstante(dateiVon('seed-components.js').roh, 'ROLLE_ZU_EIGENSCHAFT')

describe('Die Penpot-Eigenschaften', () => {
  it('bildet jede Rolle auf eine Liste ab, auch bei nur einer Eigenschaft', () => {
    // Das Lesen selbst wirft, sobald ein Eintrag keine Liste ist - hier bleibt die Untergrenze,
    // damit die Zusicherung nicht ueber einer leeren Tabelle leer wahr wird.
    const rollen = rollenTabelle()
    expect(Object.keys(rollen).length).toBeGreaterThanOrEqual(10)
    for (const [rolle, eigenschaften] of Object.entries(rollen)) {
      expect(eigenschaften.length, rolle).toBeGreaterThan(0)
    }
  })

  it('nennt ausschliesslich Eigenschaften aus der geschlossenen Liste', () => {
    for (const [rolle, eigenschaften] of Object.entries(rollenTabelle())) {
      for (const eigenschaft of eigenschaften) {
        expect(PENPOT_EIGENSCHAFTEN, `${rolle}: ${eigenschaft}`).toContain(eigenschaft)
      }
    }
  })

  /* Die beiden Sammelnamen, an denen der Lauf abgebrochen waere - namentlich, damit sie nicht
     unbemerkt zurueckkehren. */
  it('benutzt keinen der nicht existierenden Sammelnamen', () => {
    for (const verboten of ['border-radius', 'padding', 'stroke', 'margin', 'gap']) {
      expect(PENPOT_EIGENSCHAFTEN, verboten).not.toContain(verboten)
      for (const eigenschaften of Object.values(rollenTabelle())) {
        expect(eigenschaften, verboten).not.toContain(verboten)
      }
    }
  })

  /* Ein Radius hat vier Ecken, eine Polsterung vier Seiten - eine Rolle, die nur eine davon
     setzte, liesse den Baustein halb gerundet zurueck. */
  it('setzt Radius und Polsterung vollstaendig', () => {
    const rollen = rollenTabelle()
    expect(rollen.radius.length).toBe(4)
    expect(rollen.innenabstand.length).toBe(4)
    expect(rollen['innenabstand-quer']).toEqual(['paddingLeft', 'paddingRight'])
    expect(rollen['innenabstand-laengs']).toEqual(['paddingTop', 'paddingBottom'])
  })

  it('nennt auch im Symbolimport nur bekannte Eigenschaften', () => {
    const quelltext = dateiVon('seed-icons.js').roh
    const liste = knoten(
      quelltext,
      (eintrag) =>
        eintrag.type === 'VariableDeclarator' &&
        (eintrag.id as Record<string, unknown>)?.name === 'STRICH_EIGENSCHAFTEN',
    )[0]
    expect(liste, 'STRICH_EIGENSCHAFTEN nicht gefunden').toBeDefined()
    const werte = (
      ((liste.init as Record<string, unknown>).elements as Record<string, unknown>[]) ?? []
    ).map((element) => element.value as string)
    expect(werte.length).toBeGreaterThan(0)
    for (const eigenschaft of werte) {
      expect(PENPOT_EIGENSCHAFTEN, eigenschaft).toContain(eigenschaft)
    }
  })
})

// ---------------------------------------------------------------------------------------------
// Der Symbolimport
// ---------------------------------------------------------------------------------------------

/** Sucht im geparsten Baum nach Knoten, fuer die das Praedikat zutrifft. */
function knoten(quelltext: string, trifft: (eintrag: Record<string, unknown>) => boolean) {
  const gefunden: Record<string, unknown>[] = []
  const gehe = (wert: unknown): void => {
    if (wert === null || typeof wert !== 'object') return
    if (Array.isArray(wert)) {
      for (const kind of wert) gehe(kind)
      return
    }
    const eintrag = wert as Record<string, unknown>
    if (typeof eintrag.type === 'string' && trifft(eintrag)) gefunden.push(eintrag)
    for (const teil of Object.values(eintrag)) gehe(teil)
  }
  gehe(geparst(quelltext))
  return gefunden
}

function enthaeltBezeichner(wurzel: unknown, name: string): boolean {
  let gefunden = false
  const gehe = (wert: unknown): void => {
    if (gefunden || wert === null || typeof wert !== 'object') return
    if (Array.isArray(wert)) {
      for (const kind of wert) gehe(kind)
      return
    }
    const eintrag = wert as Record<string, unknown>
    if (eintrag.type === 'Identifier' && eintrag.name === name) {
      gefunden = true
      return
    }
    for (const teil of Object.values(eintrag)) gehe(teil)
  }
  gehe(wurzel)
  return gefunden
}

describe('Der Symbolimport', () => {
  const quelltext = dateiVon('seed-icons.js').roh

  /*
   * EINE GRUPPE TRAEGT IN PENPOT KEINEN EIGENEN STRICH. Das Strichfarben-Token auf das Ergebnis
   * von `createShapeFromSvg` anzuwenden lief im echten Lauf ins Leere: Die Gruppe blieb ohne
   * Bindung, der Pfad darunter kam schwarz an. Angewandt wird es deshalb auf eine daraus
   * ABGELEITETE Blattform-Menge - und genau das ist hier festgehalten.
   */
  it('wendet das Token auf die Blattformen an, nicht auf die Gruppe', () => {
    const stellen = aufrufe(quelltext).filter((aufruf) => aufruf.name === 'wendeTokenAn')
    expect(stellen.length, 'wendeTokenAn kommt nicht vor').toBeGreaterThan(0)
    for (const stelle of stellen) {
      const erstes = stelle.argumente[0]
      expect(erstes?.type, 'erstes Argument').toBe('CallExpression')
      expect((erstes?.callee as Record<string, unknown>)?.name).toBe('blattformen')
    }
  })

  /* Rekursiv, nicht nur eine Ebene: die heutigen Symbolgruppen sind flach, ein kuenftiges Symbol
     mit verschachtelter Gruppe verloere sonst still seine Farbe. */
  it('sammelt die Blattformen rekursiv ein', () => {
    const rekursiv = aufrufe(quelltext).filter((aufruf) => aufruf.name === 'blattformen')
    // Der Aufruf in `main` plus mindestens ein Selbstaufruf in der Funktion.
    expect(rekursiv.length).toBeGreaterThan(1)
  })

  /*
   * DER PRAEFIX WIRD GENAU EINMAL GESETZT. Ihn zusaetzlich ueber `komponente.name` zu setzen hing
   * ihn ein zweites Mal vor den bereits bestehenden Pfad (gemessen: `path: "symbol / symbol"`).
   * Geprueft ueber die geparsten Zuweisungen, nicht ueber eine Textsuche.
   */
  it('setzt den Pfadpraefix je Symbol genau einmal', () => {
    const zuweisungen = knoten(
      quelltext,
      (eintrag) =>
        eintrag.type === 'AssignmentExpression' && enthaeltBezeichner(eintrag.right, 'SYMBOL_PFAD'),
    )
    expect(zuweisungen).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------------------------
// Die geteilte Erkennung der Bausteine
// ---------------------------------------------------------------------------------------------

/**
 * `seed-components.js` (Waechter) und `verify.js` (Rueckleser) muessen die Bausteine AUF DIESELBE
 * WEISE wiedererkennen. Genau an dieser Doppelung ist es schon einmal auseinandergelaufen: Der
 * Waechter suchte deutsche Anzeigenamen, der Rueckleser Plugin-Daten, und weil
 * `createVariantContainer` die Komponenten in "Component" umbenennt und der Behaelter gar nicht in
 * `library.local.components` steht, griff beides ins Leere - der fail-closed-Waechter der
 * normativen Design-Quelle feuerte nie.
 *
 * Zugesichert wird deshalb die WORTGLEICHHEIT des Blocks, nicht seine Wirkung.
 */
const GETEILTE_ERKENNUNG = [
  'function bausteinSchluesselInDatei() {',
  '  const gefunden = []',
  '  for (const komponente of penpot.library.local.components) {',
  "    const schluessel = komponente.getPluginData('schluessel')",
  '    if (schluessel && gefunden.indexOf(schluessel) === -1) {',
  '      gefunden.push(schluessel)',
  '    }',
  '  }',
  '  return gefunden',
  '}',
].join('\n')

/**
 * Zweiter geteilter Block: `/` ist in Penpot ein PFADTRENNER. `symbol/star` liegt als
 * `{ name: "star", path: "symbol" }` vor - die volle Zeichenkette steht in keinem einzelnen Feld
 * (gemessen). Ein Vergleich am Namen trifft deshalb nie: `seed-icons.js` legte bei jedem Lauf
 * Dubletten an, und `verify.js` meldete null Symbole.
 */
const GETEILTE_SYMBOLERKENNUNG = [
  'function symbolNameVon(komponente) {',
  '  if (komponente.path !== SYMBOL_PFAD) {',
  "    return ''",
  '  }',
  '  return komponente.name',
  '}',
].join('\n')

const GETEILTE_BLOECKE: {
  name: string
  dateien: readonly string[]
  block: string
  aufruf: string
}[] = [
  {
    name: 'Bausteinerkennung',
    dateien: ['seed-components.js', 'verify.js'],
    block: GETEILTE_ERKENNUNG,
    aufruf: 'bausteinSchluesselInDatei',
  },
  {
    name: 'Symbolerkennung',
    dateien: ['seed-icons.js', 'verify.js'],
    block: GETEILTE_SYMBOLERKENNUNG,
    aufruf: 'symbolNameVon',
  },
]

describe('Die geteilten Erkennungen', () => {
  for (const geteilt of GETEILTE_BLOECKE) {
    it(`${geteilt.name}: steht wortgleich in ${geteilt.dateien.join(' und ')}`, () => {
      for (const datei of geteilt.dateien) {
        expect(dateiVon(datei).roh, datei).toContain(geteilt.block)
      }
    })

    it(`${geteilt.name}: wird in beiden Dateien tatsaechlich benutzt`, () => {
      for (const datei of geteilt.dateien) {
        const stellen = aufrufe(dateiVon(datei).roh).filter(
          (aufruf) => aufruf.name === geteilt.aufruf,
        )
        expect(stellen.length, datei).toBeGreaterThan(0)
      }
    })
  }

  /* Erkannt wird an den Plugin-Daten, nie am Anzeigenamen - der ueberlebt den Variantenbau nicht. */
  it('Bausteinerkennung haengt an den Plugin-Daten, nicht am Namen', () => {
    expect(GETEILTE_ERKENNUNG).toContain("getPluginData('schluessel')")
    expect(GETEILTE_ERKENNUNG).not.toContain('.name')
  })

  /* Der Pfad ist eine Konstante und muss in beiden Dateien dieselbe sein - der geteilte Block
     liest sie, traegt sie aber nicht. */
  it('Symbolerkennung liest denselben Pfad in beiden Dateien', () => {
    for (const datei of ['seed-icons.js', 'verify.js'] as const) {
      expect(dateiVon(datei).roh, datei).toContain("const SYMBOL_PFAD = 'symbol'")
    }
  })

  /* Ein Vergleich, der die volle Zeichenkette `symbol/...` gegen einen Namen haelt, ist genau der
     Fehler, an dem der erste Symbol-Lauf gescheitert ist. */
  it('vergleicht nirgends gegen einen zusammengesetzten Pfadnamen', () => {
    for (const datei of ['seed-icons.js', 'verify.js'] as const) {
      expect(dateiVon(datei).inhalt, datei).not.toContain("'symbol/'")
    }
  })
})

// ---------------------------------------------------------------------------------------------
// Binden oder leeren: die Flaeche jeder Variante
// ---------------------------------------------------------------------------------------------

/**
 * Die Bindungsreihenfolge von `baueVariante` nachgespielt - gespeist aus den beiden Tabellen der
 * Nutzlast selbst (`ROLLE_ZU_EIGENSCHAFT`, `TEXT_ROLLEN`), nie aus einer zweiten getippten Liste.
 *
 * ⚠ GESAMMELT WERDEN DIE EIGENSCHAFTEN, DIE AUFS BRETT GINGEN - nicht die vorgekommenen
 * Rollennamen. `schrift` bildet EBENFALLS auf `fill` ab und traegt praktisch jede betroffene
 * Variante; eine Ableitung "kam eine Rolle vor, die auf `fill` abbildet?" zaehlte sie mit und
 * bliebe ueber dem unveraenderten Fehler dauerhaft gruen.
 *
 * ⚠ UND ZWAR UEBER ALLE AUFRUFE, nicht nur den letzten: `bindeRollen` laeuft je Variante ein- bis
 * viermal, und eine Auspraegungs-Tabelle, die nur `schrift` fuehrt, machte sonst eine laengst
 * gebundene Flaeche wieder zunichte.
 */
interface SimulationsBaustein {
  schluessel: string
  varianten: Record<string, string[]>
  tokens: Record<string, string>
  tokensProAuspraegung?: Record<string, Record<string, Record<string, string>>>
}

interface Bindung {
  kombination: Record<string, string>
  brettEigenschaften: string[]
  flaeche: string | null
  schrift: string | null
}

/** Eigene Schluessel, nie geerbte: `constructor` loeste an einem Objektliteral sonst auf und
 * machte aus einer unbekannten Rolle eine scheinbar bekannte. */
function eigenerWert<T>(tabelle: Record<string, T>, schluessel: string): T | undefined {
  return Object.prototype.hasOwnProperty.call(tabelle, schluessel) ? tabelle[schluessel] : undefined
}

/** Das Kreuzprodukt in derselben Achsenreihenfolge wie `kombinationen` in seed-components.js. */
export function kombinationenVon(varianten: Record<string, string[]>): Record<string, string>[] {
  let ergebnis: Record<string, string>[] = [{}]
  for (const achse of Object.keys(varianten)) {
    const naechste: Record<string, string>[] = []
    for (const bisher of ergebnis) {
      for (const auspraegung of varianten[achse] ?? []) {
        naechste.push({ ...bisher, [achse]: auspraegung })
      }
    }
    ergebnis = naechste
  }
  return ergebnis
}

export function bindungenVon(
  baustein: SimulationsBaustein,
  rollenTabelle: Record<string, string[]>,
  textRollen: readonly string[],
): Bindung[] {
  return kombinationenVon(baustein.varianten).map((kombination) => {
    const brettEigenschaften: string[] = []
    let flaeche: string | null = null
    let schrift: string | null = null

    const anwenden = (rollen: Record<string, string>): void => {
      for (const rolle of Object.keys(rollen)) {
        const eigenschaften = eigenerWert(rollenTabelle, rolle)
        // Eine Rolle ohne Penpot-Eigenschaft wird von `bindeRollen` als `nachzubinden` gemeldet
        // und fasst kein Brett an.
        if (eigenschaften === undefined) continue
        const aufsBrett = !textRollen.includes(rolle)
        for (const eigenschaft of eigenschaften) {
          if (!aufsBrett) {
            if (eigenschaft === 'fill') schrift = rollen[rolle]!
            continue
          }
          if (!brettEigenschaften.includes(eigenschaft)) brettEigenschaften.push(eigenschaft)
          if (eigenschaft === 'fill') flaeche = rollen[rolle]!
        }
      }
    }

    anwenden(baustein.tokens)
    for (const achse of Object.keys(kombination)) {
      const besondere = baustein.tokensProAuspraegung?.[achse]?.[kombination[achse]!]
      if (besondere) anwenden(besondere)
    }
    return { kombination, brettEigenschaften, flaeche, schrift }
  })
}

/** Liest eine als Array-Literal geschriebene Konstante der Nutzlast aus dem geparsten Baum. */
function listenKonstante(quelltext: string, name: string): string[] {
  const deklaration = knoten(
    quelltext,
    (eintrag) =>
      eintrag.type === 'VariableDeclarator' &&
      (eintrag.id as Record<string, unknown>)?.name === name,
  )[0]
  if (deklaration === undefined) {
    throw new Error(`${name} nicht gefunden.`)
  }
  const literal = deklaration.init as Record<string, unknown>
  if (literal?.type !== 'ArrayExpression') {
    throw new Error(`${name} ist kein Array-Literal.`)
  }
  return ((literal.elements as Record<string, unknown>[]) ?? []).map(
    (element) => element.value as string,
  )
}

const textRollenTabelle = () => listenKonstante(dateiVon('seed-components.js').roh, 'TEXT_ROLLEN')

function alleBindungen(): { baustein: SimulationsBaustein; bindung: Bindung }[] {
  const rollen = rollenTabelle()
  const texte = textRollenTabelle()
  return komponenten.bausteine.flatMap((baustein) =>
    bindungenVon(baustein, rollen, texte).map((bindung) => ({ baustein, bindung })),
  )
}

/**
 * Varianten, die im Produkt KEINE eigene Flaeche tragen - eingefroren, je Auspraegung, mit Grund
 * und mit der Zahl der gedeckten Varianten (ADR 0081 Abschnitt 2).
 *
 * ⚠ DIE ZAHL IST TRAGEND, weil die Deckung 1:n ist: Eine Teilaenderung laesst einen Eintrag nicht
 * verwaisen, sondern nur schrumpfen - die blosse Verwaisungspruefung bliebe dabei gruen.
 */
const VARIANTEN_OHNE_FLAECHE: { pfad: string; varianten: number; grund: string }[] = [
  {
    pfad: 'button.auspraegung.ghost',
    varianten: 12,
    grund:
      'Im Produkt `bg-transparent`. Eine Flaeche zeigt die Schaltflaeche erst in hover/active ' +
      '(`hover:bg-overlay`, `active:bg-border`); eine Achsenkombination kann die Variantenmatrix ' +
      'nicht adressieren, weshalb `ueberfahren-flaeche`/`gedrueckt-flaeche` ungebunden dastehen.',
  },
  {
    pfad: 'button.auspraegung.link',
    varianten: 12,
    grund:
      'Im Produkt `bg-transparent`: Der Verweis traegt eine Unterstreichung statt einer Flaeche, ' +
      'die Farbe steckt vollstaendig in der Schrift (`color.accent-strong`).',
  },
  {
    pfad: 'badge.auspraegung.neutral',
    varianten: 1,
    grund:
      'Im Produkt nur `border-border` und `text-text`, kein einziges `bg-*`: Der neutrale Ton ' +
      'ignoriert die Fuellung vollstaendig - deshalb gibt es auch kein `neutral-suggested`.',
  },
]

/**
 * Rollennamen aus `components.json`, die bewusst auf KEINE Penpot-Eigenschaft abbilden - je mit
 * Grund, beide Richtungen geprueft.
 *
 * Damit gibt es nur noch zwei Faelle: Eine Rolle bildet ab, oder sie steht hier. Eine dritte
 * Moeglichkeit - eine Rolle, die still im Bericht `nachzubinden` landet, obwohl sie die Flaeche
 * des Bretts selbst meint - gibt es nicht; genau das war `spur`.
 */
const ROLLEN_OHNE_EIGENSCHAFT: Record<string, string> = {
  'ueberfahren-flaeche':
    'Achsenkombination auspraegung x zustand; die Variantenmatrix kann sie nicht adressieren.',
  'ueberfahren-schrift':
    'Achsenkombination auspraegung x zustand; die Variantenmatrix kann sie nicht adressieren.',
  'gedrueckt-flaeche':
    'Achsenkombination auspraegung x zustand; die Variantenmatrix kann sie nicht adressieren.',
  'gedrueckt-schrift':
    'Achsenkombination auspraegung x zustand; die Variantenmatrix kann sie nicht adressieren.',
  fokuskontur:
    'Der Fokusring ist eine zweite Kontur um das Feld herum; der Aufbau setzt nur die eine.',
  platzhalter: 'Die Platzhalterschrift ist ein Unterelement des Eingabefelds, nicht sein Brett.',
  textmarke: 'Die Auswahlmarkierung im Eingabefeld ist kein Merkmal des Bretts.',
  marke: 'Das Haekchen des Auswahlkaestchens ist ein Unterelement, das dieser Aufbau nicht baut.',
  knauf: 'Der Knauf des Schalters ist ein Unterelement, das dieser Aufbau nicht baut.',
  fuellung: 'Der Fuellbalken der Fortschrittsanzeige ist ein Unterelement, kein Brettmerkmal.',
  symbol: 'Das Symbol im Hinweis ist eine eigene Form, die dieser Aufbau nicht anlegt.',
  beitext: 'Der Beitext des Hinweises ist eine zweite Textform neben der Beschriftung.',
  'titel-schrift': 'Die Titelzeile ist eine zweite Textform neben der einen Beschriftung.',
  'titel-typografie': 'Die Titelzeile ist eine zweite Textform neben der einen Beschriftung.',
  'beitext-typografie': 'Der Beitext ist eine zweite Textform neben der einen Beschriftung.',
  'hinweis-schrift': 'Der Bewertungshinweis der Karte ist eine zweite Textform auf der Kachel.',
  'dateiname-schrift': 'Der Dateiname der Karte ist eine zweite Textform auf der Kachel.',
  'dateiname-schriftfamilie': 'Der Dateiname der Karte ist eine zweite Textform auf der Kachel.',
  'dateiname-typografie': 'Der Dateiname der Karte ist eine zweite Textform auf der Kachel.',
  'bildflaeche-radius': 'Die Bildflaeche der Karte ist ein Unterelement, nicht das Kartenbrett.',
  aktionsabstand: 'Der Abstand der Dialog-Aktionen gilt einer Zeile im Dialog, nicht dem Brett.',
}

describe('Binden oder leeren: die Flaeche jeder Variante', () => {
  function deckung(schluessel: string, kombination: Record<string, string>) {
    return VARIANTEN_OHNE_FLAECHE.filter((eintrag) => {
      const [baustein, achse, auspraegung] = eintrag.pfad.split('.')
      return baustein === schluessel && kombination[achse!] === auspraegung
    })
  }

  /* Die Simulation ist das tragende Bauteil: ohne sie waere jede Aussage hier eine zweite getippte
     Wahrheit neben `components.json`. */
  it('liest ihre beiden Tabellen aus der Nutzlast', () => {
    const rollen = rollenTabelle()
    expect(rollen.flaeche).toEqual(['fill'])
    expect(rollen.schrift).toEqual(['fill'])
    expect(textRollenTabelle()).toContain('schrift')
    expect(alleBindungen()).toHaveLength(158)
  })

  it('zaehlt die Eigenschaften des BRETTS, nicht die vorgekommenen Rollen', () => {
    // Falle 1: `schrift` bildet ebenfalls auf `fill` ab - aufs Brett geht davon nichts.
    const probe: SimulationsBaustein = {
      schluessel: 'probe',
      varianten: { ton: ['a'] },
      tokens: { schrift: 'color.text' },
    }
    const [bindung] = bindungenVon(probe, { flaeche: ['fill'], schrift: ['fill'] }, ['schrift'])
    expect(bindung!.flaeche).toBeNull()
    expect(bindung!.schrift).toBe('color.text')
    expect(bindung!.brettEigenschaften).toEqual([])
  })

  it('sammelt ueber alle Bindungsaufrufe, nicht nur ueber den letzten', () => {
    // Falle 2: die Auspraegungs-Tabelle fuehrt NUR `schrift` - die Grundflaeche bleibt trotzdem.
    const probe: SimulationsBaustein = {
      schluessel: 'probe',
      varianten: { ton: ['a'] },
      tokens: { flaeche: 'color.surface' },
      tokensProAuspraegung: { ton: { a: { schrift: 'color.text' } } },
    }
    const [bindung] = bindungenVon(probe, { flaeche: ['fill'], schrift: ['fill'] }, ['schrift'])
    expect(bindung!.flaeche).toBe('color.surface')
    expect(bindung!.brettEigenschaften).toEqual(['fill'])
  })

  it('laesst die letzte Bindung gewinnen, in der Achsenreihenfolge der Datendatei', () => {
    const probe: SimulationsBaustein = {
      schluessel: 'probe',
      varianten: { ton: ['a'], zustand: ['x'] },
      tokens: { flaeche: 'color.bg' },
      tokensProAuspraegung: {
        ton: { a: { flaeche: 'color.surface' } },
        zustand: { x: { flaeche: 'color.overlay' } },
      },
    }
    const [bindung] = bindungenVon(probe, { flaeche: ['fill'] }, [])
    expect(bindung!.flaeche).toBe('color.overlay')
    expect(kombinationenVon({ ton: ['a', 'b'], zustand: ['x', 'y'] })).toHaveLength(4)
  })

  /* AKZEPTANZKRITERIUM 1, erste Haelfte: jede Variante ohne gebundene Flaeche ist namentlich
     gefuehrt - und von GENAU EINEM Eintrag gedeckt. */
  it('fuehrt jede ungebundene Variante namentlich und genau einmal', () => {
    const offen: string[] = []
    for (const { baustein, bindung } of alleBindungen()) {
      if (bindung.flaeche !== null) continue
      const gedeckt = deckung(baustein.schluessel, bindung.kombination)
      if (gedeckt.length !== 1) {
        offen.push(`${baustein.schluessel}: ${JSON.stringify(bindung.kombination)}`)
      }
    }
    expect(offen).toEqual([])
  })

  /* AKZEPTANZKRITERIUM 1, zweite Haelfte: 133 gebunden, 25 ausdruecklich geleert. Beide Zahlen
     entstehen aus der Simulation, nicht aus der Liste - sonst pruefte sie sich selbst. */
  it('bindet 133 Flaechen und leert 25', () => {
    const bindungen = alleBindungen()
    const gebunden = bindungen.filter(({ bindung }) => bindung.flaeche !== null)
    expect(gebunden).toHaveLength(133)
    expect(bindungen.length - gebunden.length).toBe(25)
  })

  /* Die Zahl je Eintrag: eine Teilaenderung laesst ihn schrumpfen statt verwaisen. */
  it('deckt je Eintrag genau so viele Varianten, wie er behauptet', () => {
    const gezaehlt: Record<string, number> = {}
    for (const { baustein, bindung } of alleBindungen()) {
      if (bindung.flaeche !== null) continue
      for (const eintrag of deckung(baustein.schluessel, bindung.kombination)) {
        gezaehlt[eintrag.pfad] = (gezaehlt[eintrag.pfad] ?? 0) + 1
      }
    }
    for (const eintrag of VARIANTEN_OHNE_FLAECHE) {
      expect(gezaehlt[eintrag.pfad], eintrag.pfad).toBe(eintrag.varianten)
    }
    expect(VARIANTEN_OHNE_FLAECHE.reduce((summe, e) => summe + e.varianten, 0)).toBe(25)
  })

  it('verlangt je Eintrag eine Begruendung und einen Pfad, den es gibt', () => {
    for (const eintrag of VARIANTEN_OHNE_FLAECHE) {
      expect(eintrag.grund.length, eintrag.pfad).toBeGreaterThan(40)
      const [schluessel, achse, auspraegung] = eintrag.pfad.split('.')
      const baustein = komponenten.bausteine.find((kandidat) => kandidat.schluessel === schluessel)
      expect(baustein, eintrag.pfad).toBeDefined()
      expect(baustein!.varianten[achse!], eintrag.pfad).toContain(auspraegung)
    }
  })

  /* GEGENPROBE ZUR BAUART: eine erfundene tokenlose Auspraegung wird gemeldet, eine gefuehrte
     nicht. Ohne sie bestuende die Zusicherung auch mit einem Erkenner, der nie etwas findet. */
  it('erkennt eine ungefuehrte Variante ohne Flaeche an einer synthetischen Probe', () => {
    const probe: SimulationsBaustein = {
      schluessel: 'probe',
      varianten: { ton: ['mit', 'ohne'] },
      tokensProAuspraegung: { ton: { mit: { flaeche: 'color.bg' } } },
      tokens: {},
    }
    const ohne = bindungenVon(probe, { flaeche: ['fill'] }, []).filter(
      (bindung) => bindung.flaeche === null,
    )
    expect(ohne).toHaveLength(1)
    expect(ohne[0]!.kombination).toEqual({ ton: 'ohne' })
  })
})

// ---------------------------------------------------------------------------------------------
// Die Reihenfolge des Leerens - fuenfteilig ueber den geparsten Baum
// ---------------------------------------------------------------------------------------------

/**
 * Der Befund ueber `baueVariante`: WO und UNTER WELCHER BEDINGUNG das Brett geleert wird.
 *
 * ⚠ EIN OFFSET-VERGLEICH ALLEIN BELEGT DIE REIHENFOLGE NICHT. Steht `brett.fills = []` textlich
 * hinter dem letzten `bindeRollen`-Aufruf, aber INNERHALB der Achsenschleife, ist der Offset
 * groesser und die Ausfuehrung trotzdem falsch - es traefe `button/ghost/disabled`, dessen Flaeche
 * erst in der letzten Iteration kommt. Deshalb die Pruefung auf Verschachtelungstiefe.
 *
 * Der AKKUMULATOR wird nicht namentlich erwartet, sondern abgeleitet: Bezeichner, die den
 * Rueckgabewert von `bindeRollen` aufnehmen. Ein getippter Name waere eine zweite Wahrheit.
 */
interface LeerungsBefund {
  fillsZuweisungen: number
  zuweisungen: number
  hinterLetzterBindung: boolean
  ausserhalbSchleife: boolean
  inBedingungMitAkkumulator: boolean
  blankeBindungsaufrufe: number
}

const SCHLEIFENKNOTEN = [
  'ForStatement',
  'ForOfStatement',
  'ForInStatement',
  'WhileStatement',
  'DoWhileStatement',
]

export function leerungsBefund(quelltext: string): LeerungsBefund {
  const funktion = knoten(
    quelltext,
    (eintrag) =>
      eintrag.type === 'FunctionDeclaration' &&
      (eintrag.id as Record<string, unknown> | null)?.name === 'baueVariante',
  )[0]
  if (funktion === undefined) {
    throw new Error('baueVariante nicht gefunden.')
  }
  const von = funktion.start as number
  const bis = funktion.end as number
  const innen = (eintrag: Record<string, unknown>): boolean =>
    (eintrag.start as number) >= von && (eintrag.end as number) <= bis

  const bindungen = knoten(
    quelltext,
    (eintrag) =>
      eintrag.type === 'CallExpression' &&
      (eintrag.callee as Record<string, unknown> | null)?.name === 'bindeRollen' &&
      innen(eintrag),
  )
  const letzteBindung = bindungen.reduce(
    (groesster, eintrag) => Math.max(groesster, eintrag.start as number),
    -1,
  )

  const akkumulatoren = new Set<string>()
  for (const eintrag of knoten(
    quelltext,
    (kandidat) =>
      innen(kandidat) &&
      (kandidat.type === 'VariableDeclarator' || kandidat.type === 'AssignmentExpression'),
  )) {
    const ziel = (eintrag.type === 'VariableDeclarator' ? eintrag.id : eintrag.left) as Record<
      string,
      unknown
    > | null
    const wert = eintrag.type === 'VariableDeclarator' ? eintrag.init : eintrag.right
    if (
      ziel?.type === 'Identifier' &&
      typeof ziel.name === 'string' &&
      enthaeltBezeichner(wert, 'bindeRollen')
    ) {
      akkumulatoren.add(ziel.name)
    }
  }

  const fillsZuweisungen = knoten(
    quelltext,
    (eintrag) =>
      eintrag.type === 'AssignmentExpression' &&
      innen(eintrag) &&
      ((eintrag.left as Record<string, unknown> | null)?.property as Record<string, unknown> | null)
        ?.name === 'fills',
  )
  const treffer = fillsZuweisungen.filter((eintrag) => {
    const links = eintrag.left as Record<string, unknown>
    const objekt = links.object as Record<string, unknown> | null
    const wert = eintrag.right as Record<string, unknown> | null
    return (
      objekt?.type === 'Identifier' &&
      objekt.name === 'brett' &&
      wert?.type === 'ArrayExpression' &&
      ((wert.elements as unknown[]) ?? []).length === 0
    )
  })
  const stelle = treffer.length === 1 ? (treffer[0]!.start as number) : undefined

  const umschliessend = (typen: string[]): Record<string, unknown>[] =>
    stelle === undefined
      ? []
      : knoten(
          quelltext,
          (eintrag) =>
            typen.includes(eintrag.type as string) &&
            innen(eintrag) &&
            (eintrag.start as number) < stelle &&
            (eintrag.end as number) > stelle,
        )

  return {
    fillsZuweisungen: fillsZuweisungen.length,
    zuweisungen: treffer.length,
    hinterLetzterBindung: stelle !== undefined && stelle > letzteBindung && letzteBindung >= 0,
    ausserhalbSchleife: stelle !== undefined && umschliessend(SCHLEIFENKNOTEN).length === 0,
    inBedingungMitAkkumulator: umschliessend(['IfStatement']).some((eintrag) =>
      [...akkumulatoren].some((name) => enthaeltBezeichner(eintrag.test, name)),
    ),
    blankeBindungsaufrufe: knoten(
      quelltext,
      (eintrag) =>
        eintrag.type === 'ExpressionStatement' &&
        innen(eintrag) &&
        (eintrag.expression as Record<string, unknown> | null)?.type === 'CallExpression' &&
        ((eintrag.expression as Record<string, unknown>).callee as Record<string, unknown> | null)
          ?.name === 'bindeRollen',
    ).length,
  }
}

describe('Geleert wird nach dem Binden, genau einmal und nur bedingt', () => {
  const befund = () => leerungsBefund(dateiVon('seed-components.js').roh)

  it('leert genau einmal, auf dem Brett, mit leerem Array-Literal', () => {
    expect(befund().fillsZuweisungen).toBe(1)
    expect(befund().zuweisungen).toBe(1)
  })

  it('leert hinter dem letzten Bindungsaufruf', () => {
    expect(befund().hinterLetzterBindung).toBe(true)
  })

  it('leert ausserhalb jeder Schleife', () => {
    expect(befund().ausserhalbSchleife).toBe(true)
  })

  it('leert nur, wenn der Akkumulator es sagt', () => {
    expect(befund().inBedingungMitAkkumulator).toBe(true)
  })

  /* Ein Aufruf als blankes `ExpressionStatement` wirft seinen Rueckgabewert weg - der Akkumulator
     verloere genau die Bindungen dieses Aufrufs, und 16 heute korrekte Varianten wuerden geleert. */
  it('wirft den Rueckgabewert keines Bindungsaufrufs weg', () => {
    expect(befund().blankeBindungsaufrufe).toBe(0)
  })

  /*
   * VIER SYNTHETISCHE GEGENPROBEN. Ohne sie ist der Block darueber eine Beruhigung: Ein Befund,
   * der auch bei falscher Reihenfolge gruen bliebe, sichert nichts zu.
   */
  const probe = (rumpf: string) => `function baueVariante(a, b) {\n${rumpf}\n}`

  it('meldet eine Leerung VOR dem letzten Bindungsaufruf', () => {
    const gegenprobe = leerungsBefund(
      probe(
        [
          "  let gesetzt = bindeRollen(brett, text, a, 'h', [])",
          "  if (gesetzt.indexOf('fill') === -1) { brett.fills = [] }",
          "  gesetzt = gesetzt.concat(bindeRollen(brett, text, b, 'h', []))",
        ].join('\n'),
      ),
    )
    expect(gegenprobe.zuweisungen).toBe(1)
    expect(gegenprobe.hinterLetzterBindung).toBe(false)
  })

  it('meldet eine Leerung INNERHALB der Achsenschleife, trotz groesserem Offset', () => {
    const gegenprobe = leerungsBefund(
      probe(
        [
          "  let gesetzt = bindeRollen(brett, text, a, 'h', [])",
          '  for (const achse of achsen) {',
          "    gesetzt = gesetzt.concat(bindeRollen(brett, text, b, 'h', []))",
          "    if (gesetzt.indexOf('fill') === -1) { brett.fills = [] }",
          '  }',
        ].join('\n'),
      ),
    )
    // Der Offset-Vergleich allein bliebe hier gruen - genau das ist der Punkt.
    expect(gegenprobe.hinterLetzterBindung).toBe(true)
    expect(gegenprobe.ausserhalbSchleife).toBe(false)
  })

  it('meldet eine UNBEDINGTE Leerung', () => {
    const gegenprobe = leerungsBefund(
      probe(
        ["  let gesetzt = bindeRollen(brett, text, a, 'h', [])", '  brett.fills = []'].join('\n'),
      ),
    )
    expect(gegenprobe.zuweisungen).toBe(1)
    expect(gegenprobe.inBedingungMitAkkumulator).toBe(false)
  })

  it('meldet eine Leerung am FALSCHEN Ziel', () => {
    const gegenprobe = leerungsBefund(
      probe(
        [
          "  let gesetzt = bindeRollen(brett, text, a, 'h', [])",
          "  if (gesetzt.indexOf('fill') === -1) { beschriftung.fills = [] }",
        ].join('\n'),
      ),
    )
    expect(gegenprobe.fillsZuweisungen).toBe(1)
    expect(gegenprobe.zuweisungen).toBe(0)
  })

  it('meldet einen weggeworfenen Rueckgabewert', () => {
    expect(
      leerungsBefund(probe("  bindeRollen(brett, text, a, 'h', [])")).blankeBindungsaufrufe,
    ).toBe(1)
  })

  /* Und die Bedingung haengt am ABGELEITETEN Akkumulator, nicht an einem beliebigen Bezeichner. */
  it('erkennt eine Bedingung ohne den Akkumulator nicht als Bedingung', () => {
    const gegenprobe = leerungsBefund(
      probe(
        [
          "  let gesetzt = bindeRollen(brett, text, a, 'h', [])",
          '  if (baustein.schluessel) { brett.fills = [] }',
        ].join('\n'),
      ),
    )
    expect(gegenprobe.inBedingungMitAkkumulator).toBe(false)
  })
})

describe('Das Rollenvokabular bildet ab oder ist gefuehrt', () => {
  const rollenIn = (): string[] => [
    ...new Set(tokenSlots().map((slot) => slot.pfad.split('.').slice(-1)[0]!)),
  ]

  it('bildet jede Rolle aus components.json ab oder fuehrt sie namentlich', () => {
    const abbildend = rollenTabelle()
    const ungefuehrt = rollenIn().filter(
      (rolle) =>
        eigenerWert(abbildend, rolle) === undefined &&
        eigenerWert(ROLLEN_OHNE_EIGENSCHAFT, rolle) === undefined,
    )
    expect(ungefuehrt).toEqual([])
  })

  /* GEGENRICHTUNG: ein stehengebliebener Eintrag wird verwaist und rot - genau daran faellt
     `spur` auf, sobald die Rolle ihren Platz gewechselt hat. */
  it('fuehrt keinen verwaisten und keinen doppelt gefuehrten Eintrag', () => {
    const vorhanden = new Set(rollenIn())
    const abbildend = rollenTabelle()
    for (const [rolle, grund] of Object.entries(ROLLEN_OHNE_EIGENSCHAFT)) {
      expect(vorhanden.has(rolle), rolle).toBe(true)
      expect(eigenerWert(abbildend, rolle), rolle).toBeUndefined()
      expect(grund.length, rolle).toBeGreaterThan(40)
    }
  })

  it('sieht im Bestand ueberhaupt Rollen', () => {
    expect(rollenIn().length).toBeGreaterThanOrEqual(20)
  })
})

// ---------------------------------------------------------------------------------------------
// Verdrahtung des TS-Projekts
// ---------------------------------------------------------------------------------------------

describe('Verdrahtung des TS-Projekts', () => {
  // Die tsconfig-Dateien sind JSONC; die Kommentarstreichung von oben macht sie lesbar, ohne dass
  // dafuer ein Parser dazukaeme.
  const tsconfig = JSON.parse(
    streicheKommentare(readFileSync(`${FRONTEND_DIR}tsconfig.json`, 'utf8')),
  ) as { references: { path: string }[] }
  const penpotConfig = JSON.parse(
    streicheKommentare(readFileSync(`${FRONTEND_DIR}tsconfig.penpot.json`, 'utf8')),
  ) as { include: string[] }

  /* OHNE DIESE ZUSICHERUNG ist der stille Fehlermodus, dass `frontend/penpot/**` von `tsc -b` GAR
     NICHT geprueft wird - gruene CI ohne Typpruefung. */
  it('referenziert tsconfig.penpot.json aus tsconfig.json', () => {
    expect(tsconfig.references.map((referenz) => referenz.path)).toContain('./tsconfig.penpot.json')
  })

  it('nennt im include jede Erzeuger- und Testdatei unter penpot/', () => {
    expect(penpotConfig.include.sort()).toEqual(
      [
        'penpot/icons.test.ts',
        'penpot/icons.ts',
        'penpot/payload.test.ts',
        'penpot/tokens.test.ts',
        'penpot/tokens.ts',
      ].sort(),
    )
  })
})

// ---------------------------------------------------------------------------------------------
// Was die Nutzlast darf - die abschliessende Liste aus ADR 0066 Abschnitt 5 Punkt 6
// ---------------------------------------------------------------------------------------------

/** Verbotene Bezeichner. `execute_code` laeuft in einer angemeldeten Sitzung ohne Sandbox; der
 * Blast-Radius ist nicht die eine Design-Datei, sondern alles, was diese Sitzung erreicht. */
const VERBOTENE_BEZEICHNER: { name: string; muster: RegExp; probe: string }[] = [
  { name: 'fetch', muster: /\bfetch\s*\(/, probe: 'fetch("x")' },
  { name: 'XMLHttpRequest', muster: /\bXMLHttpRequest\b/, probe: 'new XMLHttpRequest()' },
  { name: 'WebSocket', muster: /\bWebSocket\b/, probe: 'new WebSocket("x")' },
  { name: 'sendBeacon', muster: /\bsendBeacon\s*\(/, probe: 'navigator.sendBeacon("x")' },
  { name: 'dynamisches import()', muster: /\bimport\s*\(/, probe: 'import("x")' },
  { name: 'eval', muster: /\beval\s*\(/, probe: 'eval("x")' },
  { name: 'new Function', muster: /\bnew\s+Function\b/, probe: 'new Function("x")' },
  { name: 'setTimeout', muster: /\bsetTimeout\s*\(/, probe: 'setTimeout("x", 1)' },
  { name: 'setInterval', muster: /\bsetInterval\s*\(/, probe: 'setInterval("x", 1)' },
  { name: 'innerHTML', muster: /\binnerHTML\b/, probe: 'el.innerHTML = "x"' },
  { name: 'document', muster: /\bdocument\b/, probe: 'document.write("x")' },
  { name: 'window', muster: /\bwindow\b/, probe: 'window.location = "x"' },
  { name: 'localStorage', muster: /\blocalStorage\b/, probe: 'localStorage.getItem("x")' },
  { name: 'storage', muster: /\bstorage\b/, probe: 'storage.setItem("x", 1)' },
  // "Kein Skript loescht je etwas" (ADR 0066 Abschnitt 4). Statisch als Abwesenheit gefuehrt,
  // weil kein Aufbauskript einen Loeschgrund hat - die konservative Richtung ist jederzeit
  // verschaerfbar, die Gegenrichtung nicht.
  { name: 'remove', muster: /\.remove\s*\(/, probe: 'shape.remove()' },
  { name: 'delete', muster: /\bdelete\s+/, probe: 'delete obj.x' },
]

/**
 * Fundstellengenaue Freigaben zur Liste oben - und zwar genau eine. `createShapeFromSvg` haengt
 * von sich aus ein Kind `base-background` an (an einer verbundenen Instanz gemessen); es zu
 * entfernen ist von der abschliessenden Liste GEDECKT, weil das Rechteck im selben Lauf vom
 * Skript selbst entstanden ist. Die Freigabe ist an Datei, Zeile und Ausschnitt gebunden, damit
 * sie nicht zur Generalerlaubnis fuer `remove` in dieser Datei wird.
 */
const BEZEICHNER_FREIGABEN: {
  datei: string
  zeile: number
  bezeichner: string
  ausschnitt: string
}[] = [{ datei: 'seed-icons.js', zeile: 106, bezeichner: 'remove', ausschnitt: 'kind.remove()' }]

describe('Was die Nutzlast darf, ist abschliessend', () => {
  function verstoesse(verboten: (typeof VERBOTENE_BEZEICHNER)[number]): Fund[] {
    const funde = suche(nutzlast, new RegExp(verboten.muster.source, `${verboten.muster.flags}g`))
    return funde.filter(
      (fund) =>
        !BEZEICHNER_FREIGABEN.some(
          (freigabe) =>
            freigabe.bezeichner === verboten.name &&
            freigabe.datei === fund.datei &&
            freigabe.zeile === fund.zeile &&
            fund.text.includes(freigabe.ausschnitt),
        ),
    )
  }

  for (const verboten of VERBOTENE_BEZEICHNER) {
    it(`enthaelt kein ${verboten.name}`, () => {
      expect(meldung(verstoesse(verboten))).toBe('')
    })
  }

  it('fuehrt keine verwaiste Bezeichner-Freigabe', () => {
    for (const freigabe of BEZEICHNER_FREIGABEN) {
      const verboten = VERBOTENE_BEZEICHNER.find(
        (kandidat) => kandidat.name === freigabe.bezeichner,
      )
      expect(verboten, freigabe.bezeichner).toBeDefined()
      const alle = suche(
        nutzlast,
        new RegExp(verboten!.muster.source, `${verboten!.muster.flags}g`),
      )
      expect(
        alle.some(
          (fund) =>
            fund.datei === freigabe.datei &&
            fund.zeile === freigabe.zeile &&
            fund.text.includes(freigabe.ausschnitt),
        ),
        `${freigabe.datei}:${freigabe.zeile}`,
      ).toBe(true)
    }
  })

  /* Selbsttest je Muster: ein Verbot, das seinen eigenen Verstoss nicht erkennt, ist eine
     Beruhigung, keine Zusicherung. */
  it('erkennt jeden verbotenen Bezeichner an einer synthetischen Probe', () => {
    for (const verboten of VERBOTENE_BEZEICHNER) {
      expect(verboten.muster.test(verboten.probe), verboten.name).toBe(true)
    }
  })
})
