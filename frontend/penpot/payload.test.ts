// @vitest-environment node
/*
 * Statische Regeln ueber die HANDGESCHRIEBENE Penpot-Nutzlast (specs/features/0352-penpot-als-
 * alleinige-design-quelle.md, Teststrategie Ebene 2; decisions/0065-penpot-stand-als-erzeugte-
 * idempotente-nutzlast.md Abschnitt 5 Punkt 6).
 *
 * WARUM DIESE EBENE EXISTIERT: `execute_code` fuehrt den Text der Aufbauskripte im Plugin-Kontext
 * einer ANGEMELDETEN Penpot-Sitzung aus, ohne Sandbox. CI kann die Skripte nicht ausfuehren - das
 * Review ist das einzige Gate zwischen einer Zeile im Repository und ihrer Ausfuehrung. Was
 * statisch pruefbar ist, wird deshalb hier geprueft.
 *
 * SUCHRAUM sind die fuenf handgeschriebenen Dateien unter `design/penpot/`. Ausdruecklich NICHT
 * `tokens.json`/`icons.json`: sie sind erzeugt, sie MUESSEN Werte tragen, und genau deshalb sind
 * sie die Gegenprobe. `README.md` ist Prosa und bleibt aussen vor.
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

/** Die fuenf handgeschriebenen Dateien - NAMENTLICH behauptet, nicht "mindestens fuenf Dateien
 * im Verzeichnis". Eine Verzeichnisaufzaehlung waere von einem kaputten Glob nicht zu
 * unterscheiden. */
const NUTZLAST_DATEIEN = [
  'seed-tokens.js',
  'seed-icons.js',
  'seed-components.js',
  'verify.js',
  'components.json',
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
const TOKEN_GRUPPEN = [
  'color',
  'radius',
  'space',
  'font-size',
  'line-height',
  'font-weight',
  'letter-spacing',
  'font-family',
] as const

const TOKENNAME_MUSTER = new RegExp(`\\b(?:${TOKEN_GRUPPEN.join('|')})\\.[a-z0-9-]+`, 'g')

/**
 * Maskiert Tokennamen-Literale zeichen- und zeilentreu. OHNE DIESEN SCHRITT IST DIE REGEL EINE
 * FEHLALARM-MASCHINE: `space.3`, `space.16` und `font-size.2xl` schluegen als blanke Zahlen an,
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
  return funde.map((fund) => `${fund.datei}:${fund.zeile}: ${fund.treffer} | ${fund.text.trim()}`).join('\n')
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
    expect(maskiereTokennamen('"font-size.2xl"')).not.toContain('2')
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
  it('umfasst genau die fuenf namentlich behaupteten Dateien', () => {
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
  }

  /* Mindestzahl gescannter Zeilen NACH der Vorbehandlung. Ohne sie ist ein kaputter
     Vorbehandlungsschritt (der alles wegstreicht) von einem sauberen Bestand nicht zu
     unterscheiden: beide melden null Funde. Gemessen 707, eingefroren auf 600. */
  const MINDESTZEILEN = 600

  it('hat je Datei ueberhaupt Inhalt', () => {
    for (const datei of nutzlast) {
      expect(datei.roh.length, datei.datei).toBeGreaterThanOrEqual(MINDESTZEICHEN[datei.datei])
    }
  })

  it('scannt nach der Vorbehandlung noch genug Zeilen', () => {
    const zeilen = nutzlast.reduce(
      (summe, datei) => summe + datei.inhalt.split('\n').filter((zeile) => zeile.trim().length > 0).length,
      0
    )
    expect(zeilen).toBeGreaterThanOrEqual(MINDESTZEILEN)
  })
})

