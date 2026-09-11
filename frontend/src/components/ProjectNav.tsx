import { useState } from 'react'
import { Link, useLocation } from 'react-router'

import { cn } from '../lib/utils'
import {
  isSecondaryNavTargetId,
  PROJECT_NAV_PRIMARY_TARGETS,
  PROJECT_NAV_SECONDARY_TARGETS,
  resolveActiveNavTargetId,
  type ProjectNavTarget,
} from '../utils/projectRoutes'
import { Button } from './ui/button'
import { Icon } from './ui/icon'
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover'

/*
 * Projekt-Navigationsgruppe in der Kopfzeile.
 *
 * EIN AUSLOESER, ZWEI PANEL-INHALTE - AUS EINER ZIELTABELLE IN ZWEI GRUPPEN: ab `lg:` stehen die
 * drei Hauptziele als Leiste, daneben der Ausloeser mit den zwei Nebenzielen im Panel; darunter
 * ist die Leiste ausgeblendet und das Panel fuehrt alle fuenf Ziele in zwei Bloecken. Alle Zweige
 * rendern ueber DENSELBEN internen Baustein (ProjectNavLink) - Beschriftung, Sprungziel und
 * Aktiv-Ableitung existieren genau einmal.
 *
 * GENAU EINE Popover-INSTANZ MIT GENAU EINEM AUSLOESER, unabhaengig von der Breite; der Breakpoint
 * steuert ausschliesslich, welche Teile des Panels dargestellt werden. Der naheliegende
 * Gegenentwurf - zwei Instanzen (eine `lg:hidden` mit allen fuenf, eine `hidden lg:block` mit den
 * zwei Nebenzielen) - ist ausdruecklich abgewaehlt: er legte zwei Buttons mit demselben
 * zugaenglichen Namen ins DOM und machte jede Rollen-Query darauf mehrdeutig (auch in
 * e2e/tests/tap-targets.spec.ts und popover-position.spec.ts, die den Ausloeser bereits
 * ansteuern). Mit einer Instanz ist die Zusage "genau ein Ausloeser" im DOM pruefbar statt nur
 * visuell.
 *
 * DER LANDMARK UMSCHLIESST LEISTE UND AUSLÖSER, nicht nur die Leiste: es muss zu jedem
 * Zeitpunkt und in jeder Darstellung genau EIN `navigation`-Landmark "Projektbereiche"
 * geben. Läge das
 * `aria-label` auf dem `hidden lg:flex`-Container, gaebe es unterhalb `lg:` gar keinen Landmark
 * mehr - `display: none` nimmt das Element aus dem Accessibility-Tree. So bleibt in beiden
 * Darstellungen genau einer uebrig: ab `lg:` umschliesst er die drei sichtbaren Hauptziele samt
 * Ausloeser, darunter den Ausloeser allein.
 *
 * DER PANEL-INHALT LIEGT DAGEGEN AUSSERHALB DIESES `<nav>`: `PopoverContent` wickelt sich in
 * `PopoverPrimitive.Portal` (ui/popover.tsx) und haengt damit an `document.body`, nicht im
 * Komponentenbaum. Ein zweites, gleichnamiges `<nav>` um die Panelzeilen waere die naheliegende
 * Reaktion darauf und ist bewusst NICHT gesetzt: zwei gleichnamige Landmarks nebeneinander sind
 * ein Bedienbarkeitsfehler in der Landmark-Liste des Screenreaders und machten jede Rollen-Query
 * darauf mehrdeutig. Die Panelzeilen bleiben echte `<a>` und damit in jeder Linkliste - was ihnen
 * fehlt, ist ausschliesslich die Landmark-Einordnung.
 *
 * MENUE UEBER DAS VORHANDENE RADIX-POPOVER, NICHT UEBER @radix-ui/react-dropdown-menu: dessen
 * ARIA-`menu`-Muster (`role="menu"`/`menuitem`) naehme den Zielen ihre Link-Semantik - sie waeren
 * fuer Screenreader keine Links mehr und tauchten in keiner Linkliste auf. Verschärft gilt das
 * unterhalb `lg:`: dort liegen ALLE FÜNF Ziele im Panel, die Anwendung hätte auf schmalen
 * Bildschirmen dann ueberhaupt keine Navigationslinks mehr.
 *
 * Das Popover liefert ausserdem ohne Zutun alles, was die Akzeptanzkriterien verlangen: Portal mit
 * `z-50` (Panel ueber Kopfzeile und Stepper, beide `z-10`), kollisionsbewusste Platzierung samt
 * Hoehenschranke, Schliessen per Escape/Klick ausserhalb, Fokus ins Panel und zurueck auf den
 * Ausloeser.
 */

