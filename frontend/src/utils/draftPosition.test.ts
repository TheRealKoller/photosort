import { describe, expect, it } from 'vitest'

import { currentSectionPosition } from './draftPosition'

/*
 * Als aktuell gilt der Abschnitt, dessen Oberkante zuletzt unter die Kopfleiste gelaufen ist (ihre
 * Unterkante liegt hier bei 100). Abschnitte stehen in Dokumentreihenfolge; ein zugeklappter Tag
 * ist EIN Abschnitt mit der Position seines ersten Events.
 */
const EDGE = 100

describe('currentSectionPosition', () => {
  it.each([
    {
      name: 'vor dem ersten Abschnitt gilt Event 1',
      sections: [
        { position: 1, top: 300 },
        { position: 2, top: 900 },
      ],
      expected: 1,
    },
    {
      name: 'an der Kante gilt der Abschnitt schon',
      sections: [
        { position: 1, top: -400 },
        { position: 2, top: EDGE },
      ],
      expected: 2,
    },
    {
      name: 'einen Pixel darunter noch der vorige',
      sections: [
        { position: 1, top: -400 },
        { position: 2, top: EDGE + 1 },
      ],
      expected: 1,
    },
    {
      name: 'weit gescrollt: der letzte, der darunter lief',
      sections: [
        { position: 1, top: -2000 },
        { position: 2, top: -900 },
        { position: 3, top: 40 },
        { position: 4, top: 600 },
      ],
      expected: 3,
    },
    {
      name: 'zurueckgescrollt: dieselbe Regel, keine Erinnerung an den Weg',
      sections: [
        { position: 1, top: -50 },
        { position: 2, top: 700 },
        { position: 3, top: 1500 },
      ],
      expected: 1,
    },
    {
      name: 'zugeklappter Tag zaehlt mit der Position seines ersten Events',
      sections: [
        { position: 1, top: -300 },
        { position: 2, top: -200 },
        { position: 5, top: 20 },
        { position: 6, top: 80 },
      ],
      expected: 6,
    },
    {
      name: 'ein leeres Event ist ein Abschnitt wie jeder andere',
      sections: [
        { position: 1, top: -600 },
        { position: 2, top: 60 },
        { position: 3, top: 140 },
      ],
      expected: 2,
    },
    {
      name: 'ein vom Filter geleertes Event steht weiter und zaehlt mit',
      sections: [
        { position: 1, top: -80 },
        { position: 2, top: 10 },
        { position: 3, top: 400 },
      ],
      expected: 2,
    },
  ])('$name', ({ sections, expected }) => {
    expect(currentSectionPosition(sections, EDGE)).toBe(expected)
  })

  it('falls back to event 1 without any section', () => {
    expect(currentSectionPosition([], EDGE)).toBe(1)
  })
})
