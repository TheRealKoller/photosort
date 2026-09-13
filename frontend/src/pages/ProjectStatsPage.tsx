import type { ReactNode } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { CloudVisionPurpose, ProjectStatsCostByPurpose, ProjectStatsOut } from '../api/types'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '../components/ui/popover'
import { useProjectStatsQuery } from '../hooks/useProjects'
import {
  formatBytes,
  formatCount,
  formatCriterionPercent,
  formatDate,
  formatDateTime,
  formatUsd,
  NOT_AVAILABLE,
} from '../utils/formatStats'

/**
 * Projekt-Statistikseite - eine MOMENTAUFNAHME des Projektzustands an einem Ort: Umfang, Speicher,
 * Ist-Kosten der Remote-Berechnungen, Bearbeitungs- und Bewertungsstand, Kategorienverteilung,
 * Diagnose.
 *
 * Reine Anzeige (Akzeptanzkriterium A3): keine Foto-Vorschauen, keine Bewertungs- oder
 * Kategorie-Bedienelemente, keine Ausloeser fuer Verarbeitungslaeufe, keine Filter-, Sortier- oder
 * Export-Bedienelemente. Die Daten werden einmal beim Oeffnen geladen und aktualisieren sich nicht
 * selbsttaetig (siehe `useProjectStatsQuery`: kein Polling).
 *
 * Aufbau nach dem Schema von ProjectSettingsPage und dem Scan-Schritt: mehrere fokussierte
 * `<section>`-Bloecke mit `<h2>`, kein Karten-Chrome - Whitespace und Abschnittsgrenzen statt
 * einer Kachelwand ("Chrome tritt zurueck", Design-System).
 *
 * Bewusst OHNE `useProjectQuery` fuer den Projektnamen: dieser Hook pollt, solange irgendein Lauf
 * aktiv ist - er wuerde der Seite genau die selbsttaetige Aktualisierung geben, die
 * Akzeptanzkriterium A3 ausschliesst. Den Projektkontext liefert der Sticky-Header.
 */

/** Wiederkehrendes Muster "Grosszahl + Label" (Design-System/UI-Abschnitt der Spec): der Wert in
 * `text-xl`, darunter das Label klein. Rein typografisch, kein eigener Hintergrund, kein
 * Rahmen. */
function Metric({
  value,
  label,
  info,
  children,
}: {
  value: string
  label: string
  info?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="col-span-12 flex min-w-0 flex-col gap-1 sm:col-span-6 lg:col-span-3">
      {/* Kennzahlen in Festbreitenschrift (Board): eine Zahl ist eine Datenausgabe, kein
          Fliesstext - und untereinander stehende Kennzahlen fluchten dadurch. */}
      <span className="font-mono text-xl font-semibold text-text-h">{value}</span>
      <span className="flex items-center gap-1 text-sm text-text">
        {label}
        {info}
      </span>
      {children}
    </div>
  )
}

/**
 * Kennzahlen stehen auf breiten Schirmen nebeneinander und auf dem Smartphone gestapelt.
 *
 * Die erste Verwendung des 12-Spalten-Rasters des Boards (Spaltenbreite fluessig, Zwischenraum 12px
 * = `gap-x-3`). Bewusst hier und nicht als Seitengeruest: eine Kennzahlenreihe ist genau der Fall,
 * fuer den ein festes Spaltenraster gegenueber `flex-wrap` etwas bringt - die Werte stehen
 * untereinander auf einer Achse statt inhaltsabhaengig zu springen.
 */
function MetricRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-12 gap-x-3 gap-y-6">{children}</div>
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    // Abschnittstrenner auf --separator: als freistehende Linie auf dem Grund erreichte --border
    // 1.45:1 und war praktisch keine Linie.
    <section aria-labelledby={id} className="flex flex-col gap-4 border-t border-separator pt-6">
      <h2 id={id} className="text-lg text-text-h">
        {title}
      </h2>
      {children}
    </section>
  )
}

/**
 * Erlaeuterung unmittelbar bei der Kennzahl (Akzeptanzkriterium A2) - das im Projekt etablierte
 * Info-Popover-Muster (Radix, Klick-Ausloeser, 44x44px Trefferflaeche). Bewusst KEIN
 * `title`-Attribut: auf Touchgeraeten unzuverlaessig ausloesbar.
 */
