// @vitest-environment node
/**
 * Haelt `scripts/tests/prettier_endungen.json` gegen das TATSAECHLICH installierte Prettier.
 *
 * **Warum diese Datei hier liegt und nicht bei ihrem Verbraucher.** Die Liste wird von
 * `scripts/tests/test_prettierignore_spiegelung.py` gebraucht: Dort entscheidet sie, ob ein
 * `.gitignore`-Datei-Glob wie `*.log` eine von Prettier parsbare Datei treffen kann und deshalb
 * in `/.prettierignore` gespiegelt gehoeren muss. Der CI-Job `demo-scripts` hat aber **weder
 * Node noch node_modules** - er kann `prettier --support-info` nicht aufrufen. Der Job
 * `frontend` kann es, weil Prettier dort als devDependency installiert ist. Also: erzeugter,
 * eingecheckter Datenstand fuer den Verbraucher, Abgleich gegen die Wahrheit in dem Job, der sie
 * erreichen kann. Beide Jobs laufen bei jedem Pull Request; keine Haelfte haengt an einem
 * `skip`, und ein uebersprungener Prueflauf waere von einem bestandenen nicht zu unterscheiden.
 *
 * **Warum ueberhaupt abgeleitet statt gepflegt** (Copilot-Finding zu PR #409): Die Liste stand
 * zuvor als handverlesene Auswahl im Python-Test, ausdruecklich "gekuerzt auf die, die in einem
 * Artefaktverzeichnis dieses Projekts realistisch auftreten". Gemessen waren das **25 von 115**
 * Endungen - es fehlten unter anderem `.gql`, `.graphqls`, `.markdown`, `.mdown`, `.geojson`,
 * `.htm`, `.xhtml`, `.pcss` und `.postcss`. Genau die Ermessensentscheidung ueber den
 * "realistischen" Fall, die fuer diese Story ausgeschlossen ist.
 *
 * **Die Richtung des Fehlers ist hier entscheidend, und deshalb ist Vollstaendigkeit kein
 * Luxus.** Der Verbraucher fordert eine Spiegelung, wenn die Endung in dieser Liste steht. Eine
 * zu kurze Liste fordert also zu **wenig** - ein `.gitignore`-Eintrag bleibt ungespiegelt, und
 * der Formatierer greift lokal auf unversionierte Dateien zu, ohne dass es auffaellt. Das ist
 * die Fehlerrichtung, gegen die die ganze Zusicherung antritt.
 *
 * **Was bei einem Prettier-Versionswechsel passiert:** Dieser Test wird **rot**, laut und mit
 * dem Befehl zum Neuerzeugen in der Meldung. Bewusst kein `toMatchFileSnapshot`, obwohl das
 * Repository dieses Muster kennt (`frontend/penpot/tokens.test.ts`): Ein Snapshot-Schreiber
 * zieht die Datei still nach und faerbt dabei NICHT rot. Eine still nachgezogene Liste ist
 * wieder eine von Hand gepflegte - nur besser getarnt -, und der Moment, in dem die
 * Spiegelungsregel neu zu bewerten waere, ginge unbemerkt vorbei.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
// eslint-disable-next-line import/no-extraneous-dependencies -- devDependency, nur im Test
import { getSupportInfo, version } from 'prettier'

const DATENSTAND_PFAD = fileURLToPath(
  new URL('../../scripts/tests/prettier_endungen.json', import.meta.url),
)

const ERZEUGUNGSBEFEHL =
  'cd frontend && ./node_modules/.bin/prettier --support-info  (siehe Kopfkommentar dieser Datei)'

type Datenstand = {
  prettierVersion: string
  extensions: string[]
}

const datenstand = JSON.parse(readFileSync(DATENSTAND_PFAD, 'utf8')) as Datenstand

async function installierteEndungen(): Promise<string[]> {
  const info = await getSupportInfo()
  return [...new Set(info.languages.flatMap((sprache) => sprache.extensions ?? []))].sort()
}

describe('prettier_endungen.json', () => {
  it('nennt die Version des installierten Prettier', () => {
    expect(datenstand.prettierVersion, `Neu erzeugen: ${ERZEUGUNGSBEFEHL}`).toBe(version)
  })

  it('fuehrt genau die Endungen des installierten Prettier', async () => {
    const installiert = await installierteEndungen()
    const fehlend = installiert.filter((e) => !datenstand.extensions.includes(e))
    const ueberzaehlig = datenstand.extensions.filter((e) => !installiert.includes(e))

    expect(
      { fehlend, ueberzaehlig },
      `scripts/tests/prettier_endungen.json weicht vom installierten Prettier ${version} ab. ` +
        'Fehlende Endungen sind die gefaehrliche Richtung: Der Waechter in ' +
        'scripts/tests/test_prettierignore_spiegelung.py fordert dann fuer einen ' +
        '.gitignore-Datei-Glob mit dieser Endung KEINE Spiegelung, und der Formatierer greift ' +
        `lokal auf unversionierte Dateien zu. Neu erzeugen: ${ERZEUGUNGSBEFEHL}`,
    ).toEqual({ fehlend: [], ueberzaehlig: [] })
  })

  it('ist plausibel gross und enthaelt die Endungen, an denen der Verbraucher haengt', async () => {
    // Selbstschutz: Ein Leser, der still ein leeres Array liefert, machte den Abgleich oben
    // vakuum-gruen (leer == leer). Die Stichprobe nennt bewusst Endungen, die in der frueheren
    // handverlesenen Liste FEHLTEN - sie sind der Anlass dieser Datei.
    expect(datenstand.extensions.length).toBeGreaterThan(100)
    for (const endung of ['.json', '.ts', '.css', '.md', '.yaml', '.gql', '.geojson', '.htm']) {
      expect(datenstand.extensions, `${endung} fehlt im Datenstand`).toContain(endung)
    }
    expect(await installierteEndungen()).toContain('.gql')
  })
})
