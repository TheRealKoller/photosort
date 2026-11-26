import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import { ProjectStatsContent } from '../components/ProjectStatsContent'
import { Alert } from '../components/ui/alert'
import { useProjectStatsQuery } from '../hooks/useProjects'

/**
 * Projekt-Statistikseite - eine MOMENTAUFNAHME des Projektzustands an einem Ort: Umfang, Speicher,
 * Ist-Kosten der Remote-Berechnungen, Bearbeitungs- und Bewertungsstand, Kategorienverteilung,
 * Diagnose.
 *
 * Reine Anzeige: keine Foto-Vorschauen, keine Bewertungs- oder
 * Kategorie-Bedienelemente, keine Ausloeser fuer Verarbeitungslaeufe, keine Filter-, Sortier- oder
 * Export-Bedienelemente. Die Daten werden einmal beim Oeffnen geladen und aktualisieren sich nicht
 * selbsttaetig (siehe `useProjectStatsQuery`: kein Polling).
 *
 * Aufbau nach dem Schema von ProjectSettingsPage und dem Scan-Schritt: mehrere fokussierte
 * `<section>`-Bloecke mit `<h2>`, kein Karten-Chrome - Whitespace und Abschnittsgrenzen statt
 * einer Kachelwand ("Chrome tritt zurueck", Design-System).
 *
 * Bewusst OHNE `useProjectQuery` fuer den Projektnamen: dieser Hook pollt, solange irgendein Lauf
 * aktiv ist - er wuerde der Seite genau die selbsttaetige Aktualisierung geben, die diese Seite
 * ausschliesst. Den Projektkontext liefert der Sticky-Header.
 */

export function ProjectStatsPage() {
  const { projectId } = useParams()
  const query = useProjectStatsQuery(Number(projectId))

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Statistik wird geladen…
      </p>
    )
  }

  if (query.isError || !query.data) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Fehler beim Laden der Statistik.'}
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl sm:text-2xl">Statistik</h1>
        <p className="text-sm text-text">Momentaufnahme des aktuellen Stands</p>
      </header>
      <ProjectStatsContent stats={query.data} />
    </div>
  )
}
