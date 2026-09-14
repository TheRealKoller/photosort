import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import { ProjectStandLine } from '../components/ProjectStandLine'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Icon } from '../components/ui/icon'
import { Skeleton } from '../components/ui/skeleton'
import { useProjectsQuery } from '../hooks/useProjects'
import { cn } from '../lib/utils'
import { formatCount, formatTakenAtRange, NOT_AVAILABLE } from '../utils/formatStats'
import { deriveProjectStand } from '../utils/pipelineSteps'

const SKELETON_CARD_COUNT = 4

/*
 * Die Projektkarte ist EIN DOM-Baum, kein zweiter Zweig je Breite: `lg:grid lg:grid-cols-12` auf
 * dem bestehenden `Link`. Kein `hidden lg:block` neben `lg:hidden`, kein doppelter Inhalt, keine
 * Spaltenkopfzeile - JEDER WERT TRAEGT SEIN WORT BEI SICH ("… Fotos", "Aufnahmen …"). Ein Wert,
 * der seine Bedeutung aus einer Kopfzeile bezoege, braeuchte zwei Darstellungen, und die zweite
 * waere Text, den es nur in einer Breite gibt.
 */
function ProjectCard({ project }: { project: ProjectOut }) {
  const takenAtRange = formatTakenAtRange(project.taken_at_earliest, project.taken_at_latest)
  // WER HIER ENTSCHEIDET: die Formatierungsfunktion, nicht die Karte. Verglichen wird gegen die von
  // ihr selbst zurueckgegebene Konstante, statt die Regel "einer der beiden Werte fehlt" ein
  // zweites Mal hinzuschreiben - eine zweite Formulierung liefe mit der ersten auseinander.
  const isTakenAtPlaceholder = takenAtRange === NOT_AVAILABLE

  return (
    <Card className="p-0">
      {/* Die ganze Zeile ist EINE Trefferflaeche - `min-h-11` als Zeilenhoehe einer zeilenweisen
          Liste (Trefferflaechen-Regel 3), nicht als Schaltflaechenmass. */}
      <Link
        to={`/projects/${project.id}`}
        className="flex min-h-11 flex-col gap-2 px-4 py-3 lg:grid lg:grid-cols-12 lg:items-center lg:gap-x-3 lg:gap-y-0"
      >
        <span className="flex min-w-0 flex-col lg:col-span-4">
          {/* Ungekuerzt und umbrechend: ein Projektname ist die Kennung, unter der der Nutzer sein
              Projekt wiedererkennt - ein abgeschnittener Name macht zwei aehnliche Projekte
              ununterscheidbar. */}
          <span className="text-lg font-semibold leading-tight text-text-h">{project.name}</span>
          {/* Pfad in Festbreitenschrift und einzeilig gekuerzt: ein Cloud-Pfad ist eine technische
              Kennung, kein Fliesstext. */}
          <span className="truncate font-mono text-xs text-text">{project.opencloud_path}</span>
        </span>

        {/* Zahl in Festbreitenschrift, Wortmarke in der Textschrift - die Wortmarke steht IM
            sichtbaren Text, nicht in einer Spaltenkopfzeile. Der `data-testid` macht den Bereich
            einzeln lokalisierbar, ohne dass die Typografie dafuer in ein Element zusammenfallen
            muesste. */}
        <span
          data-testid={`project-photo-count-${project.id}`}
          className="text-sm text-text lg:col-span-2"
        >
          <span className="font-mono">{formatCount(project.photo_count)}</span> Fotos
        </span>

        {/* Die Tonwertstufe haengt am WERT, nicht am Container: eine bekannte Spanne steht in
            `--text`, der Platzhalterstrich in `--text-muted`. Der Strich heisst "keine Angabe" und
            ist ausdruecklich nicht dasselbe wie eine Null - auf der Karte eines ungescannten
            Projekts steht er neben "0 Fotos", und genau dieses Paar traegt den Unterschied
            zwischen einer Aussage und ihrer Abwesenheit. Die ganze Spanne muted zu setzen naehme
            dem echten Wert seine Stufe.

            `data-value-state` ist der semantische Haken fuer den Test (Muster `data-status` an
            StatusTag) - zugesichert wird er, nicht die CSS-Klasse. */}
        <span data-testid={`project-taken-at-${project.id}`} className="text-sm lg:col-span-3">
          <span className="text-text-muted">Aufnahmen</span>{' '}
          <span
            data-value-state={isTakenAtPlaceholder ? 'placeholder' : 'known'}
            className={cn('font-mono', isTakenAtPlaceholder ? 'text-text-muted' : 'text-text')}
          >
            {takenAtRange}
          </span>
        </span>

        <span className="lg:col-span-3">
          <ProjectStandLine stand={deriveProjectStand(project)} projectId={project.id} />
        </span>
      </Link>
    </Card>
  )
}