function InfoPopover({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Erkläre ${label}`}
          className="shrink-0 border border-border-control"
        >
          i
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between gap-3 pb-3">
          <p className="text-sm font-semibold text-text-h">{label}</p>
          <PopoverClose asChild>
            <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
              <span aria-hidden="true">×</span>
            </Button>
          </PopoverClose>
        </div>
        <p className="text-sm text-text">{children}</p>
      </PopoverContent>
    </Popover>
  )
}

/** Eine Zeile "Bezeichnung … x von y Fotos" bzw. "Bezeichnung … Wert". */
function DetailRow({ term, children }: { term: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-separator py-2 last:border-b-0">
      <dt className="flex items-center gap-1 text-sm text-text">{term}</dt>
      <dd className="text-sm font-medium text-text-h">{children}</dd>
    </div>
  )
}

const PURPOSE_LABELS: Record<CloudVisionPurpose, string> = {
  landmark: 'Sehenswürdigkeiten-Erkennung',
  remote_category: 'Kategorie-Klassifizierung',
}

/**
 * Hinweis samt Erlaeuterung, beides im Wortlaut des UI/UX-Abschnitts der Spec. Bewusst dezent und
 * ohne Fehler-Rot: eine unvollstaendig erfasste Summe ist kein Fehler, sondern eine Einschraenkung
 * der Aussage.
 *
 * Die Erlaeuterung steht als Beschreibungstext direkt darunter statt in einem Info-Popover
 * (Akzeptanzkriterium A2 laesst beides zu): sie erscheint ohnehin nur im Ausnahmefall, und auf
 * einer Seite zur Kostenkontrolle soll der Vorbehalt nicht erst auf Klick sichtbar werden. Ein
 * Popover je Zweck brauchte zudem zwei Ausloeser mit identischem Text.
 */
function IncompleteHint() {
  return (
    <>
      <span className="text-xs text-text">Summe unvollständig erfasst</span>
      <span className="text-xs text-text">
        Für mindestens einen Lauf dieses Zwecks liegen keine Verbrauchsdaten vor. Es wird bewusst
        nichts geschätzt — der angezeigte Betrag ist die Summe des tatsächlich Erfassten.
      </span>
    </>
  )
}

/**
 * `data-purpose` ist ein semantisches Testattribut nach Projektkonvention (Design-System,
 * "Selektor-Stabilitaet") - es macht pruefbar, dass der Hinweis GENAU beim betroffenen Zweck
 * steht und nicht bei einem unbetroffenen.
 */
function CostEntry({ entry }: { entry: ProjectStatsCostByPurpose }) {
  return (
    <div
      data-purpose={entry.purpose}
      className="flex flex-wrap items-start justify-between gap-2 border-b border-separator py-2 last:border-b-0"
    >
      <dt className="text-sm text-text">{PURPOSE_LABELS[entry.purpose]}</dt>
      <dd className="flex max-w-md flex-col items-end gap-1 text-right">
        <span className="text-sm font-medium text-text-h">{formatUsd(entry.cost_usd)}</span>
        {entry.has_unrecorded_runs && <IncompleteHint />}
      </dd>
    </div>
  )
}

function formatMoment(value: string | null, fallback: string): string {
  return value === null ? fallback : formatDateTime(value)
}

function StatsContent({ stats }: { stats: ProjectStatsOut }) {
  const {
    storage,
    motifs,
    strength_bands: strengthBands,
    cost,
    progress,
    ratings,
    diagnostics,
  } = stats
  const total = stats.photo_count
  // "x von y" mit ueberall derselben Bezugsgroesse (Akzeptanzkriterium F1) - bei 0 Fotos steht
  // ueberall "0 von 0".
  const outOf = (value: number) => `${formatCount(value)} von ${formatCount(total)}`
  // Der lokale Gesamtwert ist die Summe des BEKANNTEN: ist der Datenbank-Anteil nicht ermittelbar,
  // fliesst er nicht als 0 ein, sondern die Teilzeile darunter sagt ausdruecklich, dass er fehlt.
  const localTotalBytes = storage.local_cache_bytes + (storage.local_database_bytes_estimate ?? 0)

  return (
    <div className="flex flex-col gap-8">
      <Section id="stats-scope" title="Umfang und Speicher">
        <MetricRow>
          <Metric value={formatCount(total)} label="Fotos im Projekt" />
          <Metric
            value={formatBytes(storage.opencloud_bytes)}
            label="Originaldateien in OpenCloud"
          />
          <Metric
            value={formatBytes(localTotalBytes)}
            label="Lokal belegt (Thumbnail-Cache + Datenbestand)"
            info={
              <InfoPopover label="geschätzten Datenbank-Anteil">
                Der Datenbank-Anteil lässt sich nur bei einer PostgreSQL-Datenbank abschätzen. Er
                wird aus der Gesamtgröße der Datenbank anteilig nach dem Fotoanteil dieses Projekts
                geschätzt — es ist keine Messung dieses Projekts allein.
              </InfoPopover>
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

      <Section id="stats-cost" title="Kosten für Remote-Berechnungen">
        <MetricRow>
          {/* Bewusst OHNE Erlaeuterung am Gesamtwert: der
              Vorbehalt gilt je Zweck, und der zugehoerige Textbaustein spricht ausdruecklich von
              "diesem Zweck" - an der zweckuebergreifenden Summe stuende er sachlich falsch und
              erschiene selbst dann, wenn beide Zwecke vollstaendig erfasst sind. Er sitzt
              stattdessen unmittelbar am betroffenen Einzelposten (siehe CostEntry). */}
          <Metric
            value={formatUsd(cost.total_usd)}
            label={`Gesamt in diesem Projekt (${cost.currency})`}
          />
        </MetricRow>
        <dl className="flex flex-col">
          {cost.by_purpose.map((entry) => (
            <CostEntry key={entry.purpose} entry={entry} />
          ))}
        </dl>
      </Section>

      <Section id="stats-progress" title="Bearbeitungs- und Bewertungsstand">
        <dl className="flex flex-col">
          <DetailRow term="Gescannt">{outOf(progress.scanned)}</DetailRow>
          <DetailRow term="Thumbnails erzeugt">{outOf(progress.thumbnails_ready)}</DetailRow>
          <DetailRow term="Lokal bewertet">{outOf(progress.ausschuss_scored)}</DetailRow>
          <DetailRow term="Eingeordnet">{outOf(progress.ranked)}</DetailRow>
          {/* "Cloud-klassifiziert" statt des frueheren "Remote klassifiziert": gezaehlt werden
              Fotos mit einer Motiv-Kopfzeile aus der Cloud. Die lokale Kopfzeile des
              Kriterien-Laufs zaehlt hier ausdruecklich nicht mit. */}
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
            Seit ADR 0098 steht der Favorit NEBEN der Albumentscheidung: dasselbe Foto zählt in
            "Favorit" und in "Albumwürdig". Die Anzeige darf keine Aufteilung des Bestands über
            alle vier Zahlen behaupten - deshalb steht "Favorit" hinter den drei Zahlen der
            Albumentscheidung, nicht zwischen ihnen. */}
        <p className="text-sm text-text">
          Die ersten drei Zahlen teilen alle Fotos unter sich auf. „Favorit“ ist eine eigene
          Auszeichnung daneben und zählt deshalb zusätzlich mit — dasselbe Foto kann albumwürdig und
          Favorit sein.
        </p>
      </Section>

      {/* EIN Abschnitt statt der beiden Kategorie-Bloecke (Spec 0427, PR 3). */}
      <Section id="stats-motifs" title="Motivverteilung">
        {/* DAUERHAFT SICHTBAR, nicht hinter einem Info-Auslöser: eine Summe, die nicht aufgeht,
            wird sonst als Fehler gelesen - und dieser Effekt tritt beim ersten Blick ein. */}
        <p className="text-sm text-text">
          Jedes Foto trägt alle acht Motive mit unterschiedlicher Stärke und zählt deshalb in
          mehreren Zeilen — die Summe der Zahlen ist größer als die Zahl der Fotos.
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
                  <InfoPopover label="Bedeutung der Stärkebänder">
                    {`Stark ab ${formatCriterionPercent(strengthBands.strong)}, mittel ab ` +
                      `${formatCriterionPercent(strengthBands.medium)}. Die Grenzen sind eine ` +
                      'Anzeigehilfe dieser Tabelle. Sie entscheiden nicht, ob ein Foto zu einem ' +
                      'Motiv gehört — dafür gibt es keine Schwelle.'}
                  </InfoPopover>
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
              <InfoPopover label="noch nicht klassifiziert">
                Diese Fotos fehlen in jeder Zahl der Tabelle. Sie erhalten Motive erst bei einem
                Klassifizierungslauf, den du selbst auslöst.
              </InfoPopover>
            }
          />
          <Metric value={formatCount(stats.motif_correction_count)} label="Von Hand korrigiert" />
          <Metric
            value={formatCount(stats.excluded_photo_count)}
            label="Als Dokument ausgeschlossen"
            info={
              <InfoPopover label="als Dokument ausgeschlossen">
                Diese Fotos erscheinen in keiner Motivauswahl. Die Einstufung lässt sich nicht von
                Hand ändern.
              </InfoPopover>
            }
          />
        </MetricRow>
      </Section>

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
                <InfoPopover label="übersprungene Dateien">
                  Dateien, die der zuletzt gestartete Scan nicht übernommen hat — etwa weil ihr
                  Format nicht unterstützt wird. Sie gehören zum letzten Scan-Lauf, unabhängig
                  davon, ob dieser erfolgreich war.
                </InfoPopover>
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
                  <InfoPopover label="fehlgeschlagene Remote-Aufrufe">
                    Ein Ist-Zustand, keine Historie: gezählt werden Fotos, für die aktuell ein
                    letzter fehlgeschlagener Cloud-Aufruf vermerkt ist. Ein später erfolgreicher
                    Aufruf für dasselbe Foto senkt den Wert wieder.
                  </InfoPopover>
                </>
              }
            >
              {formatCount(failure.photo_count)}
            </DetailRow>
          ))}
        </dl>
      </Section>
    </div>
  )
}

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
      <StatsContent stats={query.data} />
    </div>
  )
}
