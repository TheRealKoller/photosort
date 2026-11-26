// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Abstands- und Wertskalen.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts .
 */

import { describe, expect, it } from 'vitest'

import {
  allowlistedOccurrences,
  type AllowlistEntry,
  escapeForRegExp,
  findMatches,
  productionTsxFiles,
  sourceFiles,
} from './test/designSystemScan'

// ---------------------------------------------------------------------------------------------
// Abstands- und Wertskalen (specs/features/0321-dark-utility-register-ansichten.md, "Das Netz")
// ---------------------------------------------------------------------------------------------

/**
 * Zerlegt eine Quellzeile in Utility-Kandidaten. Bewusst tokenweise statt ueber einen einzigen
 * grossen regulaeren Ausdruck: Klassenlisten stehen in Zeichenketten, Template-Teilen und
 * `cn()`-Argumenten, und ein Ausdruck mit Wortgrenzen faengt dort zuverlaessig Fehlalarme
 * (`max-w-5xl` als `w-5`) statt Treffer.
 */
function classTokens(line: string): string[] {
  // Bewusst NICHT an Klammern, Kommas oder Schraegstrichen getrennt: `w-[min(32rem,calc(100vw-
  // 2rem))]`, `aspect-[4/3]` und `bg-bg/95` sind je EIN Token. Getrennt wird an dem, was eine
  // Klassenliste im Quelltext tatsaechlich begrenzt.
  return line.split(/[\s'"`{}=;<>]+/).filter((token) => token.length > 0)
}

/**
 * Entfernt die Variantenpraefixe eines Utility-Tokens und liefert die reine Utility. Arbiträre
 * VARIANTEN (`[&::-webkit-progress-bar]:`, `data-[state=open]:`, `has-[:disabled]:`) tragen
 * ebenfalls eckige Klammern, sind aber KEINE willkuerlichen Werte - ohne dieses Abstreifen waeren
 * sie dauerhafte Fehlalarme der Regel "keine willkuerlichen Werte".
 */
function utilityBase(token: string): string {
  let rest = token
  for (;;) {
    const match = /^(?:\[[^\]]*\]|[a-z0-9-]+(?:\[[^\]]*\])?):([\s\S]*)$/.exec(rest)
    if (match === null) {
      return rest
    }
    rest = match[1]
  }
}

/*
 * REGEL 1 - ABSTANDSSKALA. Die acht Stufen des 8-Punkt-Rasters plus die Null. `auto` bleibt
 * zulaessig: es ist ein Schluesselwort (`m-auto` zentriert den Dialog), keine Abstandsstufe.
 *
 * DIES IST EINE ABSTANDS-, KEINE GROESSENREGEL. `h-11`, `size-8`, `h-0.5`, `min-w-6`, `w-full` und
 * `max-w-5xl` sind ausdruecklich nicht betroffen - ein Fehlalarm dort zwingt die Umsetzung dazu,
 * die Regel wieder aufzuweichen.
 */
const SPACING_UTILITIES = [
  'gap-x',
  'gap-y',
  'space-x',
  'space-y',
  'gap',
  'px',
  'py',
  'pt',
  'pr',
  'pb',
  'pl',
  'p',
  'mx',
  'my',
  'mt',
  'mr',
  'mb',
  'ml',
  'm',
]
const SPACING_SCALE = new Set(['0', '1', '2', '3', '4', '6', '8', '12', '16', 'auto'])
const SPACING_PATTERN = new RegExp(`^-?(${SPACING_UTILITIES.join('|')})-(.+)$`)

/** Alle Abstands-Utilities einer Zeile - Grundlage der Positiv-Gegenprobe. */
function spacingUtilities(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => SPACING_PATTERN.test(base))
}

/** Abstands-Utilities einer Zeile, die NICHT auf der Skala liegen. */
function offendingSpacingUtilities(line: string): string[] {
  return spacingUtilities(line).filter((base) => {
    const value = SPACING_PATTERN.exec(base)?.[2] ?? ''
    return !SPACING_SCALE.has(value)
  })
}

/*
 * REGEL 2 - KEINE WILLKUERLICHEN WERTE. Ein willkuerlicher Wert umgeht jede Skala des
 * Design-Systems, ohne dass irgendetwas rot wird. Arbiträre VARIANTEN bleiben zulaessig (siehe
 * `utilityBase`).
 */
function arbitraryValues(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => /^-?[a-z0-9-]+-\[[^\]]*\]$/.test(base))
}

