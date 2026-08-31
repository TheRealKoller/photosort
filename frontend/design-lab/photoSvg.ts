/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): deterministisch erzeugte
 * Urlaubsmotive als SVG-Data-URI.
 *
 * Warum generiert statt echter Bilder:
 * - Kein Netzabruf zur Laufzeit (kein picsum/Unsplash) - das Labor bleibt offline durchklickbar
 *   und holt sich keine Drittquelle ins Haus.
 * - Kein einziges Rasterbild kommt neu ins Repository (Security-Auflage A4).
 * - Die vorhandenen scripts/demo_photos/*.jpg sind bewusst NICHT die Quelle: das sind abstrakte
 *   Formfixtures fuer die Scoring-Pipeline (Farbkloetze auf Verlauf), als "Urlaubsfoto" zeigen sie
 *   nichts.
 *
 * Die Palette ist bewusst NEUTRAL (gedaempfte Grau-, Stein- und Laubtoene): sie darf keiner der
 * fuenf Richtungen entgegenkommen, sonst vergleicht der Betrachter Bildwirkung statt Gestaltung.
 *
 * SICHERHEIT: Die Motive werden ausschliesslich als `src` eines `img`-Elements verwendet
 * (Auflage D1) - kein dangerouslySetInnerHTML, kein inline zusammengesetztes <svg>, kein
 * <object>/<embed>/<iframe>. Ein per data:-URI in ein img geladenes SVG rendert der Browser
 * skriptlos und ohne Zugriff auf das umgebende DOM. Der SVG-String wird vor dem Einbetten mit
 * `encodeURIComponent` kodiert (Auflage D2) - ohne das wuerde schon das erste `#` einer Hexfarbe
 * die Data-URI beenden und das Motiv unsichtbar machen.
 */

export type MotifId = 'kueste' | 'bergkamm' | 'gasse' | 'wald' | 'tisch' | 'gruppe'

/** Seitenverhaeltnisse: 4:3 quer sowie zwei Hochformate (3:4 und 2:3). */
export type AspectId = 'landscape' | 'portrait' | 'portraitTall'

const ASPECT_SIZES: Record<AspectId, { width: number; height: number }> = {
  landscape: { width: 720, height: 540 },
  portrait: { width: 540, height: 720 },
  portraitTall: { width: 480, height: 720 },
}

/** Bewusst neutrale, entsaettigte Palette - keine Richtungsfarbe, keine Signalfarbe. */
const PALETTE = {
  skyHigh: '#c2c9cb',
  skyLow: '#d6d8d3',
  water: '#93a2a6',
  waterDeep: '#7c8b91',
  sand: '#d9d0bf',
  stone: '#b0aaa0',
  stoneDark: '#8e887e',
  foliage: '#8d9683',
  foliageDark: '#6d7666',
  wood: '#b9ab97',
  shade: '#6b6b66',
  ink: '#4a4c4a',
  light: '#e7e4dd',
}

function rect(x: number, y: number, width: number, height: number, fill: string): string {
  return `<rect x="${round(x)}" y="${round(y)}" width="${round(width)}" height="${round(height)}" fill="${fill}"/>`
}

function circle(cx: number, cy: number, r: number, fill: string): string {
  return `<circle cx="${round(cx)}" cy="${round(cy)}" r="${round(r)}" fill="${fill}"/>`
}

function polygon(points: [number, number][], fill: string): string {
  const coordinates = points.map(([x, y]) => `${round(x)},${round(y)}`).join(' ')
  return `<polygon points="${coordinates}" fill="${fill}"/>`
}

function round(value: number): number {
  return Math.round(value * 10) / 10
}

type MotifPainter = (width: number, height: number) => string

