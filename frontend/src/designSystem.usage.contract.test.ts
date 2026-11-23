// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: statische Verwendungsregeln.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts (Spec 0320, Spec 0651).
 */

import { describe, expect, it } from 'vitest'

import { DUPLICATE_TILE_INSET_X_PX } from './utils/duplicateLayout'
import { GRID_GAP_PX } from './utils/justifiedRows'
import { sourceFiles, stringLiterals, stripComments, tsxFiles } from './test/designSystemScan'

// ---------------------------------------------------------------------------------------------
// Statische Verwendungsregeln
// ---------------------------------------------------------------------------------------------

const TAP_TARGET_UTILITY = 'tap-target'

/**
 * Utilities, die die eine globale Fokusdarstellung aushebeln. Der Name der outline-Utility ist
 * bewusst ZUSAMMENGESETZT statt als Literal geschrieben: Tailwind scannt auch diese Datei, und
 * ein Vorkommen hier allein wuerde die verbotene Regel in die gebaute CSS aufnehmen - ein
 * Artefakt, das beim Nachmessen am gebauten Stylesheet genau den Verdacht erzeugt, den dieser
 * Test ausraeumen soll.
 */
const FOCUS_SUPPRESSING_UTILITY = new RegExp(
  `ring-offset|focus-visible:|(^|[\\s'"\`([])(?:[a-z-]+:)*outline-${'none'}\\b`,
)

