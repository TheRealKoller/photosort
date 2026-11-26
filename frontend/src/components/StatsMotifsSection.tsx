import type { ProjectStatsOut } from '../api/types'
import { formatCount, formatCriterionPercent, NOT_AVAILABLE } from '../utils/formatStats'
import { StatsInfoPopover } from './StatsInfoPopover'
import { Metric, MetricRow, Section } from './StatsLayout'

export function StatsMotifsSection({ stats }: { stats: ProjectStatsOut }) {
  const { motifs, strength_bands: strengthBands } = stats

  return (
    <Section id="stats-motifs" title="Motivverteilung">
      {/* DAUERHAFT SICHTBAR, nicht hinter einem Info-Auslöser: eine Summe, die nicht aufgeht,
        wird sonst als Fehler gelesen - und dieser Effekt tritt beim ersten Blick ein. */}
      <p className="text-sm text-text">
        Jedes Foto trägt alle acht Motive mit unterschiedlicher Stärke und zählt deshalb in mehreren
        Zeilen — die Summe der Zahlen ist größer als die Zahl der Fotos.
      </p>
      <table className="w-full table-fixed text-sm">
        <thead>
          {/* Tabellenkopf in der Board-Rolle "Beschriftung". */}
          <tr className="border-b border-separator text-left text-xs font-semibold uppercase tracking-wide text-text">
            <th scope="col" className="py-2">
              Motiv
            </th>
            <th scope="col" className="py-2 text-right">
              <span className="inline-flex items-center gap-1">
                stark
                {/* Die Grenzen werden aus `strength_bands` FORMATIERT, nicht im Frontend
                  hinterlegt: `0.67` hier und `2/3` im Backend verschöben die Grenze um einen
                  Betrag, den kein Fall trifft. */}
                <StatsInfoPopover label="Bedeutung der Stärkebänder">
                  {`Stark ab ${formatCriterionPercent(strengthBands.strong)}, mittel ab ` +
                    `${formatCriterionPercent(strengthBands.medium)}. Die Grenzen sind eine ` +
                    'Anzeigehilfe dieser Tabelle. Sie entscheiden nicht, ob ein Foto zu einem ' +
                    'Motiv gehört — dafür gibt es keine Schwelle.'}
                </StatsInfoPopover>
              </span>
            </th>
            <th scope="col" className="py-2 text-right">
              mittel
            </th>
            <th scope="col" className="py-2 text-right">
              schwach
            </th>
            <th scope="col" className="py-2 text-right">
              Ø Stärke
            </th>
          </tr>
        </thead>
        <tbody>
          {motifs.map((entry) => (
            <tr key={entry.motif_key} className="border-b border-separator">
              {/* Anzeigename AUSSCHLIESSLICH vom Server - es gibt bewusst keine
                Uebersetzungstabelle fuer Motivschluessel im Frontend. */}
              <th
                scope="row"
                data-motif-key={entry.motif_key}
                className="break-words py-2 text-left font-normal text-text-h"
              >
                {entry.display_name}
              </th>
              <td className="py-2 text-right font-mono text-text-h">
                {formatCount(entry.strong_photo_count)}
              </td>
              <td className="py-2 text-right font-mono text-text">
                {formatCount(entry.medium_photo_count)}
              </td>
              <td className="py-2 text-right font-mono text-text">
                {formatCount(entry.weak_photo_count)}
              </td>
              {/* Ein Motiv ohne ein einziges beurteiltes Foto zeigt KEINEN Prozentwert - `0 %`
                waere die Aussage "das Modell sieht das Motiv durchweg nicht". Deshalb der
                Strich aus `NOT_AVAILABLE` ("nicht ermittelbar") und die Pruefung auf
                `=== null` statt auf Falsyness: `0` ist ein gueltiger Mittelwert. */}
              <td className="py-2 text-right font-mono text-text-h">
                {entry.average_strength === null
                  ? NOT_AVAILABLE
                  : formatCriterionPercent(entry.average_strength)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <MetricRow>
        <Metric
          value={formatCount(stats.unassessed_photo_count)}
          label="Noch nicht klassifiziert"
          info={
            <StatsInfoPopover label="noch nicht klassifiziert">
              Diese Fotos fehlen in jeder Zahl der Tabelle. Sie erhalten Motive erst bei einem
              Klassifizierungslauf, den du selbst auslöst.
            </StatsInfoPopover>
          }
        />
        <Metric value={formatCount(stats.motif_correction_count)} label="Von Hand korrigiert" />
        <Metric
          value={formatCount(stats.excluded_photo_count)}
          label="Als Dokument ausgeschlossen"
          info={
            <StatsInfoPopover label="als Dokument ausgeschlossen">
              Diese Fotos erscheinen in keiner Motivauswahl. Die Einstufung lässt sich nicht von
              Hand ändern.
            </StatsInfoPopover>
          }
        />
      </MetricRow>
    </Section>
  )
}