/*
 * DIE DREI BOARD-ZUSTAENDE DES NAVIGATIONSELEMENTS - zeichengleich zum Schrittmarker in
 * components/Stepper.tsx, nicht neu hergeleitet. Bewusst
 * DATEILOKAL und nicht mit Stepper geteilt: etablierte "erst ab dem dritten Konsumenten
 * auslagern"-Praxis dieses Projekts.
 *
 * Kein `Button`-Wrapper fuer die Ziele, sondern schlichte `<Link>` mit diesem Rezept - aus
 * demselben Grund, aus dem Stepper es so haelt: ruhend/ueberfahren/aktiv sind keine
 * `Button`-Auspraegung, und der Aktiv-Zustand braucht Rand, Schnitt und Farbe GEMEINSAM.
 *
 * `--border-control` statt des rein dekorativen `--border`: ein Bedienelement
 * mit `--border` waere auf dunklem Grund unsichtbar. Zu jeder `hover:`-Variante steht eine
 * `active:`-Variante - Tailwind bindet `hover:` an `@media (hover: hover)`, am Telefon ist
 * "gedrueckt" der einzige Zustand, den es ueberhaupt gibt.
 */
const NAV_LINK_BASE_CLASSES =
  'flex items-center rounded-md border px-3 py-2 text-xs font-semibold transition-colors'
const NAV_LINK_ACTIVE_CLASSES = 'border-accent bg-overlay font-bold text-accent'
const NAV_LINK_RESTING_CLASSES =
  'border-border-control bg-surface text-text hover:bg-overlay hover:text-text-h active:bg-border active:text-text'

/*
 * AKTIVSTIL DES GESCHLOSSENEN AUSLÖSERS - ein DRITTES, absichtlich abweichendes Rezept,
 * das der Stepper-Bindung in designSystem.contract.test.ts bewusst NICHT hinzugefuegt wird: ein
 * Symbol-Button ist kein Board-Navigationselement.
 *
 * NICHT FARBE ALLEIN: der ruhende Ghost-Button hat GAR KEINEN Rand - der Rand selbst ist damit der
 * nicht-farbliche Traeger der Aussage, nicht nur seine Farbe.
 */
const NAV_TRIGGER_ACTIVE_CLASSES = 'border border-accent bg-overlay text-accent'

/*
 * TRENNER AM BLOCK DER HAUPTZIELE, NICHT AM BLOCK DER NEBENZIELE: so verschwindet die Linie
 * ab `lg:` automatisch mit dem Block, den sie abtrennt. Ein Trenner am Nebenblock braeuchte eine
 * zweite, gegenlaeufige `lg:`-Regel zum Wieder-Abschalten - eine stille Fehlerquelle.
 *
 * `--separator` STATT `--border` NACH DER BENANNTEN AUSNAHME "Gruppentrenner auf
 * `--elevated`/`--overlay`" des Design-Systems (ebenso am Token in index.css vermerkt):
 * Innerhalb von Panels und Popovern verwenden
 * Gruppengrenzen `--separator`, weil die Flaechenstufe selbst nicht zur Trennung ausreicht und die
 * Regel speziell Kanten ZWISCHEN verschiedenen Flaechen adressiert, nicht Unterteilungen INNERHALB
 * einer Flaeche.
 *
 * AUSDRUECKLICH NICHT die Regel "Linie auf dem Grund" - die trifft hier NICHT zu: das
 * `PopoverContent` steht auf `--elevated`, nicht auf `--bg`/`--surface`. Wer diesem Trugschluss
 * folgt, stellt richtig fest, dass das Panel nicht auf dem Grund steht, und wechselt auf
 * `--border` - das wäre mit 1,04-1,45:1 faktisch keine Linie mehr, und die Trennung trüge dann
 * allein der verdoppelte Abstand. Der Korridor 2,0-2,5 ist auf die beiden Grundflächen
 * kalibriert und gilt
 * fuer diese Verwendung nicht; tragend ist die Zusicherung, dass `--separator` auf JEDER der vier
 * Flaechen sichtbarer bleibt als `--border`.
 *
 * EIGENES LITERAL statt inline im `className`: designSystem.contract.test.ts bindet die Zeile
 * woertlich und sichert damit insbesondere die Token-Wahl `border-separator`.
 */
const PANEL_PRIMARY_GROUP_CLASSES = 'mb-2 border-b border-separator pb-2 lg:hidden'

interface ProjectNavLinkProps {
  target: ProjectNavTarget
  projectId: string
  isActive: boolean
  /**
   * `bar` = Eintrag der Leiste, Trefferflaeche wird per `tap-target` aufgespannt.
   * `row` = Zeile des Panels; hier ist die ZEILE SELBST die Trefferflaeche und traegt `min-h-11`
   * (Design-System-Regel "zeilenweise Listen werden nicht aufgespannt").
   */
  layout: 'bar' | 'row'
  onSelect?: () => void
}