/*
 * REGEL 3 - KEINE DECKKRAFT-MODIFIKATOREN AUF FARB-UTILITIES. Zwei Fehlerklassen in einer: Der
 * Kontrast einer abgedunkelten Farbe ist statisch nicht nachrechenbar, und genau so verschwinden
 * die Trennlinien auf dem Grund (`border-border/60` liegt bei 0.87:1).
 *
 * Der Erkenner ist an die FARB-NAMENSRAEUME gebunden, nicht an das Vorkommen eines Schraegstrichs -
 * `w-1/2`, `h-1/3` und `basis-1/2` sind Brueche, keine Deckkraft.
 */
const COLOR_UTILITY_ROOTS = [
  'bg',
  'text',
  'border',
  'fill',
  'stroke',
  'ring',
  'outline',
  'divide',
  'decoration',
  'placeholder',
  'caret',
  'shadow',
]
const COLOR_OPACITY_PATTERN = new RegExp(`^(${COLOR_UTILITY_ROOTS.join('|')})-[a-z0-9-]+/\\d+$`)

function colorOpacityModifiers(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => COLOR_OPACITY_PATTERN.test(base))
}

/*
 * REGEL 5 - KEINE BILDFLAECHE WIRD GEDAEMPFT (ADR 0112). Auf einer Bildflaeche liegt keine
 * Daempfung, in keiner Ansicht, und kein anderes bildveraenderndes Mittel tritt an ihre Stelle:
 * Eine gedaempft dargestellte Aufnahme verfaelscht die Beurteilung des Motivs, und ueberall dort,
 * wo die Daempfung sass, wird beurteilt. Der Zustand einer Aufnahme haengt stattdessen an
 * Kennzeichen, Rahmen, Punkt und durchgestrichenem Dateinamen - alle ausserhalb der Bildflaeche.
 *
 * SECHS FILTER-MUSTER plus das MISCHMODUS-Muster treten neben `opacity-`: Ein `grayscale` oder
 * `brightness-50` erreichte dasselbe Ergebnis, ohne dass Regel 4 anschlueg.
 */
const FILTER_PREFIX_UTILITIES = ['brightness', 'contrast', 'saturate', 'mix-blend']
const FILTER_BARE_UTILITIES = ['grayscale', 'invert', 'sepia']

/** Ein Utility in TAILWIND-KLASSENFORM, verankert an beiden Enden. Nie als Teilzeichenkette: Sonst
 * traefe der Erkenner den Bezeichner `inverted`, das `animate-pulse` des Bildskeletts und - bei
 * einem spaeter erweiterten Suchraum - den CSS-Wert in `-moz-osx-font-smoothing: grayscale`. */
function utilityPattern(prefixed: string[], bare: string[]): RegExp {
  const alternatives = [
    ...(prefixed.length > 0 ? [`(?:${prefixed.join('|')})-\\S+`] : []),
    ...(bare.length > 0 ? [`(?:${bare.join('|')})(?:-\\S+)?`] : []),
  ]
  return new RegExp(`^(?:${alternatives.join('|')})$`)
}

const FILTER_PATTERN = utilityPattern(FILTER_PREFIX_UTILITIES, FILTER_BARE_UTILITIES)
const DIMMING_PATTERN = utilityPattern(
  ['opacity', ...FILTER_PREFIX_UTILITIES],
  FILTER_BARE_UTILITIES,
)

/**
 * Die Treffer einer Zeile zu einem der beiden Muster.
 *
 * Ein WERT EINER CSS-DEKLARATION ist kein Utility und wird ausgenommen: Dort folgt der Name auf
 * einen Doppelpunkt MIT Leerraum (`-moz-osx-font-smoothing: grayscale`), waehrend eine
 * Tailwind-Variante ohne Leerraum anschliesst (`hover:grayscale`).
 */
function matchingUtilities(pattern: RegExp, line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => pattern.test(base))
    .filter((base) => !new RegExp(`:\\s+${escapeForRegExp(base)}\\b`).test(line))
}

/** `opacity-*` samt Filtern und Mischmodi - der volle Satz fuer die bildtragenden Dateien. */
function imageDimmingUtilities(line: string): string[] {
  return matchingUtilities(DIMMING_PATTERN, line)
}

/** Nur Filter und Mischmodi - der Satz fuer alle uebrigen Produktivdateien. */
function filterUtilities(line: string): string[] {
  return matchingUtilities(FILTER_PATTERN, line)
}