describe('Design-Vertrag: statische Verwendungsregeln', () => {
  it('verwendet text-text-disabled ausschliesslich als disabled:-Variante', () => {
    const offenders: string[] = []
    for (const file of sourceFiles) {
      for (const line of stripComments(file.content).split('\n')) {
        for (const word of line.split(/[\s'"`(){},]+/)) {
          if (!word.endsWith('text-text-disabled')) continue
          // Zulaessig ist jede Variante, die den deaktivierten Zustand traegt - `disabled:` am
          // Element selbst ebenso wie `has-[:disabled]:`/`group-disabled:` am umgebenden Element.
          const variants = word.slice(0, word.length - 'text-text-disabled'.length)
          if (!variants.includes('disabled')) {
            offenders.push(`${file.label}: ${line.trim()}`)
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })

  // Der Erkenner steht als benannte Konstante da, damit der Mikrotest darunter GENAU DIESEN
  // Ausdruck pruefen kann und nicht eine abgeschriebene Kopie davon.
  //
  // Der Lookahead nennt ZWEI Ausnahmen (Spec 0044): hinter `danger` liegt eine Wortgrenze, der
  // Erkenner schlaegt deshalb auch auf `text-danger-fg` an - dem Vordergrund-Token AUF gefuellter
  // --danger-Flaeche, das gerade keine Fliesstextfarbe ist. `\b` hinter jeder Ausnahme, damit ein
  // hypothetisches `text-danger-fgx` nicht mit durchrutscht.
  const FLOWING_TEXT_DANGER = /\btext-danger\b(?!-text\b|-fg\b)/

  it('verwendet --danger nie als Fliesstextfarbe (nur --danger-text haelt AA auf allen vier Flaechen)', () => {
    const offenders: string[] = []
    for (const file of sourceFiles) {
      for (const line of stripComments(file.content).split('\n')) {
        if (FLOWING_TEXT_DANGER.test(line)) {
          offenders.push(`${file.label}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  // Der Erkenner oben ist eine scharfe Regel, deren Lookahead beim Hinzufuegen von --danger-fg
  // aufgeweicht werden musste (Spec 0044). Ohne diesen Mikrotest ist nicht mehr unterscheidbar,
  // ob die Regel noch greift oder ob der Lookahead sie stillgelegt hat.
  it.each([
    ['flex items-center text-danger', true],
    ['text-danger', true],
    ['hover:text-danger', true],
    ['sm:text-danger md:text-lg', true],
    ['text-danger-text', false],
    ['text-danger-fg', false],
    ['bg-danger text-danger-fg hover:opacity-85', false],
    ['border-danger bg-surface', false],
    ['text-dangerous', false],
  ])('Erkenner "verwendet --danger als Fliesstext": %s -> %s', (line, expected) => {
    expect(FLOWING_TEXT_DANGER.test(line)).toBe(expected)
  })

  /*
   * specs/features/0489-fotouebersicht-ohne-beschnitt.md, AK1: Die Rasterkachel beschneidet NIE.
   * `object-cover` schneidet zu, `aspect-square` zwingt eine feste Form auf - beides hebt die
   * Zusage auf, ohne dass sonst irgendetwas rot wuerde. Die Bildflaeche traegt ihr eigenes
   * Verhaeltnis als gerechnetes Inline-Mass; die Kachel selbst darf dazu keine Form vorgeben.
   */
  it.each(['object-cover', 'aspect-square'])(
    'haelt %s aus der Rasterkachel heraus (AK1: kein Beschnitt)',
    (utility) => {
      const tile = sourceFiles.find((file) =>
        file.path.endsWith('src/components/PhotoGridTile.tsx'),
      )
      expect(tile, 'PhotoGridTile.tsx muss im Pruefsatz liegen').toBeDefined()

      expect(stripComments(tile?.content ?? '')).not.toContain(utility)
    },
  )

  /*
   * Die Kuratierungsraster (Album-Entwurf, Alternativen, Hinzufuegen-Panel, Endauswahl) zeigen
   * jedes Foto im eigenen Seitenverhaeltnis, nie beschnitten und nie in eine feste Form gezwungen:
   * `object-cover` schneidet zu, `aspect-square` zwingt jede Bildflaeche ins Quadrat, und ein
   * Spaltenraster (`grid-cols-*`) setzte die Kachelbreite unabhaengig vom Foto.
   */
  const CURATION_FILES = [
    'src/components/PhotoCard.tsx',
    'src/components/CurationPhotoTile.tsx',
    'src/components/SelectionPhotoTile.tsx',
    'src/components/DraftAlternativesBand.tsx',
    'src/components/DraftEventSection.tsx',
    'src/components/CurationSkeletonList.tsx',
    'src/pages/AlbumDraftPage.tsx',
    'src/pages/AlbumSelectionPage.tsx',
  ]

  it.each(CURATION_FILES)(
    'haelt object-cover, aspect-square und Spaltenraster aus %s heraus',
    (path) => {
      const file = sourceFiles.find((candidate) => candidate.path.endsWith(path))
      expect(file, `${path} muss im Pruefsatz liegen`).toBeDefined()

      const code = stripComments(file?.content ?? '')
      expect(code).not.toContain('object-cover')
      expect(code).not.toContain('aspect-square')
      expect(code).not.toMatch(/grid-cols-/)
    },
  )

  /*
   * specs/features/0638-duplikatansicht-originalformat.md: Raster, Platzhalter und
   * Vorschau-Streifen der Vergleichsansicht beschneiden nie und zwingen keine feste Form auf -
   * dieselbe Regel wie in der Kuratierung. Die Buehne der Grossansicht war schon `object-contain`.
   */
  it.each([
    'src/components/DuplicatePhotoTile.tsx',
    'src/components/DuplicateEnlargedView.tsx',
    'src/pages/DuplicateComparePage.tsx',
  ])('haelt object-cover, aspect-square und Spaltenraster aus %s heraus (Spec 0638)', (path) => {
    const file = sourceFiles.find((candidate) => candidate.path.endsWith(path))
    expect(file, `${path} muss im Pruefsatz liegen`).toBeDefined()

    const code = stripComments(file?.content ?? '')
    expect(code).not.toContain('object-cover')
    expect(code).not.toContain('aspect-square')
    expect(code).not.toMatch(/grid-cols-/)
  })

  /*
   * Die Duplikatliste (Raster und Platzhalter) rechnet mit `GRID_GAP_PX` als Abstand zwischen
   * zwei Kacheln - die Utility der Liste muss dieselbe Zahl setzen.
   */
  it('setzt die Duplikatliste als flex-wrap mit dem gerechneten Zwischenraum (Spec 0638)', () => {
    const page = sourceFiles.find((file) =>
      file.path.endsWith('src/pages/DuplicateComparePage.tsx'),
    )
    expect(page, 'DuplicateComparePage.tsx muss im Pruefsatz liegen').toBeDefined()

    const listClasses = stripComments(page?.content ?? '').match(
      /const GRID_LIST_CLASSES = '([^']*)'/,
    )
    expect(listClasses, 'Die Liste muss ihre Klassen in GRID_LIST_CLASSES fuehren').not.toBeNull()
    const classes = listClasses?.[1].split(/\s+/) ?? []
    expect(classes).toEqual(expect.arrayContaining(['flex', 'flex-wrap', 'items-start']))
    expect(classes).toContain(`gap-${GRID_GAP_PX / 4}`)
  })

  /*
   * DIE DRITTE WAHRHEIT DESSELBEN WERTS (Spec 0638). Der waagerechte Kachelrand der
   * Vergleichsansicht ist `px-2` (8) plus `border-2` (2), je Seite, UND die Zahl
   * `DUPLICATE_TILE_INSET_X_PX` in der Rasterrechnung. Haengt der Rand an einer Bildschirmbreite
   * (`sm:px-3`, `p-2 sm:p-3`), stimmt die Rechnung nur noch an einem Breakpoint, und jede volle
   * Reihe laeuft dort ueber oder schliesst nicht buendig ab.
   */
  it('haelt den Kachelrand der Vergleichsansicht an seiner Rechengroesse fest (Spec 0638)', () => {
    expect(DUPLICATE_TILE_INSET_X_PX).toBe(2 * (8 + 2))

    const tile = sourceFiles.find((file) =>
      file.path.endsWith('src/components/DuplicatePhotoTile.tsx'),
    )
    const page = sourceFiles.find((file) =>
      file.path.endsWith('src/pages/DuplicateComparePage.tsx'),
    )
    expect(tile, 'DuplicatePhotoTile.tsx muss im Pruefsatz liegen').toBeDefined()
    expect(page, 'DuplicateComparePage.tsx muss im Pruefsatz liegen').toBeDefined()
    const tileCode = stripComments(tile?.content ?? '')
    const pageCode = stripComments(page?.content ?? '')

    // Die Kachel: ihre Klassen stehen im ersten Literal des `cn` direkt hinter der gerechneten
    // Breite; der Rahmen kommt aus den Zustaenden.
    const tileClasses = tileCode.match(
      /width: imageWidth \+ DUPLICATE_TILE_INSET_X_PX \}\}\s*className=\{cn\(\s*'([^']*)'/,
    )?.[1]
    // Der Platzhalter: das `li` mit derselben gerechneten Breite.
    const skeletonClasses = pageCode.match(
      /width: size\.width \+ DUPLICATE_TILE_INSET_X_PX \}\}\s*className="([^"]*)"/,
    )?.[1]
    expect(tileClasses, 'Kachelklassen hinter der gerechneten Breite').toBeDefined()
    expect(skeletonClasses, 'Platzhalterklassen hinter der gerechneten Breite').toBeDefined()

    for (const classes of [tileClasses ?? '', skeletonClasses ?? '']) {
      const list = classes.split(/\s+/)
      expect(list).toContain('px-2')
      expect(list.filter((utility) => /^(?:[a-z0-9]+:)*(?:p|pl|pr|px)-/.test(utility))).toEqual([
        'px-2',
      ])
    }
    expect(skeletonClasses?.split(/\s+/)).toContain('border-2')
    for (const rahmen of tileCode.matchAll(/rahmen: '([^']*)'/g)) {
      expect(rahmen[1].split(/\s+/)).toContain('border-2')
    }
    expect([...tileCode.matchAll(/rahmen: '([^']*)'/g)]).toHaveLength(2)
  })

  /*
   * Jedes Kuratierungsraster ist eine umbrechende Liste mit demselben Zwischenraum, mit dem
   * `justifiedRows` rechnet - sonst bricht jede Reihe einen Pixel zu frueh oder zu spaet um.
   */
  it.each([
    'src/components/DraftEventSection.tsx',
    'src/components/DraftAlternativesBand.tsx',
    'src/components/CurationSkeletonList.tsx',
    'src/pages/AlbumSelectionPage.tsx',
  ])('setzt das Raster in %s als flex-wrap mit dem gerechneten Zwischenraum', (path) => {
    const file = sourceFiles.find((candidate) => candidate.path.endsWith(path))
    expect(file, `${path} muss im Pruefsatz liegen`).toBeDefined()

    expect(stripComments(file?.content ?? '')).toContain(
      `className="flex flex-wrap gap-${GRID_GAP_PX / 4}"`,
    )
  })

  /*
   * ZWEI WAHRHEITEN DESSELBEN WERTS. Der Zwischenraum zwischen zwei Kacheln ist eine Utility der
   * 8-Punkt-Skala (`gap-3` = 12px) UND eine Zahl in der Rasterrechnung (`GRID_GAP_PX`). Laufen
   * die beiden auseinander, rechnet die Funktion mit einem anderen Abstand als der Browser setzt,
   * und jede Zeile bricht einen Pixel zu frueh oder zu spaet um - buendig waere sie nie wieder,
   * ohne dass eine Pruefung anschluege.
   */
  it('haelt den Zwischenraum des Rasters an seiner Utility fest', () => {
    expect(GRID_GAP_PX).toBe(12)

    const page = sourceFiles.find((file) => file.path.endsWith('src/pages/PhotoGridPage.tsx'))
    expect(page, 'PhotoGridPage.tsx muss im Pruefsatz liegen').toBeDefined()
    // Ueber das semantische `data-photo-grid` gesucht, nicht ueber "irgendeine flex-wrap-Zeile":
    // Die Filterleiste derselben Datei ist ebenfalls eine, traegt aber ihren eigenen Abstand.
    const listClasses = stripComments(page?.content ?? '').match(
      /data-photo-grid[^>]*?className="([^"]*)"/,
    )
    expect(listClasses, 'Das Raster muss als `data-photo-grid` erkennbar sein').not.toBeNull()
    expect(listClasses?.[1]).toContain('flex-wrap')
    expect(listClasses?.[1]).toContain(`gap-${GRID_GAP_PX / 4}`)
  })

  /** Der Variantenpraefix einer Utility (`group-active:bg-border` -> `group-active:`), leer bei
   * einer unpraefixierten. */
  function variantPrefix(utility: string): string {
    const cut = utility.lastIndexOf(':')
    return cut === -1 ? '' : utility.slice(0, cut + 1)
  }

  /**
   * Der Vordergrund, der GLEICHZEITIG mit einer Flaeche gilt: der mit demselben Variantenpraefix,
   * sonst der unpraefixierte Ruhewert. Ohne diese Unterscheidung meldete die Regel unten jedes
   * Rezept falsch-rot, das Ruhezustand und Zustandsvarianten in EINEM Klassenliteral fuehrt -
   * seit dem `group-`-Muster (Spec 0387) ist das der Regelfall, und der Ruhevordergrund gilt dort
   * gerade NICHT auf der gedrueckten Flaeche.
   */
  function foregroundWith(classes: string[], surface: string): string | undefined {
    const prefix = variantPrefix(surface)
    const foregrounds = classes.filter((cls) => /(^|:)text-[a-z-]+$/.test(cls))
    return (
      foregrounds.find((cls) => variantPrefix(cls) === prefix) ??
      foregrounds.find((cls) => variantPrefix(cls) === '')
    )
  }

  it.each([
    [['bg-border', 'text-text-muted'], 'text-text-muted'],
    [
      ['group-active:bg-border', 'text-text-muted', 'group-active:text-text'],
      'group-active:text-text',
    ],
    [['group-active:bg-border', 'text-text-muted'], 'text-text-muted'],
  ])('Erkenner "Vordergrund auf der Flaeche": %s -> %s', (classes, expected) => {
    // Selbsttest des Zuordners: ohne ihn koennte er stets `undefined` liefern und die Regel
    // unten waere dauerhaft gruen.
    const surface = classes.find((cls) => /(^|:)bg-border$/.test(cls))!
    expect(foregroundWith(classes, surface)).toBe(expected)
  })

  it('setzt auf die gedrueckte Flaeche --border nur die dort gerechneten Vordergruende', () => {
    // `--text-muted` misst auf `--border` 4.36:1 und `--danger-text` 4.33:1 - beide verfehlen AA.
    // Der gedrueckte Zustand ist am Telefon der EINZIGE Zustand, den es gibt (Tailwind bindet
    // `hover:` an `@media (hover: hover)`); eine dort unlesbare Beschriftung ist deshalb kein
    // Randfall. Zulaessig sind `--text` (5.49) und `--text-h` (13.49).
    const forbiddenOnBorder = ['text-text-muted', 'text-danger-text']
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const literal of stringLiterals(file.content)) {
        const classes = literal.split(/\s+/)
        for (const surface of classes.filter((cls) => /(^|:)bg-border$/.test(cls))) {
          const foreground = foregroundWith(classes, surface)
          if (
            foreground !== undefined &&
            forbiddenOnBorder.some((name) => foreground.endsWith(name))
          ) {
            offenders.push(`${file.label}: ${foreground} auf ${surface}`)
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('umreisst Bedienelement-Primitive nie mit dem rein dekorativen --border', () => {
    // --border liegt bei 1.04-1.45:1 - als einziger Umriss eines Bedienelements auf dunklem Grund
    // ist der Button schlicht unsichtbar. Dafuer gibt es --border-control (>= 3:1 auf allen vier
    // Flaechen). Karten, Panels und Popover duerfen --border weiterhin als Trennlinie tragen.
    const controlPrimitives = ['ui/button.tsx', 'ui/input.tsx', 'ui/switch.tsx', 'ui/checkbox.tsx']
    const offenders: string[] = []
    for (const file of sourceFiles) {
      if (!controlPrimitives.some((name) => file.label.endsWith(name))) continue
      for (const line of stripComments(file.content).split('\n')) {
        for (const word of line.split(/[\s'"`(){},]+/)) {
          if (!word.endsWith('border-border')) continue
          // Ausnahme: der DEAKTIVIERTE Zustand. WCAG 1.4.11 nimmt inaktive Bedienelemente aus,
          // und das Board setzt dort ausdruecklich den dekorativen Rahmen ein.
          const variants = word.slice(0, word.length - 'border-border'.length)
          if (!variants.includes('disabled')) {
            offenders.push(`${file.label}: ${line.trim()}`)
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('importiert lucide-react ausschliesslich benannt und ausschliesslich in ui/icon.tsx', () => {
    const importingFiles = sourceFiles.filter((file) =>
      /from\s+'lucide-react'/.test(stripComments(file.content)),
    )
    expect(importingFiles.map((file) => file.label)).toEqual(['src/components/ui/icon.tsx'])

    const iconSource = stripComments(importingFiles[0].content)
    const importStatements = iconSource.match(/import[^;]*from\s+'lucide-react'/g) ?? []
    expect(importStatements).toHaveLength(1)
    // Namespace-Import und berechneter Zugriff auf das Paket-Objekt hebeln das Tree-Shaking aus
    // und zoegen den vollen Lucide-Satz (~32 MB entpackt) ins Bundle.
    expect(importStatements[0]).not.toMatch(/import\s+\*/)
    expect(importStatements[0]).toMatch(/import\s*\{[^}]+\}\s*from\s+'lucide-react'/)
    expect(iconSource).not.toMatch(/require\(\s*'lucide-react'\s*\)/)
  })

  it.each(['ui/badge.tsx', 'ui/icon.tsx'])(
    'baut in %s keine Klassennamen zusammen (Tailwind erkennt nur statische, vollstaendige Strings)',
    (name) => {
      const file = sourceFiles.find((candidate) => candidate.label.endsWith(name))
      expect(file, `${name} nicht gefunden`).toBeDefined()
      expect(stripComments(file!.content)).not.toMatch(/`[^`]*\$\{/)
    },
  )

  it('hebelt die globale Fokusdarstellung nirgends in einer .tsx aus', () => {
    /*
     * Die eine globale :focus-visible-Regel ist die alleinige Fokusdarstellung (s.o.). Neben den
     * offensichtlichen Schreibweisen (`ring-offset`, `focus-visible:`) MUSS auch die
     * outline-unterdrueckende Utility verboten sein - und zwar in jeder Variante, mit und ohne
     * `focus:`-Praefix (der Name steht bewusst nirgends als Literal in dieser Datei, siehe
     * FOCUS_SUPPRESSING_UTILITY).
     *
     * Der Grund ist an der gebauten CSS gemessen, nicht hergeleitet: die globale Regel steht in
     * `@layer base`, die Utility in `@layer utilities`. Bei Cascade Layers gewinnt die SPAETERE
     * Ebene unabhaengig von der Spezifitaet - eine einzige solche Klasse an einem
     * Primitive nimmt der ganzen App an dieser Stelle die Fokuskontur, ohne dass irgendetwas
     * fehlschlaegt. Genau das ist hier passiert, waehrend diese Regel nur `ring-offset` und
     * `focus-visible:` kannte: der Test war gruen, die Zusage hielt nicht.
     */
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const line of stripComments(file.content).split('\n')) {
        if (FOCUS_SUPPRESSING_UTILITY.test(line)) {
          offenders.push(`${file.label}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('spannt die Trefferflaeche nie innerhalb eines beschneidenden Containers auf', () => {
    // Ein `overflow: hidden` auf DEMSELBEN Knoten beschneidet das Pseudo-Element still - die
    // Trefferflaeche faellt auf das sichtbare Mass zurueck, ohne dass etwas kaputt aussieht.
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const literal of stringLiterals(file.content)) {
        const classes = literal.split(/\s+/)
        if (classes.includes(TAP_TARGET_UTILITY) && classes.includes('overflow-hidden')) {
          offenders.push(`${file.label}: ${literal}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('setzt die Trefferflaechen-Utility an allen aufspannenden Primitiven', () => {
    for (const name of ['ui/button.tsx', 'ui/switch.tsx', 'ui/checkbox.tsx']) {
      const file = sourceFiles.find((candidate) => candidate.label.endsWith(name))
      expect(file, `${name} nicht gefunden`).toBeDefined()
      expect(file!.content, `${name} ohne ${TAP_TARGET_UTILITY}`).toContain(TAP_TARGET_UTILITY)
    }
  })

  it('stellt jeder hover:-Variante der Primitive eine active:-Variante zur Seite', () => {
    // Tailwind bindet `hover:` an `@media (hover: hover)` - am Telefon faellt der Zustand ersatzlos
    // weg. Ohne `active:` erzeugt ein Fingertipp dort gar keine sichtbare Rueckmeldung.
    const offenders: string[] = []
    for (const file of sourceFiles) {
      if (!/\/ui\/[a-z]+\.tsx$/.test(file.label)) continue
      for (const literal of stringLiterals(file.content)) {
        if (literal.includes('hover:') && !literal.includes('active:')) {
          offenders.push(`${file.label}: ${literal}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })
})
