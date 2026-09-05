import {
  Book,
  Camera,
  Check,
  ChevronDown,
  CircleX,
  Cog,
  Folder,
  Image as ImageIcon,
  Info,
  Search,
  Star,
  Tag,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/*
 * Der Zwoelfer-Symbolsatz des Boards (specs/architecture/0005-board-dark-utility-register.md
 * Abschnitt 7, decisions/0055-dark-utility-register-fundament.md Punkt 7).
 *
 * DIES IST DIE EINZIGE DATEI IM PROJEKT, DIE AUS `lucide-react` IMPORTIEREN DARF - statisch
 * erzwungen in src/designSystem.contract.test.ts. Gruende:
 *  1. Die Aufrufstellen waehlen ihr Symbol DATENGETRIEBEN (RatingBadge's Record,
 *     CloudVisionStatusList's Status-Tabelle) - ein String-Name ist dort der Eins-zu-eins-Ersatz
 *     fuer das frueher verwendete Sonderzeichen, eine Komponenten-Referenz waere eine Umschreibung.
 *  2. Umbenennungen im Paket (x-circle -> circle-x) und Namenskollisionen (Image) bleiben auf eine
 *     Datei begrenzt.
 *  3. Ein spaeterer Ausstieg aus dem Paket waere eine reine Innensache dieser Datei.
 *
 * TREE-SHAKING IST BEDINGUNG, NICHT KOSMETIK: `lucide-react` ist entpackt rund 32 MB (ein Modul je
 * Symbol). Nur BENANNTE Importe in einem STATISCHEN Objektliteral halten die tatsaechlich
 * ausgelieferte Menge bei zwoelf Pfad-Definitionen. Ein Namespace-Import (`import * as icons`)
 * oder ein berechneter Zugriff auf das Paket-Objekt zoege den vollen Satz ins Bundle - bei einer
 * PWA mit Mobilfunk-Nutzung ist das die Bedingung, unter der diese Abhaengigkeit vertretbar ist.
 *
 * Alle zwoelf Board-SVGs sind nachgewiesenermassen Lucide-Pfade (ADR 0055 Punkt 7a) - der
 * Figma-Export hat lediglich Boegen in kubische Beziers aufgeloest und `star` gegenlaeufig
 * gezeichnet. Es gibt damit keine Geometrie-Abweichung zwischen Board und Paket.
 *
 * Der Satz wird NICHT stillschweigend erweitert. Die fuenf dokumentierten Luecken (`x` Schliessen,
 * `✎` Uebersteuerungs-Marker, `○` "nicht gelaufen", `●●○` Qualitaetsmesser, `–` unbewertet)
 * bleiben Textzeichen bzw. bestehende Komponenten - sie mit beliebigen weiteren Lucide-Symbolen zu
 * fuellen waere eine Gestaltungsentscheidung ohne Vorlage.
 */
const ICONS = {
  star: Star,
  book: Book,
  // Lucide hat das Symbol zu `circle-x` umbenannt; `XCircle` ist nur noch der Alt-Alias. Gegen die
  // installierte Version geprueft (icon.test.tsx), nicht geraten.
  'x-circle': CircleX,
  // Nicht `Settings`: die Board-Pfaddaten sind die des sechsspeichigen `cog`.
  cog: Cog,
  // `Image` kollidiert mit dem DOM-Global - deshalb umbenannt importiert.
  image: ImageIcon,
  check: Check,
  info: Info,
  'chevron-down': ChevronDown,
  search: Search,
  folder: Folder,
  camera: Camera,
  tag: Tag,
} as const satisfies Record<string, LucideIcon>

export type IconName = keyof typeof ICONS

/** Die zwoelf Namen als Laufzeitwert - Grundlage der parametrisierten Tests, damit ein neues
 * Symbol nicht ungeprueft hinzukommen kann. */
export const ICON_NAMES = Object.keys(ICONS) as readonly IconName[]

export interface IconProps {
  name: IconName
  /** Board-Groessen: 14 / 16 / 18 / 24. */
  size?: number
  /** Nur fuer den seltenen Alleinstand ohne begleitendes Label - schaltet das Symbol von
   * dekorativ auf `role="img"` mit Textalternative um. */
  title?: string
  className?: string
}

export function Icon({ name, size = 16, title, className }: IconProps) {
  const LucideComponent = ICONS[name]
  const labelled = title !== undefined

  return (
    <LucideComponent
      // Semantischer Haken im Stil der bestehenden data-suggested/data-status-Konvention: die
      // Tests selektieren darueber statt ueber einen Klassennamen und ueberleben damit die
      // gestalterische Ueberarbeitung der Ansichten (Stufe 2, Issue #321).
      data-icon={name}
      width={size}
      height={size}
      // Board-Strichstaerke, zentral statt an jeder Aufrufstelle wiederholt.
      strokeWidth={2}
      // Einfaerbung ueber currentColor (Lucide-Default) - das Symbol erbt die Textfarbe seiner
      // Umgebung und faellt damit automatisch in dieselbe Kontrastrechnung wie der Text daneben.
      aria-hidden={labelled ? undefined : true}
      focusable="false"
      role={labelled ? 'img' : undefined}
      aria-label={title}
      className={className}
    />
  )
}
