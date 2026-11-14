import type { OperationKind, OperationOut } from '../api/types'
import { OPERATION_LABELS } from './stepActionTexts'

/*
 * Spec 0641: Die Wortlaute des Abbruchs an EINER Stelle. Sie stehen im Knopf, in der Statuszeile,
 * in der Projektleiste, im Dialog und im Fehlerfall; eine Seite, die ihren eigenen Satz tippt,
 * hiesse beim naechsten Wortlautwechsel nachziehen zu muessen.
 */

export const CANCEL_TEXTS = {
  /** Der sichtbare Knopftext - der zugaengliche Name ergaenzt den Vorgang davor. */
  button: 'Abbrechen',
  /** Zustand "angefordert": gesperrt, bis der Lauf wirklich endet. */
  requested: 'Wird abgebrochen…',
  /** Scheitert nur die Uebermittlung (Netz/5xx) - der Vorgang laeuft dann weiter. */
  failed: 'Der Abbruch konnte nicht übermittelt werden.',
  retry: 'Erneut versuchen',
  all: 'Alle abbrechen',
  dialogTitle: 'Alle Vorgänge abbrechen?',
  /** Die harmlose Antwort im Dialog - keine Bestaetigung, kein „Verwerfen". */
  keepRunning: 'Weiterlaufen lassen',
  keepsRunning:
    'Was bis jetzt fertig ist, bleibt erhalten. Ein gerade begonnenes Foto wird noch abgeschlossen.',
} as const

/** „Scan abbrechen" - enthaelt den sichtbaren Knopftext woertlich (WCAG 2.5.3). */
export function cancelAriaLabel(kind: OperationKind): string {
  return `${OPERATION_LABELS[kind]} abbrechen`
}

export function cancelRequestedText(kind: OperationKind): string {
  return `${OPERATION_LABELS[kind]} wird abgebrochen…`
}

export function waitingText(kind: OperationKind): string {
  return `${OPERATION_LABELS[kind]} wartet`
}

export function cancelledText(kind: OperationKind): string {
  return `${OPERATION_LABELS[kind]} abgebrochen`
}

/** „1 Vorgang wird angehalten:" bzw. „{n} Vorgänge werden angehalten:". */
export function cancelAllDescription(count: number): string {
  return count === 1 ? '1 Vorgang wird angehalten:' : `${count} Vorgänge werden angehalten:`
}

/** Das Wort hinter dem Vorgangsnamen - dieselbe Vokabel wie in den Endzustaenden. */
export function operationStatusWord(status: OperationOut['status']): string {
  return status === 'queued' ? 'wartet' : 'läuft'
}

/** „Läuft oder wartet: Scan, Export" - die Statuszeile der Projektleiste. */
export function operationsBarText(operations: OperationOut[], allCancelRequested: boolean): string {
  const names = operations.map((operation) => operation.label).join(', ')
  return allCancelRequested ? `Wird abgebrochen: ${names}` : `Läuft oder wartet: ${names}`
}

/** Der eingefrorene Stand eines abgebrochenen Laufs - nie 0, nie eine Restdauer. */
export function cancelledAtText(done: number, total: number, unit: string): string {
  return `Abgebrochen bei ${done} von ${total} ${unit}`
}