const MOTIF_PAINTERS: Record<MotifId, MotifPainter> = {
  kueste: (w, h) =>
    [
      rect(0, 0, w, h * 0.56, PALETTE.skyHigh),
      circle(w * 0.74, h * 0.2, h * 0.07, PALETTE.light),
      polygon(
        [
          [0, h * 0.56],
          [w * 0.26, h * 0.44],
          [w * 0.48, h * 0.56],
        ],
        PALETTE.stone
      ),
      rect(0, h * 0.56, w, h * 0.24, PALETTE.water),
      rect(0, h * 0.63, w, h * 0.012, PALETTE.waterDeep),
      rect(w * 0.18, h * 0.71, w * 0.6, h * 0.012, PALETTE.waterDeep),
      rect(0, h * 0.8, w, h * 0.2, PALETTE.sand),
      circle(w * 0.22, h * 0.9, h * 0.03, PALETTE.stone),
      circle(w * 0.31, h * 0.93, h * 0.02, PALETTE.stoneDark),
    ].join(''),

  bergkamm: (w, h) =>
    [
      rect(0, 0, w, h, PALETTE.skyLow),
      polygon(
        [
          [0, h * 0.62],
          [w * 0.3, h * 0.24],
          [w * 0.58, h * 0.62],
        ],
        PALETTE.stone
      ),
      polygon(
        [
          [w * 0.34, h * 0.62],
          [w * 0.68, h * 0.3],
          [w, h * 0.62],
        ],
        PALETTE.stoneDark
      ),
      polygon(
        [
          [0, h * 0.78],
          [w * 0.42, h * 0.5],
          [w * 0.8, h * 0.78],
        ],
        PALETTE.foliageDark
      ),
      rect(0, h * 0.76, w, h * 0.24, PALETTE.foliage),
    ].join(''),

  gasse: (w, h) =>
    [
      rect(0, 0, w, h, PALETTE.skyLow),
      rect(w * 0.3, h * 0.22, w * 0.4, h * 0.64, PALETTE.wood),
      rect(w * 0.42, h * 0.52, w * 0.16, h * 0.34, PALETTE.shade),
      rect(0, 0, w * 0.3, h * 0.88, PALETTE.stone),
      rect(w * 0.7, 0, w * 0.3, h * 0.88, PALETTE.stoneDark),
      rect(w * 0.06, h * 0.2, w * 0.1, h * 0.12, PALETTE.shade),
      rect(w * 0.06, h * 0.46, w * 0.1, h * 0.12, PALETTE.shade),
      rect(w * 0.78, h * 0.2, w * 0.1, h * 0.12, PALETTE.shade),
      rect(w * 0.78, h * 0.46, w * 0.1, h * 0.12, PALETTE.shade),
      rect(0, h * 0.86, w, h * 0.14, PALETTE.sand),
    ].join(''),

  wald: (w, h) =>
    [
      rect(0, 0, w, h, PALETTE.foliage),
      rect(0, 0, w, h * 0.34, PALETTE.foliageDark),
      rect(w * 0.1, h * 0.18, w * 0.07, h * 0.68, PALETTE.wood),
      rect(w * 0.34, h * 0.1, w * 0.09, h * 0.76, PALETTE.shade),
      rect(w * 0.6, h * 0.2, w * 0.06, h * 0.66, PALETTE.wood),
      rect(w * 0.8, h * 0.14, w * 0.08, h * 0.72, PALETTE.shade),
      rect(0, h * 0.84, w, h * 0.16, PALETTE.stoneDark),
    ].join(''),

  tisch: (w, h) =>
    [
      rect(0, 0, w, h, PALETTE.wood),
      rect(0, h * 0.06, w, h * 0.08, PALETTE.light),
      circle(w * 0.34, h * 0.48, h * 0.19, PALETTE.light),
      circle(w * 0.34, h * 0.48, h * 0.12, PALETTE.sand),
      circle(w * 0.72, h * 0.36, h * 0.09, PALETTE.stone),
      rect(w * 0.66, h * 0.6, w * 0.12, h * 0.24, PALETTE.skyHigh),
      rect(w * 0.06, h * 0.78, w * 0.24, h * 0.1, PALETTE.stoneDark),
    ].join(''),

  gruppe: (w, h) =>
    [
      rect(0, 0, w, h * 0.72, PALETTE.skyHigh),
      rect(0, h * 0.72, w, h * 0.28, PALETTE.sand),
      circle(w * 0.28, h * 0.42, h * 0.07, PALETTE.ink),
      rect(w * 0.2, h * 0.5, w * 0.16, h * 0.3, PALETTE.ink),
      circle(w * 0.5, h * 0.36, h * 0.08, PALETTE.shade),
      rect(w * 0.41, h * 0.45, w * 0.18, h * 0.35, PALETTE.shade),
      circle(w * 0.73, h * 0.45, h * 0.06, PALETTE.ink),
      rect(w * 0.66, h * 0.52, w * 0.14, h * 0.28, PALETTE.ink),
    ].join(''),
}

/** Ein Motiv als `data:image/svg+xml`-URI, ausschliesslich fuer `img.src` gedacht (Auflage D1). */
export function motifDataUri(motif: MotifId, aspect: AspectId): string {
  const { width, height } = ASPECT_SIZES[aspect]
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" ` +
    `width="${width}" height="${height}" role="presentation">` +
    MOTIF_PAINTERS[motif](width, height) +
    '</svg>'
  // encodeURIComponent statt btoa: haelt die Umlaute-freie Zeichenkette lesbar und ist gegen das
  // `#` der Hexfarben zwingend (Auflage D2).
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

/*
 * Optionale Uebersteuerung mit echten Fotos: beliebige JPG/PNG in frontend/design-lab/photos-local/
 * ablegen. Der Ordner ist per Root-.gitignore ausgeschlossen und wird zusaetzlich vom Guard A2
 * ueberwacht - Familienfotos duerfen NIE ins Repository (CLAUDE.md).
 *
 * Ein fehlendes oder leeres Verzeichnis ist der Normalfall (Git fuehrt keine leeren Verzeichnisse)
 * und muss klaglos funktionieren (Auflage A3): `import.meta.glob` liefert dann schlicht kein
 * Ergebnis und jedes Foto faellt auf sein generiertes Motiv zurueck.
 */
const localPhotoModules = import.meta.glob('./photos-local/*.{jpg,jpeg,png}', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

/** Nach Dateiname sortiert, damit die Zuordnung zu den Fixture-Positionen stabil bleibt. */
const localPhotoUrls: string[] = Object.keys(localPhotoModules)
  .sort()
  .map((key) => localPhotoModules[key])

/** Anzahl gefundener lokaler Fotos - die Huelle zeigt den Zustand selbstdiagnostisch an. */
export const localPhotoCount = localPhotoUrls.length

/**
 * Bildquelle fuer die Fixture-Position `index`: das positionsgleiche lokale Foto, sonst das
 * generierte Motiv.
 */
export function photoSrc(index: number, motif: MotifId, aspect: AspectId): string {
  return localPhotoUrls[index] ?? motifDataUri(motif, aspect)
}
