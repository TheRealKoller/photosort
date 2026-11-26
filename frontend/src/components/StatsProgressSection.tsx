import type { ProjectStatsOut } from '../api/types'
import { formatCount } from '../utils/formatStats'
import { DetailRow, Metric, MetricRow, Section } from './StatsLayout'

export function StatsProgressSection({
  progress,
  ratings,
  total,
}: {
  progress: ProjectStatsOut['progress']
  ratings: ProjectStatsOut['ratings']
  total: number
}) {
  // "x von y" mit ueberall derselben Bezugsgroesse - bei 0 Fotos steht
  // ueberall "0 von 0".
  const outOf = (value: number) => `${formatCount(value)} von ${formatCount(total)}`

  return (
    <Section id="stats-progress" title="Bearbeitungs- und Bewertungsstand">
      <dl className="flex flex-col">
        <DetailRow term="Gescannt">{outOf(progress.scanned)}</DetailRow>
        <DetailRow term="Thumbnails erzeugt">{outOf(progress.thumbnails_ready)}</DetailRow>
        <DetailRow term="Lokal bewertet">{outOf(progress.ausschuss_scored)}</DetailRow>
        <DetailRow term="Eingeordnet">{outOf(progress.ranked)}</DetailRow>
        {/* "Cloud-klassifiziert": gezaehlt werden Fotos mit einer Motiv-Kopfzeile aus der Cloud.
          Die lokale Kopfzeile des Kriterien-Laufs zaehlt hier ausdruecklich nicht mit. */}
        <DetailRow term="Cloud-klassifiziert">{outOf(progress.remote_classified)}</DetailRow>
      </dl>
      <p className="text-sm text-text">Deine Bewertungen (nur deine eigenen)</p>
      <MetricRow>
        <Metric value={formatCount(ratings.album_worthy)} label="Albumwürdig" />
        <Metric value={formatCount(ratings.rejected)} label="Aussortiert" />
        <Metric value={formatCount(ratings.unrated)} label="Noch nicht entschieden" />
        <Metric value={formatCount(ratings.favorite)} label="Favorit" />
      </MetricRow>
      {/* DAUERHAFT SICHTBAR, nicht hinter einem Info-Auslöser - dieselbe Begründung wie bei der
        Motivverteilung unten: eine Summe, die nicht aufgeht, wird sonst als Fehler gelesen,
        und dieser Effekt tritt beim ersten Blick ein.
        Der Favorit steht NEBEN der Albumentscheidung: dasselbe Foto zählt in
        "Favorit" und in "Albumwürdig". Die Anzeige darf keine Aufteilung des Bestands über
        alle vier Zahlen behaupten - deshalb steht "Favorit" hinter den drei Zahlen der
        Albumentscheidung, nicht zwischen ihnen. */}
      <p className="text-sm text-text">
        Die ersten drei Zahlen teilen alle Fotos unter sich auf. „Favorit“ ist eine eigene
        Auszeichnung daneben und zählt deshalb zusätzlich mit — dasselbe Foto kann albumwürdig und
        Favorit sein.
      </p>
    </Section>
  )
}