describe('Design-Vertrag: Abstands- und Wertskalen', () => {
  /*
   * Jeder der vier Erkenner wird TABELLENGETRIEBEN gegen synthetische Zeilen geprueft, bevor er
   * produktiv laeuft. Eine statische Pruefung hat genau einen ernsten Fehlermodus: Sie findet
   * nichts und besteht deswegen. Ein kaputter regulaerer Ausdruck faellt hier auf, statt still
   * alles durchzuwinken.
   */
  it.each([
    'gap-1.5',
    'gap-2.5',
    'gap-3.5',
    'py-3.5',
    'px-5',
    'mt-5',
    'py-10',
    'px-10',
    'p-0.5',
    'mb-7',
    'sm:gap-1.5',
    'hover:py-3.5',
    '-mt-5',
  ])('erkennt %s als Abstand ausserhalb der Skala', (utility) => {
    expect(offendingSpacingUtilities(`className="${utility} flex"`)).not.toEqual([])
  })

  it.each([
    'p-0',
    'gap-1',
    'p-2',
    'gap-3',
    'p-4',
    'py-6',
    'px-8 py-8',
    'mb-12',
    'mt-16',
    'm-auto',
    'h-11',
    'size-8',
    'h-0.5',
    'min-w-6',
    'w-full',
    'max-w-5xl',
    'size-2.5',
    'translate-x-0.5',
    'text-2xl',
    'w-1/2',
  ])('erkennt %s NICHT als Abstandsverstoss', (utility) => {
    expect(offendingSpacingUtilities(`className="${utility} flex"`)).toEqual([])
  })

  it.each(['text-[10px]', 'text-[10.5px]', 'h-[50px]', 'w-[240px]', 'gap-[3px]', 'p-[7px]'])(
    'erkennt %s als willkuerlichen Wert',
    (utility) => {
      expect(arbitraryValues(`className="${utility}"`)).toEqual([utility])
    },
  )

  it.each([
    '[&::-webkit-progress-bar]:bg-accent',
    'indeterminate:[&::-moz-progress-bar]:bg-transparent',
    'data-[state=open]:flex',
    'has-[:disabled]:text-text-disabled',
    'text-xs',
    'aspect-square',
  ])('erkennt %s NICHT als willkuerlichen Wert', (utility) => {
    expect(arbitraryValues(`className="${utility}"`)).toEqual([])
  })

  it.each(['border-border/60', 'bg-border/60', 'text-text/70', 'bg-black/60', 'hover:bg-bg/95'])(
    'erkennt %s als Deckkraft-Modifikator auf einer Farb-Utility',
    (utility) => {
      expect(colorOpacityModifiers(`className="${utility}"`)).not.toEqual([])
    },
  )

  it.each(['w-1/2', 'h-1/3', 'basis-1/2', 'bg-border', 'aspect-[4/3]'])(
    'erkennt %s NICHT als Deckkraft-Modifikator',
    (utility) => {
      expect(colorOpacityModifiers(`className="${utility}"`)).toEqual([])
    },
  )

  // -----------------------------------------------------------------------------------------
  // Die Regeln selbst
  // -----------------------------------------------------------------------------------------

  it('haelt jede Abstands-Utility auf den acht Stufen des 8-Punkt-Rasters', () => {
    expect(allowlistedOccurrences(offendingSpacingUtilities, [], productionTsxFiles())).toEqual([])
    // Positiv-Gegenprobe: Die Kandidatenmenge ist nachweislich gross - die Regel laeuft nicht
    // gegen eine leere Menge und bestuende deshalb auch bei kaputtem Erkenner.
    expect(findMatches(spacingUtilities, productionTsxFiles()).length).toBeGreaterThan(100)
  })

  const ARBITRARY_VALUE_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/popover.tsx',
      snippet: "'z-50 max-h-[min(60vh,var(--radix-popover-content-available-height))] w-72",
      reason:
        'Hoehendeckel des Popover-Panels: Minimum aus der Board-Schranke 60vh und dem von Radix ' +
        'gemessenen verfuegbaren Platz - keine Rasterstufe moeglich',
    },
    {
      file: 'src/components/ui/checkbox.tsx',
      snippet: "'size-[18px] shrink-0",
      reason: 'abgeleitetes Board-Mass des Kontrollkaestchens (zwischen size-4 und size-5)',
    },
    {
      file: 'src/components/ui/dialog.tsx',
      snippet: "'m-auto w-[min(32rem,calc(100vw-2rem))]",
      reason: 'Dialogbreite: Board-Mass, aber nie breiter als das Sichtfenster abzueglich Rand',
    },
    {
      file: 'src/components/ui/input.tsx',
      snippet: "'focus:border-[1.5px] focus:border-accent'",
      reason: 'Fokusstaerkung des Feldrands - 1.5px liegt auf keiner Tailwind-Randstufe',
    },
    {
      file: 'src/components/PhotoDetailStage.tsx',
      snippet: 'className="flex h-[calc(100dvh-var(--spacing-header)-var(--spacing)*6)] flex-col',
      reason:
        'Hoehe der Buehne: sichtbare Hoehe abzueglich Kopfzeile und des oberen Innenabstands der ' +
        'Inhaltsspalte (py-6 an main). Fotoflaeche, Bewertungsleiste und Navigation muessen ' +
        'zusammen ohne Scrollen im Sichtfenster liegen - das ist eine Rechnung ueber dem ' +
        'Sichtfenster und keine Rasterstufe. Die Kopfzeilenhoehe kommt aus demselben ' +
        '--spacing-header, aus dem h-header/top-header entstehen; ein zweiter Zahlenwert dafuer ' +
        'ist verboten. Weder eine in JavaScript gemessene Hoehe im Inline-Stil noch eine ' +
        'CSS-Custom-Property als Traeger eines gerechneten Wertes waeren ein zulaessiger Ausweg - ' +
        'beides ist im Sicherheitskonzept untersagt',
    },
    {
      file: 'src/pages/ProjectListPage.tsx',
      snippet: 'className="h-[136px] w-full rounded-lg lg:h-[72px]"',
      reason:
        'Platzhalterhoehe der Projektkarte, aus der tatsaechlichen Kartenhoehe gemessen (vier ' +
        'Zeilen mobil, eine Rasterzeile ab lg:) - ein Platzhalter auf der naechsten Rasterstufe ' +
        'liesse die Seite beim Eintreffen der Daten springen. Ausgewiesene Luecke der Spec 0375',
    },
  ]

  it('verwendet willkuerliche Werte nur an der begruendeten Liste', () => {
    expect(
      allowlistedOccurrences(arbitraryValues, ARBITRARY_VALUE_ALLOWLIST, productionTsxFiles()),
    ).toEqual([])
    // Positiv-Gegenprobe: Die Regel laeuft nicht gegen eine leere Kandidatenmenge.
    expect(findMatches(arbitraryValues, productionTsxFiles()).length).toBeGreaterThan(0)
  })

  const COLOR_OPACITY_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/dialog.tsx',
      snippet: "'backdrop:bg-black/60'",
      reason: 'Abdunklung des Hintergrunds hinter dem Modal - kein Vorder-/Hintergrundpaar',
    },
    {
      file: 'src/components/CurationLightbox.tsx',
      snippet: "'backdrop:bg-bg/72'",
      reason:
        'Abdunklung der Kuratierung hinter der Grossansicht - Deckkraft 0.72 ueber --bg (Entwurf)',
    },
    {
      file: 'src/components/Stepper.tsx',
      snippet: 'border-b border-separator bg-bg/95',
      reason: 'durchscheinende sticky Kopfzeile der Schrittnavigation',
    },
  ]

  it('verwendet Deckkraft-Modifikatoren auf Farb-Utilities nur an der begruendeten Liste', () => {
    expect(
      allowlistedOccurrences(colorOpacityModifiers, COLOR_OPACITY_ALLOWLIST, productionTsxFiles()),
    ).toEqual([])
    // Positiv-Gegenprobe: Die drei freigegebenen Abdunklungen werden tatsaechlich gefunden.
    expect(findMatches(colorOpacityModifiers, productionTsxFiles()).length).toBeGreaterThan(0)
  })

  /*
   * REGEL 4 - `opacity-*` FUNDSTELLENGENAU. Die Liste fuehrt ausschliesslich ZUSTAENDE VON
   * BEDIENELEMENTEN (deaktiviert, ueberfahren, gedrueckt); kein Eintrag nennt eine Bildflaeche.
   * Jedes nicht freigegebene `opacity-`-Vorkommen in einer Produktions-`.tsx` ist rot.
   *
   * DIE ORTSREGEL (ADR 0112): Entstuende je wieder eine Daempfung an einer Foto-Kachel, saesse sie
   * auf der BILDFLAECHE und nie am Kachel- oder Kartenkoerper - dort druecke dieselbe Utility
   * Kennzeichen und Dateinamen unter die Kontrastschwelle. Ueber einer Bildflaeche selbst ist ein
   * Kontrast mit Deckkraft statisch ohnehin nicht nachrechenbar. Die Regel gilt weiter, hat aber
   * keinen Gegenstand mehr: Regel 5 schliesst jede Daempfung auf einer Bildflaeche bereits aus.
   *
   * Diese Regel ist ein FREIGABE-, kein Verbotsmechanismus - wer eine Bildflaeche wieder daempfen
   * wollte, koennte hier einen Eintrag mit Begruendung nachtragen. Genau deshalb steht Regel 5
   * daneben, die keine Ausnahme kennt.
   */
  const OPACITY_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'disabled:text-text-disabled disabled:opacity-40',
      reason: 'deaktivierte Schaltflaeche - WCAG nimmt inaktive Bedienelemente ausdruecklich aus',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'bg-accent text-accent-fg hover:opacity-85 active:opacity-70',
      reason: 'Ueberfahren/Gedrueckt der primaeren Schaltflaeche - Flaeche bleibt, nur Deckkraft',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: "'border border-border-control bg-overlay text-text-h hover:opacity-80",
      reason: 'Ueberfahren der sekundaeren Schaltflaeche (zwei Auspraegungen, gleiche Zeile)',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: "isDisabledSlot && 'pointer-events-none opacity-40'",
      reason: 'deaktivierter asChild-Link - traegt kein natives disabled-Attribut',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'bg-danger text-danger-fg hover:opacity-85 active:opacity-70',
      reason:
        'Ueberfahren/Gedrueckt der zerstoererischen Schaltflaeche - zeichengleich zur primaeren',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-favorite-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Favorit)',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-album-worthy-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Album-wuerdig)',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-rejected-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Verwerfen)',
    },
  ]

  it('verwendet opacity-* nur an der begruendeten Liste, fundstellengenau', () => {
    expect(allowlistedOccurrences('opacity-', OPACITY_ALLOWLIST, productionTsxFiles())).toEqual([])
    // Positiv-Gegenprobe: Die Regel laeuft nicht gegen eine leere Kandidatenmenge - sonst bestuende
    // sie auch dann, wenn der Suchbegriff nichts mehr faende.
    expect(findMatches('opacity-', productionTsxFiles()).length).toBeGreaterThan(0)
  })

  // -----------------------------------------------------------------------------------------
  // Regel 5 - keine Bildflaeche wird gedaempft (ADR 0112, Spec 0498 AK3)
  // -----------------------------------------------------------------------------------------

  it.each([
    'opacity-40',
    'opacity-85',
    'hover:opacity-85',
    'grayscale',
    'grayscale-50',
    'invert',
    'sepia',
    'brightness-50',
    'contrast-125',
    'saturate-0',
    'mix-blend-multiply',
    'sm:mix-blend-overlay',
  ])('erkennt %s als bildveraenderndes Utility', (utility) => {
    expect(imageDimmingUtilities(`className="${utility} size-full"`)).toEqual([
      utilityBase(utility),
    ])
  })

  it.each([
    'inverted',
    'animate-pulse',
    'object-contain',
    'invertiert',
    'bg-invert',
    'sepiafarben',
    'text-contrast',
    '-moz-osx-font-smoothing: grayscale;',
  ])('erkennt %s NICHT als bildveraenderndes Utility', (line) => {
    expect(imageDimmingUtilities(line)).toEqual([])
  })

  it.each(['grayscale', 'invert', 'sepia', 'brightness-50', 'contrast-125', 'mix-blend-multiply'])(
    'erkennt %s als Filter-/Mischmodus-Utility',
    (utility) => {
      expect(filterUtilities(`className="${utility}"`)).toEqual([utility])
    },
  )

  it('zaehlt opacity-* NICHT zu den Filtern - dort gilt die Freigabeliste der Regel 4', () => {
    // Sonst waere jede Schaltflaeche mit `hover:opacity-85` ueber die zweite, ausnahmefreie Regel
    // rot, und die begruendete Freigabe der Bedienelement-Zustaende liefe ins Leere.
    expect(filterUtilities('className="hover:opacity-85"')).toEqual([])
  })

  /**
   * Die bildtragenden Produktivdateien: ABGELEITET statt aufgezaehlt - jede Produktions-`.tsx`,
   * die `PhotoImage` nennt. Eine neue bildtragende Komponente faellt damit ohne Zutun unter die
   * Regel, waehrend eine abgeschriebene Liste beim naechsten Zuwachs still unvollstaendig waere.
   *
   * Bewusst am ROHEN Inhalt, nicht am kommentarfreien: In `PhotoCard` und `PhotoGridTile` steht
   * der Name ausschliesslich im Doku-Block der `image`-Prop - beide fielen sonst heraus, und das
   * sind genau die beiden Dateien, um die es hier geht.
   */
  function imageBearingFiles(): typeof sourceFiles {
    return productionTsxFiles().filter((file) => file.content.includes('PhotoImage'))
  }

  it('daempft in keiner bildtragenden Datei die Bildflaeche - ohne Ausnahmemoeglichkeit', () => {
    const files = imageBearingFiles()

    // Gegenprobe auf eine nicht leere Kandidatenmenge, OHNE ihre Maechtigkeit festzuschreiben:
    // Eine neue bildtragende Datei soll in die Regel fallen, nicht die Gegenprobe rot faerben.
    expect(files.length).toBeGreaterThan(0)
    // ... und die Ableitung erfasst tatsaechlich die Kacheln und Bildflaechen, um die es geht.
    // Ohne diese Zeile bliebe unbemerkt, dass sie am Kern vorbeigreift, solange sie irgendetwas
    // findet.
    const labels = files.map((file) => file.label)
    for (const kachel of [
      'PhotoCard',
      'PhotoGridTile',
      'DuplicatePhotoTile',
      'DuplicateEnlargedView',
      'DuplicateStackTile',
    ]) {
      expect(labels).toContain(`src/components/${kachel}.tsx`)
    }

    // KEINE Freigabeliste - anders als Regel 4 ist das ein Verbot, kein Freigabemechanismus.
    expect(allowlistedOccurrences(imageDimmingUtilities, [], files)).toEqual([])
  })

  /*
   * Die zweite Regel, ueber ALLE Produktiv-`.tsx`. Grund: Die abgeleitete Menge oben erfasst die
   * drei Seiten nicht, die eine Foto-Kachel rendern, ohne `PhotoImage` selbst zu nennen
   * (`AlbumDraftPage`, `AlbumSelectionPage`, `DuplicateComparePage`). Filter und Mischmodus wirken
   * von JEDEM Vorfahren auf das Kind - ein `<div className="grayscale">` um die Kachel liefe sonst
   * durch. `opacity-*` bleibt hier aussen vor: dafuer gibt es Regel 4 mit ihrer begruendeten
   * Freigabe der Bedienelement-Zustaende.
   *
   * Die Liste ist HEUTE LEER und kostet gemessen nichts - es gibt kein Vorkommen dieser Muster in
   * einer Produktiv-`.tsx`. Sie steht trotzdem als Liste da, damit ein kuenftiger Bedarf eine
   * fundstellengenaue Begruendung verlangt statt einer Regelaufweichung.
   */
  const FILTER_ALLOWLIST: AllowlistEntry[] = []

  it('verwendet in keiner Produktivdatei ein Filter- oder Mischmodus-Utility', () => {
    const files = productionTsxFiles()

    expect(files.length).toBeGreaterThan(0)
    expect(allowlistedOccurrences(filterUtilities, FILTER_ALLOWLIST, files)).toEqual([])
  })

  it('meldet ein Filter-Utility an einer synthetischen Produktivdatei', () => {
    // Die Regel oben laeuft ueber eine leere TREFFERmenge - sie bestuende deshalb auch mit einem
    // stillgelegten Erkenner. Hier wird sie einmal im roten Zustand gesehen, an einer literal
    // geschriebenen Datei statt am Bestand.
    const problems = allowlistedOccurrences(filterUtilities, FILTER_ALLOWLIST, [
      { label: 'src/pages/Irgendeine.tsx', content: '<div className="grayscale">{kachel}</div>' },
    ])

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('src/pages/Irgendeine.tsx')
  })

  /*
   * `h-11`/`min-h-11` ist seit ADR 0055 Punkt 8 die AUSNAHME, nicht die Regel: Bedienelemente sind
   * sichtbar 32px hoch und beziehen ihre 44px aus der Aufspannung. Sichtbare 44px sind nur in drei
   * Faellen richtig - heisser Pfad, Zeilenhoehe zeilenweiser Listen, und Eingabefelder/
   * Kontrollkaestchen (ein ersetztes Element traegt keine Pseudo-Elemente und loest seine
   * Trefferflaeche ausschliesslich ueber die sichtbare Zeilenhoehe).
   */
  const TALL_CONTROL_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: "const HOT_PATH_HEIGHT = 'h-11 sm:h-8'",
      reason: 'heisser Pfad: ein Fehlgriff schreibt hier einen falschen Datenwert',
    },
    {
      file: 'src/components/ui/input.tsx',
      snippet: "'h-11 w-full rounded-sm",
      reason: 'Eingabefeld: ersetztes Element ohne Pseudo-Element, Trefferflaeche = Zeilenhoehe',
    },
    {
      file: 'src/components/ui/checkbox.tsx',
      snippet: 'inline-flex min-h-11 cursor-pointer',
      reason: 'Kontrollkaestchen samt Beschriftung: dieselbe Begruendung wie beim Eingabefeld',
    },
    {
      file: 'src/components/ModelChoiceSection.tsx',
      snippet: 'flex min-h-11 cursor-pointer flex-col justify-center gap-1',
      reason:
        'Modellwahl-Zeile (Spec 0383): Radio samt Taetigkeitsbeschriftung, Grund und Herkunft in ' +
        'einer klickbaren Zeile - dieselbe Trefferflaeche wie die Laufwahl darueber.',
    },
    {
      file: 'src/components/ClassificationSection.tsx',
      snippet: 'flex min-h-11 w-full cursor-pointer flex-col justify-center gap-1',
      reason:
        'Laufwahl mit drei Wegen: Radio-Eingabe samt Beschriftung in einer klickbaren Zeile - ' +
        'derselbe Fall wie die Richtungswahl des Versatz-Dialogs (ersetztes Element ohne ' +
        'Pseudo-Element, Trefferflaeche = Zeilenhoehe)',
    },
    {
      file: 'src/components/CameraTimeOffsetDialog.tsx',
      snippet: '<label key={option} className="flex min-h-11 items-center gap-2">',
      reason:
        'Richtungswahl des Versatz-Dialogs: Radio-Eingabe samt Beschriftung - dieselbe ' +
        'Begruendung wie beim Kontrollkaestchen (ersetztes Element ohne Pseudo-Element)',
    },
    {
      file: 'src/components/CameraTimeOffsetDialog.tsx',
      snippet: 'className="h-11 w-full rounded-sm border border-border-control bg-surface px-3',
      reason: 'Auswahlfeld der Referenzkamera: ersetztes Element ohne Pseudo-Element',
    },
    {
      file: 'src/components/FolderBrowser.tsx',
      snippet:
        'className="h-11 w-full sm:w-auto rounded-sm border border-border-control bg-surface px-3',
      reason: 'Sortierauswahl im Ordner-Browser: ersetztes Element ohne Pseudo-Element',
    },
    {
      file: 'src/pages/ProjectSettingsPage.tsx',
      snippet: '<Skeleton className="h-11 w-full rounded-lg" />',
      reason:
        'Platzhalter einer Kamerazeile: dieselbe Zeilenhoehe wie die spaetere echte Zeile - ' +
        'ein niedrigerer Platzhalter liesse die Liste beim Eintreffen der Daten springen',
    },
    {
      file: 'src/pages/ProjectSettingsPage.tsx',
      snippet: 'className="flex min-h-11 flex-wrap items-center justify-between gap-3',
      reason: 'Kamerazeile: Zeilenhoehe einer zeilenweisen Liste',
    },
    {
      file: 'src/components/AlbumDraftDay.tsx',
      snippet: 'h-auto min-h-11 w-full justify-start',
      reason: 'Aufklapp-Zeile des Album-Entwurfs: Zeilenhoehe einer zeilenweisen Liste',
    },
    {
      file: 'src/pages/ProjectListPage.tsx',
      snippet: 'flex min-h-11 flex-col gap-2 px-4 py-3 lg:grid',
      reason: 'Projektzeile: die ganze Zeile ist EINE Trefferflaeche (Zeilenhoehe einer Liste)',
    },
    {
      file: 'src/pages/LoginPage.tsx',
      snippet: 'className="mt-2 h-11 w-full text-base"',
      reason:
        'Absende-Schaltflaeche der Anmeldung: einzige Aktion des Bildschirms, einhaendig bedient',
    },
    {
      file: 'src/components/ProjectNav.tsx',
      snippet: "layout === 'bar' ? 'tap-target' : 'min-h-11 w-full'",
      reason:
        'Panelzeile der Projekt-Navigation: Zeilenhoehe einer zeilenweisen Liste - die Zeile ' +
        'selbst ist die Trefferflaeche, deshalb bewusst NICHT zusaetzlich aufgespannt',
    },
    {
      file: 'src/components/DuplicatePhotoTile.tsx',
      snippet: 'className="h-11 grow sm:h-8"',
      reason:
        'heisser Pfad: die Wahlzeile der Vergleichsansicht (Karte und Seitenspalte der ' +
        'Grossansicht) - ein Fehlgriff schreibt, welche Bilder den Homeserver verlassen',
    },
    {
      file: 'src/components/DuplicateEnlargedView.tsx',
      snippet: 'className="h-11 sm:h-8"',
      reason:
        'heisser Pfad: Vorherige/Naechste Aufnahme der Grossansicht werden viele Male ' +
        'hintereinander gedrueckt, unmittelbar neben der Wahlzeile',
    },
    {
      file: 'src/components/TileAction.tsx',
      snippet: "iconOnly ? 'size-11 sm:size-8' : 'h-11 sm:h-8'",
      reason:
        'heisser Pfad auf jeder Kuratierungskachel: Streichen/Alternativen, Tauschen/Hinzufuegen ' +
        'und Aufnehmen/Herausnehmen schreiben sofort und stehen am Telefon nebeneinander; ' +
        'Symbolknoepfe sichtbar 44 x 44, beschriftete 44 hoch',
    },
    {
      file: 'src/components/DuplicateGroupHeader.tsx',
      snippet: 'className="h-11 sm:h-8"',
      reason:
        'heisser Pfad: Vorherige/Naechste Gruppe beim Durchgang durch alle Gruppen - ' +
        'dieselbe Begruendung wie beim Blaettern innerhalb der Gruppe',
    },
    {
      file: 'src/components/AusschussRecognition.tsx',
      snippet: '<Button asChild variant="outline" size="sm" className="h-11 sm:h-8">',
      reason:
        'der Zaehler der automatisch entschiedenen Gruppen (Spec 0639) - im Durchgang durch den ' +
        'Ausschuss ein Ziel in Daumenreichweite, dieselbe Begruendung wie die Gruppen-Navigation',
    },
    {
      file: 'src/components/AusschussOverview.tsx',
      snippet: '<Button asChild variant="ghost" size="sm" className="h-11 sm:h-8">',
      reason:
        'der Rueckweg aus der gefilterten Ansicht (Spec 0639) - steht an derselben Stelle wie ' +
        'der Zaehler und ist ebenso ein Ziel im Durchgang',
    },
    {
      file: 'src/components/UnnamedFacesGroup.tsx',
      snippet:
        "const ASSIGN_BUTTON_CLASSES = 'h-auto min-h-11 whitespace-normal break-words sm:min-h-8'",
      reason:
        'heisser Pfad: die Zuordnen-Schaltflaechen in "Ohne Namen" (Spec 0551) - ein Fehlgriff ' +
        'benennt nicht nur ein Foto, er lehrt PhotoSort ein falsches Gesicht',
    },
    {
      file: 'src/components/StepActionBar.tsx',
      snippet: "const ACTION_CLASSES = 'h-11 w-full shrink-0 sm:h-8 sm:w-auto'",
      reason:
        'Hauptaktion der haftenden Aktionsleiste unter sm: die eine naechste Aktion der ' +
        'Schrittseite in voller Breite am unteren Rand, einhaendig mit dem Daumen bedient - ' +
        'dieselbe Begruendung wie bei der Absende-Schaltflaeche der Anmeldung',
    },
    {
      file: 'src/components/ClassificationReviewCreatePanel.tsx',
      snippet:
        'flex min-h-11 w-full cursor-pointer flex-col justify-center gap-1 rounded-sm border',
      reason:
        'Seitenwahl der Pruefung (Spec 0616): Radio-Eingabe samt Beschriftung in einer klickbaren ' +
        'Zeile - derselbe Fall wie die Laufwahl der Klassifizierung (ersetztes Element ohne ' +
        'Pseudo-Element, Trefferflaeche = Zeilenhoehe)',
    },
    {
      file: 'src/pages/ClassificationReviewsPage.tsx',
      snippet:
        'flex min-h-11 w-full flex-col gap-2 rounded-sm border border-border bg-surface px-3',
      reason:
        'Pruefungszeile der Liste: die ganze Zeile ist EINE Trefferflaeche (Zeilenhoehe einer ' +
        'zeilenweisen Liste), nicht nur ihr Datum',
    },
    {
      file: 'src/components/ClassificationReviewCase.tsx',
      snippet: "'h-auto min-h-11 w-full justify-between whitespace-normal text-left",
      reason:
        'heisser Pfad: die vier Urteile je Fall der Pruefung (Spec 0616) - ein Fehlgriff ' +
        'schreibt ein falsches Urteil, das beide Nutzer und der Export uebernehmen',
    },
  ]

  it('verwendet die sichtbaren 44px nur an den drei begruendeten Kategorien', () => {
    expect(
      allowlistedOccurrences(/\bmin-h-11\b|\bh-11\b/, TALL_CONTROL_ALLOWLIST, productionTsxFiles()),
    ).toEqual([])
  })
})
