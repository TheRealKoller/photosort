import { describe, expect, it } from 'vitest'

import { ETA_EXPERIENCE_TEXT, ETA_STEP_TEXTS, ETA_UNKNOWN_TEXT, etaText } from './classificationEta'

/**
 * specs/features/0481-restdauer-klassifizierungslauf.md, decisions/0116-restdauer-als-
 * servermessung-spanne-im-frontend-keine-gesamtrestzeit.md Punkt 4: Aus der gelieferten
 * Sekundenzahl entsteht hier die angezeigte Spanne - nie eine Einzelzahl.
 */

describe('etaText: die Stufenleiter', () => {
  it.each([
    [0, 'nur noch wenige Sekunden'],
    [59.9, 'nur noch wenige Sekunden'],
    [60, 'noch ca. 1–2 Minuten'],
    [119.9, 'noch ca. 1–2 Minuten'],
    [120, 'noch ca. 2–5 Minuten'],
    [299.9, 'noch ca. 2–5 Minuten'],
    [300, 'noch ca. 5–10 Minuten'],
    [599.9, 'noch ca. 5–10 Minuten'],
    [600, 'noch ca. 10–20 Minuten'],
    [1199.9, 'noch ca. 10–20 Minuten'],
    [1200, 'noch ca. 20–40 Minuten'],
    [2399.9, 'noch ca. 20–40 Minuten'],
    [2400, 'noch über 40 Minuten'],
  ])('%s Sekunden ergeben "%s"', (seconds, expected) => {
    // Jede Grenze GENAU AUF ihr geprueft, nicht nur daneben: `>` statt `>=` verschoebe jede Stufe
    // um genau diesen einen Wert, und kein Test daneben faende das.
    expect(etaText('measured', seconds)).toBe(expected)
  })

  it('faengt bei null Sekunden den unteren Randtext', () => {
    expect(etaText('measured', 0)).toBe('nur noch wenige Sekunden')
  })

  it('faengt einen sehr grossen Wert mit dem oberen Randtext', () => {
    expect(etaText('measured', 60 * 60 * 24 * 365)).toBe('noch über 40 Minuten')
  })

  it('erzeugt ueber den gesamten Wertebereich keinen Text ausserhalb des Vorrats', () => {
    // AK2 als BILDMENGEN-Pruefung, nicht als Stichprobe: Der Streifzug laeuft in feiner Schrittweite
    // ueber den ganzen Bereich; die erzeugte Textmenge muss GLEICH der Stufenleiter sein. Eine
    // Teilmengen-Pruefung bestuende auch gegen eine Stufe, die nie erreicht wird.
    const produced = new Set<string>()
    for (let seconds = 0; seconds <= 3600; seconds += 0.5) {
      produced.add(etaText('measured', seconds))
    }

    expect([...produced].sort()).toEqual([...ETA_STEP_TEXTS].sort())
  })

  it('zeigt nie eine Einzelzahl aus der gelieferten Sekundenzahl', () => {
    // Die Randtexte tragen bewusst KEINE Zahl ("noch ca. 30 Sekunden" waere genau eine, AK2).
    expect(ETA_STEP_TEXTS[0]).not.toMatch(/\d/)
    expect(ETA_STEP_TEXTS[ETA_STEP_TEXTS.length - 1]).toMatch(/40/)
    expect(etaText('measured', 137)).not.toContain('137')
  })
})

describe('etaText: die beiden nicht gemessenen Arten', () => {
  it('sagt bei fehlender Schaetzung den EINEN festen Satz', () => {
    // AK4: fuer alle drei Ursachen (zu wenige Einheiten, zu kurze Zeit, kein Phasenbeginn)
    // ununterscheidbar - weder ein leeres Feld noch eine Zahl.
    expect(etaText('unknown', null)).toBe(ETA_UNKNOWN_TEXT)
    expect(ETA_UNKNOWN_TEXT).toBe('wird noch ermittelt')
  })

  it('faellt auch bei fehlendem Wert trotz Art "measured" auf denselben Satz zurueck', () => {
    // Defensiv gegen eine Antwort, die `phase` nennt, aber keinen Wert liefert: ein leeres Feld
    // waere hier die einzige Alternative, und genau das schliesst AK4 aus.
    expect(etaText('measured', null)).toBe(ETA_UNKNOWN_TEXT)
  })

  it('zeigt fuer den Rangfolge-Teilschritt den Erfahrungstext', () => {
    expect(etaText('experience', null)).toBe(ETA_EXPERIENCE_TEXT)
  })

  it('haelt den Erfahrungstext von der Form einer Messung fern', () => {
    // ADR 0116 Punkt 5: Er steht unmittelbar neben gemessenen Angaben und wuerde sonst als eine
    // gelesen - keine Ziffer, und nie die Form "noch ca. A-B".
    expect(ETA_EXPERIENCE_TEXT).not.toMatch(/\d/)
    expect(ETA_EXPERIENCE_TEXT.startsWith('noch ca.')).toBe(false)
  })

  it('ignoriert eine gelieferte Zahl beim Erfahrungstext', () => {
    expect(etaText('experience', 1234)).toBe(ETA_EXPERIENCE_TEXT)
  })
})