// ---------------------------------------------------------------------------------------------
// Die tragende Zusicherung: kein woertlicher Farb-/Groessenwert
// ---------------------------------------------------------------------------------------------

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

  /*
   * FUNDSTELLENGENAUE FREIGABELISTE, bewusst NICHT dateiweise: `verify.js` braucht legitim vier
   * Kardinalitaeten, und eine dateiweise Freigabe waere ein stiller Selbstausschalter - ab dann
   * duerfte dort jeder Farbwert stehen. Eine Freigabe nennt Datei, Zeile, Wert und einen
   * AUSSCHNITT der Zeile; verschiebt sich die Fundstelle, faellt die Freigabe.
   */
  const FREIGABEN: { datei: string; zeile: number; wert: string; ausschnitt: string }[] = [
    { datei: 'verify.js', zeile: 40, wert: '12', ausschnitt: 'ERWARTETE_SYMBOLE = 12' },
    { datei: 'verify.js', zeile: 41, wert: '10', ausschnitt: 'ERWARTETE_BAUSTEINE = 10' },
    { datei: 'verify.js', zeile: 42, wert: '13', ausschnitt: 'ERWARTETE_KATEGORIEN = 13' },
    { datei: 'verify.js', zeile: 43, wert: '64', ausschnitt: 'ERWARTETE_FARBEN = 64' },
  ]

  function freigabeFuer(fund: Fund): (typeof FREIGABEN)[number] | undefined {
    return FREIGABEN.find(
      (freigabe) =>
        freigabe.datei === fund.datei &&
        freigabe.zeile === fund.zeile &&
        freigabe.wert === fund.treffer &&
        fund.text.includes(freigabe.ausschnitt)
    )
  }

  const blankeZahlen = suche(nutzlast, MUSTER_BLANKE_ZAHL).filter(
    (fund) => !UNVERDAECHTIGE_ZAHLEN.has(fund.treffer)
  )

  it('enthaelt keine unfreigegebene blanke Zahl', () => {
    const offen = blankeZahlen.filter((fund) => freigabeFuer(fund) === undefined)
    expect(meldung(offen)).toBe('')
  })

  /* Verwaiste Freigaben sind der stille Verfall dieser Liste: eine Zeile, die nichts mehr
     freigibt, ist eine Erlaubnis auf Vorrat. */
  it('fuehrt keine verwaiste Freigabe', () => {
    const verwaist = FREIGABEN.filter(
      (freigabe) => !blankeZahlen.some((fund) => freigabeFuer(fund) === freigabe)
    )
    expect(verwaist).toEqual([])
  })

  /* Ein Ausschnitt, der nur aus dem Suchbegriff besteht, gaebe die Zahl ueberall in der Zeile
     frei und waere damit keine Fundstellenangabe mehr. */
  it('verlangt einen aussagekraeftigen Ausschnitt je Freigabe', () => {
    for (const freigabe of FREIGABEN) {
      expect(freigabe.ausschnitt.length, freigabe.ausschnitt).toBeGreaterThanOrEqual(6)
      expect(freigabe.ausschnitt.replace(/[0-9]/g, '').trim().length, freigabe.ausschnitt).toBeGreaterThan(0)
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
      (fund) => !UNVERDAECHTIGE_ZAHLEN.has(fund.treffer)
    )
    expect(funde.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------------------------
// Struktur der Nutzlast
// ---------------------------------------------------------------------------------------------

const tokens = JSON.parse(readFileSync(`${DESIGN_DIR}tokens.json`, 'utf8')) as {
  name: string
  type: string
  value: string
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

function alleTokennamenAus(text: string): string[] {
  return [...text.matchAll(TOKENNAME_MUSTER)].map((treffer) => treffer[0])
}

describe('Referentielle Integritaet', () => {
  it('nennt in components.json und seed-components.js nur Tokens, die es gibt', () => {
    const genannt = [
      ...alleTokennamenAus(dateiVon('components.json').roh),
      ...alleTokennamenAus(streicheKommentare(dateiVon('seed-components.js').roh)),
    ]
    expect(genannt.length).toBeGreaterThan(0)
    const unbekannt = [...new Set(genannt)].filter((name) => !tokennamen.has(name))
    expect(unbekannt).toEqual([])
  })

  /*
   * DIE GEGENRICHTUNG WIRD NICHT GEPRUEFT: sie zwaenge zum Ausduennen eines bewusst vollstaendigen
   * Tokensatzes. An ihre Stelle tritt eine GRUPPEN-Zusicherung, und zwar als EINGEFRORENE
   * Zuordnung statt als "mindestens eine": `font-weight` und `letter-spacing` werden von keinem
   * der zehn Bausteine getragen, und das ist kein Versehen -
   *   - die Schnitt-Tokens sind die Standardschnitte der Typo-STUFEN (400/500/400/600/700). Die
   *     zehn Bausteine uebersteuern den Schnitt an der Aufrufstelle (`font-semibold`,
   *     `font-bold`); eine Bindung an `font-weight.2xl` waere zwar wertgleich, behauptete aber
   *     eine Kopplung an die 40px-Stufe, die es nicht gibt.
   *   - `letter-spacing.3xl` haengt an der 64px-Anzeigestufe. Keiner der zehn Bausteine ist eine
   *     Anzeigeueberschrift.
   * Eine eingefrorene Zuordnung macht diese beiden Luecken sichtbar, statt sie hinter einem
   * "mindestens eine Gruppe" verschwinden zu lassen.
   */
  it('haelt die eingefrorene Zuordnung Gruppe -> Verwendung ein', () => {
    const verwendet = new Set(
      alleTokennamenAus(dateiVon('components.json').roh).map((name) => name.split('.')[0])
    )
    expect([...verwendet].sort()).toEqual(
      ['color', 'font-family', 'font-size', 'line-height', 'radius', 'space'].sort()
    )
    for (const gruppe of ['font-weight', 'letter-spacing']) {
      expect(verwendet.has(gruppe), gruppe).toBe(false)
    }
  })

  it('haelt die Namensform aller genannten Tokens ein', () => {
    const form = new RegExp(`^(?:${TOKEN_GRUPPEN.join('|')})\\.[a-z0-9-]+$`)
    for (const name of alleTokennamenAus(dateiVon('components.json').roh)) {
      expect(form.test(name), name).toBe(true)
    }
  })
})

describe('Die zehn Bausteine', () => {
  /* GESCHLOSSENE NAMENSMENGE, nicht Kardinalitaet: "genau zehn" bestuenden auch zehn beliebige. */
  it('traegt genau die zehn maschinellen Schluessel', () => {
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
      'chip',
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
      'Kategorie-Chip',
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

  /* Die Zuordnungstabelle spannt ZWEI Verzeichnisse: neun der zehn liegen unter
     `src/components/ui/`, der Kategorie-Chip als `src/components/CategoryBadge.tsx`. Wer nur `ui/`
     aufzaehlt, verliert den zehnten still. */
  it('spannt beide Verzeichnisse auf', () => {
    const quellen = komponenten.bausteine.flatMap((baustein) => baustein.quellen)
    expect(quellen).toContain('src/components/CategoryBadge.tsx')
    expect(quellen.filter((quelle) => quelle.startsWith('src/components/ui/')).length).toBeGreaterThan(0)
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
    if (variante.test(ohneKommentare) || (eingebettet !== null && eingebettet.test(ohneKommentare))) {
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
          expect(gefuehrt.has(zustand), `${baustein.schluessel} <- ${quelle}: ${zustand}`).toBe(true)
        }
      }
    }
  })

  /* UNTERGRENZE FUER DAS, WAS DER TEST GESEHEN HAT. Ohne sie waere ein kaputter Scanner von einem
     sauberen Bestand nicht zu unterscheiden: "kein Zustand gefunden" bestuende immer. */
  it('hat im Bestand ueberhaupt Zustaende gesehen', () => {
    const gesehen = komponenten.bausteine.flatMap((baustein) =>
      baustein.quellen.flatMap((quelle) => zustaendeIn(readFileSync(`${FRONTEND_DIR}${quelle}`, 'utf8')))
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
    expect(LAUFREGEL_ZEILE.test(' * frueher galt hier LAUFREGEL: jederzeit-wiederholbar')).toBe(false)
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
  'applyToken',
  'applyToShapes',
  'createComponent',
  'createVariantContainer',
  'createBoard',
  'createRectangle',
  'createText',
  'createEllipse',
  'appendChild',
  'switchVariant',
  'instance',
]

interface Aufruf {
  name: string
  start: number
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
      gefunden.push({ name, start: eintrag.start as number })
    }
    for (const wert of Object.values(eintrag)) gehe(wert)
  }
  gehe(parseAst(quelltext))
  return gefunden.sort((a, b) => a.start - b.start)
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
    // Eine Vorbedingung, die nur meldet statt abzubrechen, ist keine. Nach ADR 0064 ist der
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
// Verdrahtung des TS-Projekts
// ---------------------------------------------------------------------------------------------

describe('Verdrahtung des TS-Projekts', () => {
  // Die tsconfig-Dateien sind JSONC; die Kommentarstreichung von oben macht sie lesbar, ohne dass
  // dafuer ein Parser dazukaeme.
  const tsconfig = JSON.parse(
    streicheKommentare(readFileSync(`${FRONTEND_DIR}tsconfig.json`, 'utf8'))
  ) as { references: { path: string }[] }
  const penpotConfig = JSON.parse(
    streicheKommentare(readFileSync(`${FRONTEND_DIR}tsconfig.penpot.json`, 'utf8'))
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
      ].sort()
    )
  })
})

// ---------------------------------------------------------------------------------------------
// Was die Nutzlast darf - die abschliessende Liste aus ADR 0065 Abschnitt 5 Punkt 6
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
  // "Kein Skript loescht je etwas" (ADR 0065 Abschnitt 4). Statisch als Abwesenheit gefuehrt,
  // weil kein Aufbauskript einen Loeschgrund hat - die konservative Richtung ist jederzeit
  // verschaerfbar, die Gegenrichtung nicht.
  { name: 'remove', muster: /\.remove\s*\(/, probe: 'shape.remove()' },
  { name: 'delete', muster: /\bdelete\s+/, probe: 'delete obj.x' },
]

describe('Was die Nutzlast darf, ist abschliessend', () => {
  for (const verboten of VERBOTENE_BEZEICHNER) {
    it(`enthaelt kein ${verboten.name}`, () => {
      for (const datei of nutzlast) {
        expect(verboten.muster.test(datei.inhalt), `${datei.datei}: ${verboten.name}`).toBe(false)
      }
    })
  }

  /* Selbsttest je Muster: ein Verbot, das seinen eigenen Verstoss nicht erkennt, ist eine
     Beruhigung, keine Zusicherung. */
  it('erkennt jeden verbotenen Bezeichner an einer synthetischen Probe', () => {
    for (const verboten of VERBOTENE_BEZEICHNER) {
      expect(verboten.muster.test(verboten.probe), verboten.name).toBe(true)
    }
  })
})
