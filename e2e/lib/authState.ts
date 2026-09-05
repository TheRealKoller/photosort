/**
 * Taugt ein gespeicherter Anmeldezustand fuer das AKTUELLE Ziel?
 *
 * Der Anlass ist ein echter Fehlerpfad, kein theoretischer: Das Frontend legt sein Token in
 * `localStorage` ab, und `localStorage` ist an die Origin gebunden. Laeuft der Pruefstack einmal
 * auf 8080 und danach - weil ein normaler PhotoSort-Stack diese Ports belegt - auf 8180, dann
 * EXISTIERT die Zustandsdatei zwar, gehoert aber zur alten Origin. Ein blosser
 * `existsSync`-Test liesse `shot`/`drive` in diesem Fall still abgemeldet laufen: die Werkzeuge
 * lieferten ein Bild der Anmeldeseite statt der gemeinten Ansicht, ohne dass irgendetwas
 * fehlschlaegt. Genau die Klasse von falschem Signal, gegen die diese Ebene antritt - ein
 * Screenshot, den Claude dann als Anwendungszustand fehldeutet.
 *
 * Auf Daniels Rechner ist der verschobene Port der Normalfall, nicht die Ausnahme
 * (docs/setup.md), weshalb dieser Fall regelmaessig eintritt statt selten.
 */

/**
 * Muss zu `TOKEN_STORAGE_KEY` in `frontend/src/auth/token.ts` passen. Ein Umbenennen dort machte
 * jeden Ad-hoc-Lauf still abgemeldet; `tests/toolchain.spec.ts` bindet die beiden Werte deshalb
 * aneinander, statt den Namen hier bloss abzuschreiben.
 */
export const TOKEN_STORAGE_KEY = 'photosort_token'

/**
 * `raw` ist der Dateiinhalt einer Playwright-`storageState`-Datei. Im Zweifel wird `false`
 * geliefert (unlesbar, unerwartete Struktur, fehlender Eintrag): die Folge davon ist eine neue
 * Anmeldung, also der sichere Ausgang - waehrend ein falsches `true` genau den stillen
 * Abgemeldet-Lauf erzeugte, den diese Pruefung verhindern soll.
 */
export function authStateCoversOrigin(raw: string, origin: string): boolean {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return false
  }
  if (typeof parsed !== 'object' || parsed === null) {
    return false
  }
  const origins = (parsed as { origins?: unknown }).origins
  if (!Array.isArray(origins)) {
    return false
  }
  return origins.some((entry: unknown) => {
    if (typeof entry !== 'object' || entry === null) {
      return false
    }
    const { origin: gespeicherteOrigin, localStorage } = entry as {
      origin?: unknown
      localStorage?: unknown
    }
    if (gespeicherteOrigin !== origin || !Array.isArray(localStorage)) {
      return false
    }
    return localStorage.some(
      (eintrag: unknown) =>
        typeof eintrag === 'object' &&
        eintrag !== null &&
        (eintrag as { name?: unknown }).name === TOKEN_STORAGE_KEY
    )
  })
}
