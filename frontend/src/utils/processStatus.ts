/**
 * `queued` und `cancelled` tragen bewusst KEINE Statusfarbe und keinen Puls: sie
 * zeigen weder Erfolg noch Fehler an. Der Punkt faellt auf dieselbe neutrale Flaeche wie „kein
 * Status" zurueck - die Farbe behauptet hier nichts.
 */
export type ProcessStatus = 'running' | 'queued' | 'success' | 'failed' | 'cancelled'

/**
 * Prozess-Status-Punkt-Farben - geteilt zwischen ProjectListPage und ProjectDetailPage, damit
 * dieselbe running/success/failed-Semantik nicht an zwei Stellen unterschiedlich implementiert
 * wird. `--status-success`/`--status-failed` sind nur als Flaechenfarbe kalibriert, nicht als
 * Text-/Symbolfarbe: Nur als dekorativer, `aria-hidden` markierter Punkt neben neutral gefaerbtem
 * Text verwenden, nie selbst als Textfarbe.
 */
export const PROCESS_STATUS_DOT_CLASSES: Record<ProcessStatus, string> = {
  running: 'bg-status-running animate-pulse motion-reduce:animate-none',
  success: 'bg-status-success',
  failed: 'bg-status-failed',
  queued: 'bg-separator',
  cancelled: 'bg-separator',
}