export function ProjectListPage() {
  const query = useProjectsQuery()

  return (
    <div className="flex flex-col gap-6">
      {/* Der Kopfbereich steht in ALLEN VIER Zustaenden - ein Projekt anlegen zu koennen haengt
          nicht daran, ob die Liste laedt oder scheitert. Nur die Zaehlzeile entfaellt, solange
          keine Zahl bekannt ist. */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl">Projekte</h1>
          {query.isSuccess && query.data.length > 0 && (
            <p className="text-xs text-text-muted">
              {query.data.length} {query.data.length === 1 ? 'Projekt' : 'Projekte'}
            </p>
          )}
        </div>
        <Button asChild>
          <Link to="/projects/new">Neues Projekt anlegen</Link>
        </Button>
      </header>

      {query.isLoading && (
        <ul role="status" aria-label="Projekte werden geladen…" className="flex flex-col gap-3">
          {Array.from({ length: SKELETON_CARD_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              {/* Hoehe aus der Kartenhoehe gemessen: vier Zeilen mobil, eine Rasterzeile ab `lg:`.
                  Ein Platzhalter, der die spaetere Hoehe verfehlt, laesst die Seite beim Eintreffen
                  der Daten springen. */}
              <Skeleton className="h-[136px] w-full rounded-lg lg:h-[72px]" />
            </li>
          ))}
        </ul>
      )}

      {/* Der Fehler ersetzt nur die LISTE, nie die ganze Ansicht. Kuratierter Titel statt des
          nichtssagenden Standardtitels "Fehler"; Beitext ist der woertliche `detail`-Text des
          Servers, ausschliesslich als Textknoten. */}
      {query.isError && (
        <Alert title="Projekte konnten nicht geladen werden" onRetry={() => query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Projekte.'}
        </Alert>
      )}

      {/*
        Leerzustand: Symbol aus dem Zwoelfer-Satz des Boards auf einer erhoehten Flaeche, dazu die
        Zusicherung, dass nur gelesen wird - das ist die Frage, die sich beim ersten Verbinden
        eines Fotoordners tatsaechlich stellt. Der erklaerende Text steht bewusst in `--text` und
        NICHT in `--text-muted`: ein Leerzustand ist die Hauptaussage der Seite, keine
        Metadatenzeile.
      */}
      {query.isSuccess && query.data.length === 0 && (
        // Ein einziger `flex-col gap-4` statt einer Kette einzelner `mb-*`/`mt-*` - der Abstand
        // steht damit an EINER Stelle und kann nicht mehr zwischen den Kindern auseinanderlaufen.
        // Die Schaltflaeche traegt das Board-Standardmass: der Leerzustand ist kein heisser Pfad.
        <div className="flex flex-col items-center gap-4 px-4 py-8 text-center">
          <span
            aria-hidden="true"
            className="grid size-16 place-items-center rounded-md bg-elevated text-accent"
          >
            <Icon name="image" size={40} />
          </span>
          <h2 className="text-lg">Noch nichts sortiert</h2>
          <p className="max-w-xs text-sm text-text">
            Zeig PhotoSort einen Ordner auf dem Cloud-Speicher — den ersten Durchgang übernimmt es
            für dich.
          </p>
          <Button asChild>
            <Link to="/projects/new">Ordner auswählen</Link>
          </Button>
          <p className="text-xs text-text-muted">
            Fotos werden nie kopiert oder verschoben — nur gelesen.
          </p>
        </div>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {query.data.map((project) => (
            <li key={project.id}>
              <ProjectCard project={project} />
            </li>
          ))}
        </ul>
      )}

      {/*
        Namensnennung des Ortsdatensatzes (ADR 0105 Punkt 5): GeoNames steht unter CC BY 4.0, die
        Nennung ist Pflicht und wird sichtbar erfuellt. Sie steht app-weit am Fuss der
        Projektliste - der Einstiegsseite nach der Anmeldung - und damit ausserhalb der
        Arbeitsansichten, und sie haengt NICHT am Ladezustand der Projekte: Die Pflicht besteht,
        weil die Anwendung den Datensatz benutzt, nicht weil gerade etwas angezeigt wird.

        Metadatenzeile in `--text-muted` ueber einer freistehenden Linie auf dem Seitengrund
        (`--separator`) - keine neue Komponente, kein neues Token.
      */}
      <footer className="border-t border-separator pt-4 text-xs text-text-muted">
        Ortsnamen aus{' '}
        <a href="https://www.geonames.org/" className="underline" rel="noreferrer" target="_blank">
          GeoNames
        </a>
        , lizenziert unter{' '}
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          className="underline"
          rel="noreferrer"
          target="_blank"
        >
          CC BY 4.0
        </a>
        .
      </footer>
    </div>
  )
}
