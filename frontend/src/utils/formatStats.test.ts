import { describe, expect, it } from 'vitest'

import {
  criterionPercentValue,
  formatBytes,
  formatCount,
  formatCriterionPercent,
  formatDate,
  formatDateTime,
  formatTakenAtRange,
  formatUsd,
  NOT_AVAILABLE,
} from './formatStats'

// specs/features/0207-projekt-statistikseite.md, Akzeptanzkriterien S1/K1/K4: reine
// Formatierungsfunktionen mit deutschem Zahlenformat. Sie tragen die Aussagen, an denen die
// Statistikseite fachlich haengt - insbesondere "ein tatsaechlich angefallener Betrag darf nie
// als 'nichts ausgegeben' erscheinen".

describe('formatBytes', () => {
  it('stellt 0 als "0 MB" dar, nicht als Strich', () => {
    expect(formatBytes(0)).toBe('0 MB')
  })

  it('stellt einen nicht ermittelbaren Wert als Strich dar', () => {
    expect(formatBytes(null)).toBe('—')
  })

  it('rechnet unterhalb von 1 GB in MB mit einer Nachkommastelle', () => {
    expect(formatBytes(1024 * 1024)).toBe('1,0 MB')
    expect(formatBytes(Math.round(2.5 * 1024 * 1024))).toBe('2,5 MB')
  })

  it('rechnet ab genau 1 GB in GB', () => {
    expect(formatBytes(1024 ** 3)).toBe('1,0 GB')
    expect(formatBytes(Math.round(2.3 * 1024 ** 3))).toBe('2,3 GB')
  })

  it('bleibt ein Byte unterhalb der Grenze noch bei MB', () => {
    expect(formatBytes(1024 ** 3 - 1)).toBe('1.024,0 MB')
  })

  it('nutzt das deutsche Dezimalkomma und den deutschen Tausenderpunkt', () => {
    expect(formatBytes(Math.round(1234.5 * 1024 ** 3))).toBe('1.234,5 GB')
  })

  it('stellt einen sehr kleinen, aber vorhandenen Wert als 0,0 MB dar, nicht als 0 MB', () => {
    // Bewusst unterschieden von der exakten Null oben: dort steht "0 MB" (nichts belegt), hier
    // ist etwas da, das nur unterhalb der angezeigten Genauigkeit liegt.
    expect(formatBytes(500)).toBe('0,0 MB')
  })
})

describe('formatUsd', () => {
  it('stellt 0 mit zwei Nachkommastellen und Waehrung dar', () => {
    expect(formatUsd(0)).toBe('0,00 USD')
  })

  it('stellt einen regulaeren Betrag mit zwei Nachkommastellen dar', () => {
    expect(formatUsd(12.1)).toBe('12,10 USD')
  })

  it('nutzt den deutschen Tausenderpunkt', () => {
    expect(formatUsd(1234.5)).toBe('1.234,50 USD')
  })

  it('rundet kaufmaennisch auf zwei Nachkommastellen', () => {
    expect(formatUsd(0.015)).toBe('0,02 USD')
  })

  it('zeigt einen Betrag unterhalb eines Cents als "< 0,01 USD"', () => {
    // Akzeptanzkriterium K4: auf einer Seite zur Kostenkontrolle darf ein tatsaechlich
    // angefallener Betrag nicht als "nichts ausgegeben" erscheinen.
    expect(formatUsd(0.004)).toBe('< 0,01 USD')
    expect(formatUsd(0.0000001)).toBe('< 0,01 USD')
  })

  it('zeigt genau an der Rundungsgrenze bereits einen Cent', () => {
    expect(formatUsd(0.005)).toBe('0,01 USD')
  })
})

describe('formatCount', () => {
  it('setzt den deutschen Tausenderpunkt', () => {
    expect(formatCount(12043)).toBe('12.043')
    expect(formatCount(0)).toBe('0')
  })
})

describe('formatDate / formatDateTime', () => {
  it('stellt ein Datum zweistellig im deutschen Format dar', () => {
    expect(formatDate('2019-04-02T10:12:00')).toBe('02.04.2019')
  })

  it('ergaenzt beim Lauf-Zeitpunkt die Uhrzeit', () => {
    expect(formatDateTime('2026-08-01T09:05:00')).toMatch(/^01\.08\.2026, 09:05$/)
  })
})

