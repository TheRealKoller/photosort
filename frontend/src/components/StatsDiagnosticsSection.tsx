import type { ProjectStatsOut } from '../api/types'
import { formatCount, formatDateTime } from '../utils/formatStats'
import { PURPOSE_LABELS } from '../utils/statsLabels'
import { StatsInfoPopover } from './StatsInfoPopover'
import { DetailRow, Section } from './StatsLayout'

function formatMoment(value: string | null, fallback: string): string {
  return value === null ? fallback : formatDateTime(value)
}

export function StatsDiagnosticsSection({ stats }: { stats: ProjectStatsOut }) {
  const { diagnostics } = stats

  return (
    <Section id="stats-diagnostics" title="Vertrauen und Fehlersuche">
      <dl className="flex flex-col">
        <DetailRow term="Letzter Scan">
          {formatMoment(stats.last_successful_runs.scan, 'noch nie gelaufen')}
        </DetailRow>
        <DetailRow term="Letzte lokale Bewertung">
          {formatMoment(stats.last_successful_runs.scoring, 'noch nie gelaufen')}
        </DetailRow>
        <DetailRow term="Letzte Klassifizierung">
          {formatMoment(stats.last_successful_runs.classification, 'noch nie gelaufen')}
        </DetailRow>
        <DetailRow term="Letzte Remote-Kategorisierung">
          {formatMoment(
            stats.last_successful_runs.remote_category_classification,
            'noch nie gelaufen',
          )}
        </DetailRow>
        <DetailRow
          term={
            <>
              Übersprungene Dateien
              <StatsInfoPopover label="übersprungene Dateien">
                Dateien, die der zuletzt gestartete Scan nicht übernommen hat — etwa weil ihr Format
                nicht unterstützt wird. Sie gehören zum letzten Scan-Lauf, unabhängig davon, ob
                dieser erfolgreich war.
              </StatsInfoPopover>
            </>
          }
        >
          {diagnostics.last_scan_files_skipped === null
            ? 'noch nie gescannt'
            : formatCount(diagnostics.last_scan_files_skipped)}
        </DetailRow>
        <DetailRow term="Als Duplikat markiert">
          {formatCount(diagnostics.duplicate_photo_count)}
        </DetailRow>
        {diagnostics.remote_failures.map((failure) => (
          <DetailRow
            key={failure.purpose}
            term={
              <>
                {`Fehlgeschlagen: ${PURPOSE_LABELS[failure.purpose]}`}
                <StatsInfoPopover label="fehlgeschlagene Remote-Aufrufe">
                  Ein Ist-Zustand, keine Historie: gezählt werden Fotos, für die aktuell ein letzter
                  fehlgeschlagener Cloud-Aufruf vermerkt ist. Ein später erfolgreicher Aufruf für
                  dasselbe Foto senkt den Wert wieder.
                </StatsInfoPopover>
              </>
            }
          >
            {formatCount(failure.photo_count)}
          </DetailRow>
        ))}
      </dl>
    </Section>
  )
}
