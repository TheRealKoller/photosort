export type ProcessStatus = 'running' | 'success' | 'failed'

/**
 * Prozess-Status-Punkt-Farben (specs/architecture/0004-design-system.md) - geteilt zwischen
 * ProjectListPage und ProjectDetailPage, damit dieselbe running/success/failed-Semantik nicht an
 * zwei Stellen unterschiedlich implementiert wird (Architect-/UX-Review-Fund, Branch
 * feature/0012-visual-redesign-views: ProjectDetailPage faerbte urspruenglich den sichtbaren
 * Statustext selbst ein, was fuer `success`/`failed` WCAG-AA gegen `--bg` verfehlt - `--status-
 * success`/`--status-failed` sind nur als Flaechenfarbe, nicht als Text-/Symbolfarbe kalibriert,
 * siehe Design-System-Dokument, Abschnitt Farbpalette). Nur als dekorativer, `aria-hidden`
 * markierter Punkt neben neutral gefaerbtem Text verwenden, nie selbst als Textfarbe.
 */
export const PROCESS_STATUS_DOT_CLASSES: Record<ProcessStatus, string> = {
  running: 'bg-status-running animate-pulse motion-reduce:animate-none',
  success: 'bg-status-success',
  failed: 'bg-status-failed',
}
