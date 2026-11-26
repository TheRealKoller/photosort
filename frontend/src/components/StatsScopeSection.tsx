import type { ProjectStatsOut } from '../api/types'
import { formatBytes, formatCount, formatDate, NOT_AVAILABLE } from '../utils/formatStats'
import { StatsInfoPopover } from './StatsInfoPopover'
import { Metric, MetricRow, Section } from './StatsLayout'

export function StatsScopeSection({ stats }: { stats: ProjectStatsOut }) {
  const { storage } = stats
  const total = stats.photo_count
  // Der lokale Gesamtwert ist die Summe des BEKANNTEN: ist der Datenbank-Anteil nicht ermittelbar,
  // fliesst er nicht als 0 ein, sondern die Teilzeile darunter sagt ausdruecklich, dass er fehlt.
  const localTotalBytes = storage.local_cache_bytes + (storage.local_database_bytes_estimate ?? 0)

  return (
    <Section id="stats-scope" title="Umfang und Speicher">
      <MetricRow>
        <Metric value={formatCount(total)} label="Fotos im Projekt" />
        <Metric value={formatBytes(storage.opencloud_bytes)} label="Originaldateien in OpenCloud" />
        <Metric
          value={formatBytes(localTotalBytes)}
          label="Lokal belegt (Thumbnail-Cache + Datenbestand)"
          info={
            <StatsInfoPopover label="geschätzten Datenbank-Anteil">
              Der Datenbank-Anteil lässt sich nur bei einer PostgreSQL-Datenbank abschätzen. Er wird
              aus der Gesamtgröße der Datenbank anteilig nach dem Fotoanteil dieses Projekts
              geschätzt — es ist keine Messung dieses Projekts allein.
            </StatsInfoPopover>
          }
        >
          <span className="flex flex-col text-xs text-text">
            <span>Thumbnail-Cache: {formatBytes(storage.local_cache_bytes)}</span>
            <span>
              Datenbank (geschätzt):{' '}
              {storage.local_database_bytes_estimate === null
                ? 'nicht ermittelbar'
                : formatBytes(storage.local_database_bytes_estimate)}
            </span>
          </span>
        </Metric>
      </MetricRow>
      <div className="flex flex-col gap-1">
        <span className="text-sm text-text">Zeitraum der Aufnahmen</span>
        {stats.taken_at_earliest === null || stats.taken_at_latest === null ? (
          <>
            <span className="text-lg text-text-h">{NOT_AVAILABLE}</span>
            <span className="text-xs text-text">Noch keine Fotos im Projekt.</span>
          </>
        ) : (
          <span className="text-lg text-text-h">
            {formatDate(stats.taken_at_earliest)} – {formatDate(stats.taken_at_latest)}
          </span>
        )}
      </div>
    </Section>
  )
}
