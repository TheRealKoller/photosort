import type { CloudVisionPhase, CloudVisionStatus, CloudVisionStatusOut } from '../api/types'
import { StatusDot } from './StatusDot'
import { Icon } from './ui/icon'
import type { IconName } from './ui/icon'

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

/*
 * Bewertungs-/Prozess-Status-Farben duerfen laut Design-System nie als direkte Text-/Symbolfarbe
 * auf dem Seitengrund gerendert werden - nur als aria-hidden, dekoratives Symbol mit redundantem
 * Text daneben (3:1-Schwelle statt 4.5:1). Der sichtbare Status-TEXT bleibt deshalb bewusst
 * neutral, nur das Symbol traegt die Farbe.
 *
 * Die drei "nicht gelaufen"-Zustaende bekommen den vorhandenen `StatusDot` statt eines Symbols:
 * der Zwoelfer-Satz des Boards enthaelt keinen leeren Kreis, und ihn stillschweigend um ein
 * dreizehntes Symbol zu erweitern waere eine Gestaltungsentscheidung ohne Vorlage
 * (decisions/0055-dark-utility-register-fundament.md Punkt 7e). Sie sind untereinander
 * ausschliesslich ueber ihren TEXT unterscheidbar - das ist der Grund, warum die Tests die
 * Unterscheidung am Text festmachen und nicht am Symbol.
 *
 * `error` traegt `--danger-text` statt `--danger`: die Symbolfarbe steht hier unmittelbar neben
 * Fliesstext derselben Farbe (die Fehlermeldung darunter), und `--danger` haelt als Fliesstext auf
 * erhoehten Flaechen kein AA.
 */
const STATUS_ICONS: Record<CloudVisionStatus, { icon: IconName; colorClass: string } | null> = {
  not_run: null,
  not_candidate: null,
  consent_disabled: null,
  error: { icon: 'x-circle', colorClass: 'text-danger-text' },
  no_result: { icon: 'check', colorClass: 'text-status-success' },
  result: { icon: 'check', colorClass: 'text-status-success' },
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
              <dd className="flex items-center gap-2 font-medium text-text-h">
                {icon === null ? (
                  <StatusDot status={null} />
                ) : (
                  <span aria-hidden="true" className={icon.colorClass}>
                    <Icon name={icon.icon} size={16} />
                  </span>
                )}
                <span>{STATUS_LABELS[entry.status]}</span>
              </dd>
            </div>
            {entry.status === 'error' && (
              <div className="flex flex-col gap-1">
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