/*
 * specs/features/0375-projektuebersicht-umfang-und-naechster-schritt.md, Akzeptanzkriterium A3:
 * vier entscheidbare Faelle. Die Testdaten tragen bewusst KEIN Zonenkennzeichen und liegen fern
 * von Mitternacht - der Testlauf pinnt keine Zeitzone, und ein Zeitstempel dicht an 00:00 fiele je
 * nach Maschine auf einen anderen Kalendertag.
 */
describe('formatTakenAtRange', () => {
  it('stellt eine Spanne mit Gedankenstrich und je einem Leerzeichen dar', () => {
    expect(formatTakenAtRange('2019-04-02T10:12:00', '2019-08-17T14:30:00')).toBe(
      '02.04.2019 – 17.08.2019',
    )
  })

  it('nennt denselben Kalendertag genau einmal, auch bei verschiedenen Uhrzeiten', () => {
    // Entschieden am FORMATIERTEN Datum, nicht am rohen Zeitstempel: zwei Aufnahmen desselben
    // Tages sind nie zeitstempelgleich, und "02.04.2019 – 02.04.2019" liest sich als Fehler.
    expect(formatTakenAtRange('2019-04-02T09:15:00', '2019-04-02T18:44:00')).toBe('02.04.2019')
  })

  it.each([
    ['nur das fruehere fehlt', null, '2019-08-17T14:30:00'],
    ['nur das spaetere fehlt', '2019-04-02T10:12:00', null],
    ['beide fehlen', null, null],
  ])('zeigt den Strich, wenn %s', (_name, earliest, latest) => {
    // Der Strich heisst "keine Angabe" und ist ausdruecklich nicht dasselbe wie eine Null.
    expect(formatTakenAtRange(earliest, latest)).toBe(NOT_AVAILABLE)
  })
})

// specs/features/0299-kategorie-konfidenz-anzeigen.md, Umsetzungsschritt 10: `formatCriterionPercent`
// ist von `components/CriterionDetailsList.tsx` hierher gewandert und wird jetzt von der
// Kandidatenliste UND dem Statistikblock geteilt - eine zweite Formatierungslogik entstuende
// sonst zwangslaeufig.
describe('formatCriterionPercent', () => {
  it('rundet kaufmaennisch auf eine ganze Prozentzahl ohne Leerzeichen', () => {
    expect(formatCriterionPercent(0.92)).toBe('92%')
    expect(formatCriterionPercent(0.925)).toBe('93%')
  })

  it('stellt die Bandgrenzen als 0% und 100% dar', () => {
    expect(formatCriterionPercent(0)).toBe('0%')
    expect(formatCriterionPercent(1)).toBe('100%')
  })

  it('rundet einen kleinen Wert ungleich null auf 0% - ohne "< 1 %"-Sonderregel', () => {
    // Akzeptanzkriterium 2: bewusst ANDERS als `formatUsd`. Bei einem Geldbetrag darf ein
    // tatsaechlich angefallener Betrag nicht als "nichts ausgegeben" erscheinen; eine
    // Modell-Selbsteinschaetzung von 0,4 % ist dagegen sachlich "0 %".
    expect(formatCriterionPercent(0.004)).toBe('0%')
    expect(formatCriterionPercent(0.995)).toBe('100%')
  })

  it('traegt weder Nachkommastelle noch Leerzeichen vor dem Prozentzeichen', () => {
    // Bewusst anders als die Betrags- und Speicherangaben derselben Seite: dieselbe Zahl
    // erscheint am Foto und in der Statistik, und zwei Formen fuer eine Zahl liessen den Leser
    // nach dem Unterschied suchen.
    expect(formatCriterionPercent(0.925)).toBe('93%')
  })
})

describe('criterionPercentValue', () => {
  it.each([0, 0.004, 0.42, 0.426, 0.925, 0.995, 1])(
    'liefert fuer %s denselben Wert, den der Text zeigt',
    (value) => {
      // Der Wert erscheint an der Motivstaerke als Text UND als Fuellhoehe. Runden beide
      // getrennt, laufen Zahl und Hoehe auseinander - dieser Fall ist die Klammer.
      expect(`${criterionPercentValue(value)}%`).toBe(formatCriterionPercent(value))
    },
  )

  it('rundet eine Staerke groesser null, die auf 0 % faellt, auch geometrisch auf null', () => {
    // Der absichernde Fall: eine Fuellung von 0,4 % Hoehe waere ein Farbstrich, den die Zahl
    // daneben nicht nennt.
    expect(criterionPercentValue(0.004)).toBe(0)
  })
})
