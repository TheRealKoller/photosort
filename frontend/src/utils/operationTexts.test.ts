import { describe, expect, it } from 'vitest'

import {
  CANCEL_TEXTS,
  cancelAllDescription,
  cancelAriaLabel,
  cancelRequestedText,
  cancelledAtText,
  cancelledText,
  operationStatusWord,
  operationsBarText,
  waitingText,
} from './operationTexts'

const SCAN = {
  kind: 'scan',
  run_id: 4,
  label: 'Scan',
  status: 'running',
  cancel_requested: false,
} as const
const EXPORT = {
  kind: 'export',
  run_id: 9,
  label: 'Export',
  status: 'queued',
  cancel_requested: false,
} as const

describe('operationTexts (Spec 0641)', () => {
  it('nennt den Knopf "Abbrechen" und seinen angeforderten Zustand', () => {
    expect(CANCEL_TEXTS.button).toBe('Abbrechen')
    expect(CANCEL_TEXTS.requested).toBe('Wird abgebrochen…')
    expect(CANCEL_TEXTS.retry).toBe('Erneut versuchen')
  })

  it('setzt den Vorgangsnamen vor das Wort - der sichtbare Knopftext bleibt enthalten', () => {
    expect(cancelAriaLabel('scan')).toBe('Scan abbrechen')
    expect(cancelAriaLabel('ausschuss')).toBe('Ausschuss abbrechen')
    // WCAG 2.5.3 vergleicht ohne Ruecksicht auf Gross-/Kleinschreibung ("abbrechen"/"Abbrechen").
    for (const label of [
      cancelAriaLabel('scan'),
      cancelAriaLabel('export'),
      cancelAriaLabel('review'),
    ]) {
      expect(label.toLowerCase()).toContain(CANCEL_TEXTS.button.toLowerCase())
    }
    expect(cancelAriaLabel('export')).toBe('Export abbrechen')
    expect(cancelAriaLabel('review')).toBe('Prüfung abbrechen')
  })

  it('unterscheidet die drei Statuszeilen desselben Vorgangs', () => {
    expect(waitingText('export')).toBe('Export wartet')
    expect(cancelRequestedText('export')).toBe('Export wird abgebrochen…')
    expect(cancelledText('export')).toBe('Export abgebrochen')
  })

  it('beugt die Dialogbeschreibung nach Anzahl', () => {
    expect(cancelAllDescription(1)).toBe('1 Vorgang wird angehalten:')
    expect(cancelAllDescription(3)).toBe('3 Vorgänge werden angehalten:')
  })

  it('nennt in der Projektleiste die Vorgaenge beim Namen', () => {
    expect(operationsBarText([SCAN, EXPORT], false)).toBe('Läuft oder wartet: Scan, Export')
    expect(operationsBarText([SCAN, EXPORT], true)).toBe('Wird abgebrochen: Scan, Export')
  })

  it('beschreibt den Stand eines Vorgangs im Dialog', () => {
    expect(operationStatusWord('queued')).toBe('wartet')
    expect(operationStatusWord('running')).toBe('läuft')
  })

  it('nennt den eingefrorenen Stand des Abbruchs, nie eine Restdauer', () => {
    expect(cancelledAtText(12, 40, 'Fotos')).toBe('Abgebrochen bei 12 von 40 Fotos')
    expect(cancelledAtText(12, 40, 'Fotos')).not.toMatch(/schätzung|verbleib|rest/i)
  })
})