function ProjectNavLink({ target, projectId, isActive, layout, onSelect }: ProjectNavLinkProps) {
  return (
    <Link
      to={target.buildPath(projectId)}
      // Der sichtbare Text IST der zugängliche Name - bewusst kein zusätzliches aria-label,
      // das sonst still von der Beschriftung abdriften könnte.
      aria-current={isActive ? 'page' : undefined}
      onClick={onSelect}
      className={cn(
        NAV_LINK_BASE_CLASSES,
        layout === 'bar' ? 'tap-target' : 'min-h-11 w-full',
        isActive ? NAV_LINK_ACTIVE_CLASSES : NAV_LINK_RESTING_CLASSES,
      )}
    >
      {target.label}
    </Link>
  )
}

export interface ProjectNavProps {
  projectId: string
}

export function ProjectNav({ projectId }: ProjectNavProps) {
  const { pathname } = useLocation()
  const activeTargetId = resolveActiveNavTargetId(pathname)
  // Kontrolliert gehalten: Radix schliesst bei einer Navigation nicht von selbst, ein offen
  // zurückbleibendes Panel über der neuen Seite wäre ein echter Fehler.
  const [open, setOpen] = useState(false)

  const isSecondaryActive = isSecondaryNavTargetId(activeTargetId)

  return (
    <nav aria-label="Projektbereiche" className="flex items-center gap-3">
      {/* gap-3 (12px) ist Pflicht, kein Geschmack: die aufgespannten Trefferflaechen ragen bis zu
          6px je Seite ueber das Sichtbare hinaus und duerfen sich nicht ueberlappen - in einer
          Überlappung gewinnt das obenliegende Element. Ab `lg:` steht auch der Auslöser
          unmittelbar neben "Vergleich", deshalb trägt der <nav> denselben Abstand. */}
      <div className="hidden items-center gap-3 lg:flex">
        {PROJECT_NAV_PRIMARY_TARGETS.map((target) => (
          <ProjectNavLink
            key={target.id}
            target={target}
            projectId={projectId}
            isActive={target.id === activeTargetId}
            layout="bar"
          />
        ))}
      </div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          {/* `chevron-down` (Board-Bedeutung "Dropdown") statt eines dreizehnten `menu`- oder
              `ellipsis`-Symbols - den Zwoelfer-Satz zu erweitern waere eine Design-System-
              Entscheidung. Kein Import aus `lucide-react` hier: der ist ausserhalb von ui/icon.tsx
              statisch verboten. `aria-expanded`/`aria-haspopup` setzt Radix selbst.

              `aria-current="true"` und nicht `"page"`: der Ausloeser ist kein Link auf die
              aktuelle Seite, aber sehr wohl "das aktuelle Element innerhalb der Menge" im Sinne
              der ARIA-Definition. Die Panelzeile behaelt daneben ihr `aria-current="page"`.

              Der zugaengliche Name bleibt routenunabhaengig "Projektbereiche": ein Bedienelement,
              dessen Name mit der Route wandert, ist desorientierend und braeche die stabilen
              Lokalisierer in tap-targets.spec.ts/popover-position.spec.ts. Ein per `lg:`-Klassen
              umgeschaltetes Doppel-`sr-only`-Paar ist ebenso verboten - in jsdom greift Tailwind
              nicht, der zugaengliche Name waere dort die Verkettung beider Texte. */}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Projektbereiche"
            aria-current={isSecondaryActive ? 'true' : undefined}
            className={cn(isSecondaryActive && NAV_TRIGGER_ACTIVE_CLASSES)}
          >
            <Icon name="chevron-down" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-2">
          {/* ZWEI <ul> STATT EINER LISTE MIT TRENNELEMENT: die drei Hauptzeilen brauchen ohnehin
              einen gemeinsamen `lg:hidden`-Container (sonst truege jede Zeile die Klasse einzeln),
              und genau dieser gemeinsame Vorfahre ist die in jsdom prüfbare Struktur der
              Gruppentrennung.
              Ein `role="group"` oder ein Label kommt ausdruecklich NICHT hinzu: der Panelinhalt
              liegt im Portal ausserhalb des Landmarks, eine Gruppe braeuchte selbst eine
              Ankuendigung, und ab `lg:` bliebe sie eine sinnlose Ein-Gruppen-Struktur. */}
          <ul className={cn('flex flex-col gap-1', PANEL_PRIMARY_GROUP_CLASSES)}>
            {PROJECT_NAV_PRIMARY_TARGETS.map((target) => (
              <li key={target.id}>
                <ProjectNavLink
                  target={target}
                  projectId={projectId}
                  isActive={target.id === activeTargetId}
                  layout="row"
                  onSelect={() => setOpen(false)}
                />
              </li>
            ))}
          </ul>
          <ul className="flex flex-col gap-1">
            {PROJECT_NAV_SECONDARY_TARGETS.map((target) => (
              <li key={target.id}>
                <ProjectNavLink
                  target={target}
                  projectId={projectId}
                  isActive={target.id === activeTargetId}
                  layout="row"
                  onSelect={() => setOpen(false)}
                />
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </nav>
  )
}
