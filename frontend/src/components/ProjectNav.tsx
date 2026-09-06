import { useState } from 'react'
import { Link, useLocation } from 'react-router'

import { cn } from '../lib/utils'
import {
  PROJECT_NAV_TARGETS,
  resolveActiveNavTargetId,
  type ProjectNavTarget,
} from '../utils/projectRoutes'
import { Button } from './ui/button'
import { Icon } from './ui/icon'
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover'

/*
 * Projekt-Navigationsgruppe in der Kopfzeile (specs/features/0298-projektnavigation-in-der-
 * kopfzeile.md, specs/architecture/0004-design-system.md, Muster "Projekt-Navigationsgruppe in der
 * Kopfzeile").
 *
 * ZWEI DARSTELLUNGEN AUS EINER ZIELTABELLE: ab `lg:` die vier Ziele als Leiste, darunter ein
 * Menue-Ausloeser mit Panel. Beide Zweige rendern ueber DENSELBEN internen Baustein
 * (ProjectNavLink) aus PROJECT_NAV_TARGETS - Beschriftung, Sprungziel und Aktiv-Ableitung
 * existieren genau einmal.
 *
 * DER LANDMARK UMSCHLIESST BEIDE ZWEIGE, nicht nur die Leiste (AK3b: genau ein
 * `navigation`-Landmark "Projektbereiche" zu jedem Zeitpunkt UND in jeder Darstellung). Laege das
 * `aria-label` auf dem `hidden lg:flex`-Container, gaebe es unterhalb `lg:` gar keinen Landmark
 * mehr - `display: none` nimmt das Element aus dem Accessibility-Tree. Das Panel bekommt aus
 * demselben Grund KEIN zweites gleichnamiges `<nav>`: zwei gleichnamige Landmarks nebeneinander
 * sind ein Bedienbarkeitsfehler in der Landmark-Liste des Screenreaders.
 *
 * MENUE UEBER DAS VORHANDENE RADIX-POPOVER, NICHT UEBER @radix-ui/react-dropdown-menu: dessen
 * ARIA-`menu`-Muster (`role="menu"`/`menuitem`) naehme den vier Zielen ihre Link-Semantik - sie
 * waeren fuer Screenreader keine Links mehr und tauchten in keiner Linkliste auf. Das Popover
 * liefert ausserdem ohne Zutun alles, was die Akzeptanzkriterien verlangen: Portal mit `z-50`
 * (Panel ueber Kopfzeile und Stepper, beide `z-10`), kollisionsbewusste Platzierung samt
 * Hoehenschranke, Schliessen per Escape/Klick ausserhalb, Fokus ins Panel und zurueck auf den
 * Ausloeser.
 */

/*
 * DIE DREI BOARD-ZUSTAENDE DES NAVIGATIONSELEMENTS - zeichengleich zum Schrittmarker in
 * components/Stepper.tsx (Board-Referenz 0005, Abschnitt 6), nicht neu hergeleitet. Bewusst
 * DATEILOKAL und nicht mit Stepper geteilt: etablierte "erst ab dem dritten Konsumenten
 * auslagern"-Praxis dieses Projekts.
 *
 * Kein `Button`-Wrapper fuer die Ziele, sondern schlichte `<Link>` mit diesem Rezept - aus
 * demselben Grund, aus dem Stepper es so haelt: ruhend/ueberfahren/aktiv sind keine
 * `Button`-Auspraegung, und der Aktiv-Zustand braucht Rand, Schnitt und Farbe GEMEINSAM.
 *
 * `--border-control` statt des rein dekorativen `--border` (Board-Abweichung 2): ein Bedienelement
 * mit `--border` waere auf dunklem Grund unsichtbar. Zu jeder `hover:`-Variante steht eine
 * `active:`-Variante - Tailwind bindet `hover:` an `@media (hover: hover)`, am Telefon ist
 * "gedrueckt" der einzige Zustand, den es ueberhaupt gibt.
 */
const NAV_LINK_BASE_CLASSES =
  'flex items-center rounded-md border px-3 py-2 text-xs font-semibold transition-colors'
const NAV_LINK_ACTIVE_CLASSES = 'border-accent bg-overlay font-bold text-accent'
const NAV_LINK_RESTING_CLASSES =
  'border-border-control bg-surface text-text hover:bg-overlay hover:text-text-h active:bg-border active:text-text'

interface ProjectNavLinkProps {
  target: ProjectNavTarget
  projectId: string
  isActive: boolean
  /**
   * `bar` = Eintrag der Leiste, Trefferflaeche wird per `tap-target` aufgespannt.
   * `row` = Zeile des Panels; hier ist die ZEILE SELBST die Trefferflaeche und traegt `min-h-11`
   * (Design-System-Regel "zeilenweise Listen werden nicht aufgespannt", Vorbild ProjectListPage/
   * CurateCategoriesPage).
   */
  layout: 'bar' | 'row'
  onSelect?: () => void
}

function ProjectNavLink({ target, projectId, isActive, layout, onSelect }: ProjectNavLinkProps) {
  return (
    <Link
      to={target.buildPath(projectId)}
      // Der sichtbare Text IST der zugaengliche Name - bewusst kein zusaetzliches aria-label
      // (AK11b), das sonst still von der Beschriftung abdriften koennte.
      aria-current={isActive ? 'page' : undefined}
      onClick={onSelect}
      className={cn(
        NAV_LINK_BASE_CLASSES,
        layout === 'bar' ? 'tap-target' : 'min-h-11 w-full',
        isActive ? NAV_LINK_ACTIVE_CLASSES : NAV_LINK_RESTING_CLASSES
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
  // zurueckbleibendes Panel ueber der neuen Seite waere ein echter Fehler (AK6).
  const [open, setOpen] = useState(false)

  return (
    <nav aria-label="Projektbereiche" className="flex items-center">
      {/* gap-3 (12px) ist Pflicht, kein Geschmack: die aufgespannten Trefferflaechen ragen bis zu
          6px je Seite ueber das Sichtbare hinaus und duerfen sich nicht ueberlappen - in einer
          Ueberlappung gewinnt das obenliegende Element. */}
      <div className="hidden items-center gap-3 lg:flex">
        {PROJECT_NAV_TARGETS.map((target) => (
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
          {/* `chevron-down` (Board-Bedeutung "Dropdown") statt eines dreizehnten `menu`-Symbols -
              den Zwoelfer-Satz zu erweitern waere eine Design-System-Entscheidung. Kein Import aus
              `lucide-react` hier: der ist ausserhalb von ui/icon.tsx statisch verboten.
              `aria-expanded`/`aria-haspopup` setzt Radix selbst. */}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Projektbereiche"
            className="lg:hidden"
          >
            <Icon name="chevron-down" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-2">
          <ul className="flex flex-col gap-1">
            {PROJECT_NAV_TARGETS.map((target) => (
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
