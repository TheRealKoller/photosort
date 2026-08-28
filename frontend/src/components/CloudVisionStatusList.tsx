import type { CloudVisionPhase, CloudVisionStatus, CloudVisionStatusOut } from '../api/types'

interface CloudVisionStatusListProps {
  cloudVisionStatus: CloudVisionStatusOut[]
}

const PHASE_LABELS: Record<CloudVisionPhase, string> = {
  landmark: 'Landmark-Erkennung',
  remote_category: 'Remote-Kategorie',
}

const STATUS_LABELS: Record<CloudVisionStatus, string> = {
  not_run: 'Noch nicht verarbeitet',
  not_candidate: 'Nicht als Kandidat qualifiziert',
  consent_disabled: 'Cloud-Erkennung deaktiviert',
  error: 'Fehler beim Versuch',
  no_result: 'Erfolgreich, keine Treffer',
  result: 'Ergebnis vorhanden',
}

// Bewertungs-/Prozess-Status-Farben duerfen laut Design-System (specs/architecture/0004-design-
// system.md, "Farbpalette") nie als direkte Text-/Symbolfarbe auf --bg gerendert werden (WCAG-AA
// gegen --bg verfehlt) - nur als aria-hidden, dekoratives Icon mit redundantem Text daneben (3:1-
// Schwelle statt 4.5:1), analog components/ui/alert.tsx ("⚠" in text-status-failed) und
// components/StatusDot.tsx. Der sichtbare Status-TEXT bleibt deshalb bewusst neutral
// (text-text-h), nur das Icon traegt die Farbe.
const STATUS_ICONS: Record<CloudVisionStatus, { glyph: string; colorClass: string }> = {
  not_run: { glyph: '○', colorClass: 'text-text' },
  not_candidate: { glyph: '○', colorClass: 'text-text' },
  consent_disabled: { glyph: '○', colorClass: 'text-text' },
  error: { glyph: '⚠', colorClass: 'text-status-failed' },
  no_result: { glyph: '✓', colorClass: 'text-status-success' },
  result: { glyph: '✓', colorClass: 'text-status-success' },
}

function formatAttemptedAt(attemptedAt: string): string {
  return new Date(attemptedAt).toLocaleString('de-DE')
}

/**
 * Reine Praesentationskomponente mit dem Cloud-Vision-Status beider Laeufe eines Fotos
 * (specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
 * fehler-persistierung.md) - analog CriterionDetailsList strukturiert (`<dl>`, kein Card-Rahmen,
 * "Die Fotos sind der Star"). Rendert IMMER genau die uebergebenen Eintraege ohne eigene
 * Sichtbarkeitsentscheidung (permanente Sichtbarkeit ist eine bewusste Stakeholder-Entscheidung
 * der Spec, umgesetzt vom Aufrufer PhotoDetailPage.tsx - analog CriterionDetailsList-
 * Praezedenzfall, dessen Docstring dieselbe Aufteilung dokumentiert).
 *
 * `error_message` wird ausschliesslich ueber einen regulaeren React-Textknoten gerendert, nie
 * `dangerouslySetInnerHTML` (Sicherheits-Muss-Kriterium der Spec, defense in depth - erste Stelle
 * im Projekt, an der ein roher, aus einer Exception stammender String direkt an die UI
 * durchgereicht wird).
 */
export function CloudVisionStatusList({ cloudVisionStatus }: CloudVisionStatusListProps) {
  return (
    <dl className="flex flex-col gap-3">
      {cloudVisionStatus.map((entry) => {
        const icon = STATUS_ICONS[entry.status]
        return (
          <div key={entry.phase} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-text">{PHASE_LABELS[entry.phase]}</dt>
              <dd className="flex items-center gap-1.5 font-medium text-text-h">
                <span aria-hidden="true" className={icon.colorClass}>
                  {icon.glyph}
                </span>
                <span>{STATUS_LABELS[entry.status]}</span>
              </dd>
            </div>
            {entry.status === 'error' && (
              <div className="flex flex-col gap-0.5">
                {/* Regulaerer React-Textknoten (nie dangerouslySetInnerHTML) - Sicherheits-Muss-
                    Kriterium der Spec, siehe Komponenten-Docstring. */}
                <p className="text-xs text-text">{entry.error_message}</p>
                {entry.attempted_at !== null && (
                  <p className="text-xs text-text">{formatAttemptedAt(entry.attempted_at)}</p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </dl>
  )
}
