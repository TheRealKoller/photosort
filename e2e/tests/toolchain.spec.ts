/**
 * Das Verlaesslichkeitsregime als Zusicherung, nicht als Absichtserklaerung.
 *
 * `retries: 0`, `forbidOnly: true` und `workers: 1` stehen in `playwright.config.ts` - eine
 * Konfigurationsdatei aendert man aber schnell und leise, gerade unter dem Druck eines
 * sprunghaften Laufs ("stell die Wiederholungen doch auf 2"). Genau dann soll dieser Spec LAUT
 * scheitern, statt dass das Regime still verschwindet. Der Akzeptanz-Wortlaut der Spec 0174:
 * "sind per Assertion an die Konfiguration gebunden".
 *
 * Geprueft wird der WIRKSAME Wert (inklusive Kommandozeilen-Ueberschreibungen), nicht der
 * Dateiinhalt - eine Textsuche in der Konfigurationsdatei liesse sich mit `--retries=2` muehelos
 * umgehen.
 *
 * Kein Rot-Nachweis noetig/moeglich im Sinne der Layout-Regel: der Spec misst kein Layout. Sein
 * Fehlschlagverhalten ist trivial belegbar - `npx playwright test --retries=1` macht ihn rot
 * (bei Einfuehrung einmal so ausgefuehrt, siehe PR-Beschreibung).
 */

import { readFileSync } from 'node:fs'
import path from 'node:path'

import { authStateCoversOrigin, TOKEN_STORAGE_KEY } from '../lib/authState.ts'
import { DEFAULT_BASE_URL, resolveBaseUrl } from '../lib/baseUrl.ts'
import { DEMO_PROJECTS } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'
import { PACKAGE_ROOT } from '../lib/paths.ts'
import { VIEWPORTS } from '../lib/viewports.ts'

const REPO_ROOT = path.join(PACKAGE_ROOT, '..')

function repoFile(relativePath: string): string {
  return readFileSync(path.join(REPO_ROOT, relativePath), 'utf8')
}

test('das Verlaesslichkeitsregime ist an die Konfiguration gebunden', () => {
  const info = test.info()

  // Wiederholen macht aus einem sprunghaften Test einen UNSICHTBAR sprunghaften Test.
  expect(info.project.retries, 'retries des laufenden Projekts').toBe(0)
  // Ein vergessenes test.only wuerde den Pruefsatz still auf einen einzigen Fall zusammenschrumpfen
  // lassen - und der Lauf bliebe gruen.
  expect(info.config.forbidOnly, 'forbidOnly').toBe(true)
  // Alle Specs teilen sich EINEN geseedeten Datenbestand.
  expect(info.config.workers, 'workers').toBe(1)
})

test('die beiden festen Viewport-Projekte haben die zugesagten Groessen', () => {
  const projects = test.info().config.projects
  const byName = new Map(projects.map((project) => [project.name, project.use.viewport]))

  // Exakte Kardinalitaet: Setup-Projekt plus genau die zwei zugesagten Viewport-Projekte. Ein
  // drittes, still hinzugekommenes Projekt waere eine unbemerkte Aenderung des Pruefumfangs.
  expect([...byName.keys()].sort(), 'Projekte in der Konfiguration').toEqual([
    'desktop',
    'mobile',
    'setup',
  ])
  expect(byName.get('mobile'), 'Viewport des mobilen Projekts').toEqual(VIEWPORTS.mobile)
  expect(byName.get('desktop'), 'Viewport des Desktop-Projekts').toEqual(VIEWPORTS.desktop)
})

/**
 * Die folgenden drei Tests messen kein Layout, sondern binden Doku an Code. Sie liegen hier statt
 * in einer der beiden anderen Testebenen, weil sie Zusagen DIESES Pakets sind - und weil sie
 * damit im selben blockierenden Lauf scheitern wie alles andere, was diese Ebene zusichert.
 */

test('review-ux bleibt ohne laufende Instanz voll funktionsfaehig', () => {
  const skill = repoFile('.claude/skills/review-ux/SKILL.md')

  // Die Unverbindlichkeit steht woertlich da - ein spaeteres Umformulieren zu "startet die
  // Anwendung und prueft ..." machte aus einer Moeglichkeit eine Voraussetzung.
  expect(skill, 'ausdrueckliche Unverbindlichkeit in review-ux').toContain('**darf**')
  expect(skill, 'ausdrueckliche Unverbindlichkeit in review-ux').toContain('**muss** es nicht')

  // Und der Skill enthaelt keinen Schritt, der eine laufende Instanz voraussetzt: keinen Befehl,
  // der etwas startet oder abfotografiert. Der Verweis auf `browse-app` bleibt ein Verweis.
  for (const forbidden of ['docker compose', 'npm run shot', 'npm run drive', 'playwright test']) {
    expect(skill, `review-ux enthaelt keinen ausfuehrbaren Schritt "${forbidden}"`).not.toContain(
      forbidden
    )
  }
})

test('der browse-app-Skill nennt die Freigabe-Zeichenkette des Seeders woertlich', () => {
  const seeder = repoFile('backend/src/photosort/demo_state.py')
  const skill = repoFile('.claude/skills/browse-app/SKILL.md')

  const match = /^CONFIRM_LITERAL = "([^"]+)"$/m.exec(seeder)
  expect(match, 'CONFIRM_LITERAL in demo_state.py').not.toBeNull()

  // Doku an Code gebunden statt abgeschrieben: aendert sich das Literal, faellt die Anleitung
  // hier auf - und nicht erst bei Daniel im Terminal als Abbruchmeldung des Seeders.
  expect(skill, 'Freigabe-Zeichenkette im browse-app-Skill').toContain(match![1])
  expect(repoFile('docker-compose.e2e.yml'), 'Freigabe-Zeichenkette im Overlay').toContain(match![1])
})

test('die Demo-Projektnamen des Pruefsatzes stammen aus dem Seeder', () => {
  const seeder = repoFile('backend/src/photosort/demo_state.py')

  const prefixMatch = /^DEMO_PROJECT_PREFIX = "([^"]+)"$/m.exec(seeder)
  expect(prefixMatch, 'DEMO_PROJECT_PREFIX in demo_state.py').not.toBeNull()
  const prefix = prefixMatch![1]!

  // Die Namen stehen im Seeder als f-String aus Praefix + Suffix; hier wird der Suffix
  // zurueckgerechnet und im Seeder gesucht. Eine Umbenennung dort faellt damit als klare Meldung
  // auf, statt in jedem einzelnen Spec als "Projektlink nicht gefunden".
  for (const [key, fullName] of Object.entries(DEMO_PROJECTS)) {
    expect(fullName, `Praefix des Demo-Projekts "${key}"`).toContain(prefix)
    const suffix = fullName.slice(prefix.length)
    expect(seeder, `Projektname "${fullName}" im Seeder`).toContain(
      `f"{DEMO_PROJECT_PREFIX}${suffix}"`
    )
  }
})

/**
 * Die Zielabsicherung der Ad-hoc-Werkzeuge (`lib/baseUrl.ts`). Sie ist die einzige strukturelle
 * Sperre, die verhindert, dass `shot`/`drive` gegen etwas anderes als einen lokalen Pruefstack
 * laufen - und sie besteht aus DREI unabhaengigen Bedingungen: Protokoll `http:`, Host aus einer
 * Allowlist, Port ausdruecklich angegeben. Jede ist einzeln abgesichert, so wie auf der
 * Backend-Seite jeder Bestandteil der Seeder-Sperre seinen eigenen Abbruch-Testfall hat.
 *
 * Die Port-Pflicht ist dabei kein theoretischer Fall: im Python-Pendant `validate_demo_base_url`
 * war genau sie ein echter Review-Fund - "http://localhost" mit implizitem Port 80 kann einen
 * voellig anderen lokalen Dienst treffen.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05), ausgefuehrt und im PR belegt: mit gestrichener
 * Port-Pflicht in `resolveBaseUrl` faellt genau ein Fall dieses Tests, und zwar mit der Meldung
 * `verletzte Bedingung "Port nicht angegeben" (http://localhost)` - die uebrigen drei bleiben
 * gruen. Damit ist belegt, was die Anti-Vakuitaets-Regel verlangt: die Faelle sind einzeln
 * empfindlich, der Test besteht nicht global weiter, wenn eine der drei Bedingungen wegfaellt.
 *
 * Fuer die Host-Allowlist ist derselbe Nachweis NICHT gesondert ausgefuehrt worden: die
 * Arbeitsumgebung verweigert das Ausfuehren des Pruefsatzes, solange eine Host-Allowlist im
 * Arbeitsbaum entfernt ist. Der Fall ist strukturbaugleich zum belegten (dieselbe Schleife,
 * dieselbe Fall-eigene Meldung, dasselbe `||`-Glied), aber das ist eine Begruendung und keine
 * Messung - hier bewusst als solche gekennzeichnet statt als Nachweis ausgegeben.
 */

test('die Ziel-Allowlist der Werkzeuge laesst genau die lokalen Adressen durch', () => {
  // Positivfaelle zuerst - ohne sie waere auch eine Sperre "gruen", die schlicht ALLES ablehnt.
  expect(resolveBaseUrl(undefined), 'Variable nicht gesetzt').toBe(DEFAULT_BASE_URL)
  expect(resolveBaseUrl(''), 'leerer Wert').toBe(DEFAULT_BASE_URL)
  expect(resolveBaseUrl('   '), 'nur Leerzeichen').toBe(DEFAULT_BASE_URL)
  // Der praktische Fall: ein bereits laufender Stack belegt 8080.
  expect(resolveBaseUrl('http://localhost:8180'), 'abweichender Port').toBe('http://localhost:8180')
  expect(resolveBaseUrl('http://127.0.0.1:8180'), 'zweiter erlaubter Host').toBe(
    'http://127.0.0.1:8180'
  )
  // Auf die Origin reduziert - ein mitgegebener Pfad darf nicht Teil der Basis-URL werden.
  expect(resolveBaseUrl('http://localhost:8180/projects/2'), 'Pfadanteil').toBe(
    'http://localhost:8180'
  )
})

test('die Ziel-Allowlist der Werkzeuge weist jede der drei Bedingungen einzeln ab', () => {
  // Je Fall ist genau EINE Bedingung verletzt, die uebrigen sind erfuellt - faellt eine der drei
  // bei einer spaeteren Umgestaltung weg, wird genau ihre Zeile rot statt gar keine.
  const rejected: [string, string][] = [
    ['Protokoll', 'https://localhost:8080'],
    ['Host ausserhalb der Allowlist', 'http://beispiel.invalid:8080'],
    ['Port nicht angegeben', 'http://localhost'],
    ['ueberhaupt keine URL', 'nicht-eine-url'],
  ]

  for (const [bedingung, wert] of rejected) {
    expect(
      () => resolveBaseUrl(wert),
      `verletzte Bedingung "${bedingung}" (${wert}) muss zum Abbruch fuehren`
    ).toThrow()
  }

  // Kardinalitaet: ohne sie bestuende der Test auch mit einer leergelaufenen Fallliste.
  expect(rejected.length, 'Anzahl geprueter Abweisungsgruende').toBe(4)
})

/**
 * Der gespeicherte Anmeldezustand und die Origin, gegen die er gilt (Copilot-Fund, PR #329).
 *
 * Das Frontend legt sein Token in `localStorage` ab - und `localStorage` ist origin-gebunden.
 * Wechselt der Pruefstack den Port (auf Daniels Rechner der Normalfall, weil ein laufender
 * PhotoSort-Stack 8080 belegt), gehoert eine VORHANDENE Zustandsdatei zur alten Origin. Ein
 * blosser Existenz-Test liesse die Ad-hoc-Werkzeuge dann still abgemeldet laufen und ein Bild
 * der Anmeldeseite als vermeintlichen Anwendungszustand liefern.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05), ausgefuehrt: mit einer `authStateCoversOrigin`,
 * die unbesehen `true` liefert, fallen die drei Ablehnungsfaelle unten; mit der umgesetzten
 * Fassung sind alle vier gruen.
 */

function storageStateFuer(origin: string, schluessel: string): string {
  return JSON.stringify({
    cookies: [],
    origins: [{ origin, localStorage: [{ name: schluessel, value: 'ein-token' }] }],
  })
}

test('ein Anmeldezustand gilt nur fuer die Origin, unter der er entstanden ist', () => {
  const jetzt = 'http://localhost:8180'

  // Positivfall zuerst - ohne ihn bestuende auch eine Pruefung, die schlicht ALLES verwirft und
  // damit bei jedem Aufruf eine neue Anmeldung erzwaenge.
  expect(
    authStateCoversOrigin(storageStateFuer(jetzt, TOKEN_STORAGE_KEY), jetzt),
    'passende Origin mit Token'
  ).toBe(true)

  // Je Fall ist genau ein Grund verletzt.
  const abgelehnt: [string, string][] = [
    // Der eigentliche Anlass: Datei vorhanden, aber vom Lauf auf dem anderen Port.
    ['andere Origin', storageStateFuer('http://localhost:8080', TOKEN_STORAGE_KEY)],
    // Eintrag da, aber ohne das Token - z.B. nach einem Abmelden im selben Kontext.
    ['richtige Origin ohne Token', storageStateFuer(jetzt, 'irgendein-anderer-schluessel')],
    // Unlesbar: im Zweifel neu anmelden. Ein `true` waere hier der stille Abgemeldet-Lauf.
    ['unlesbarer Inhalt', '{kein gueltiges JSON'],
  ]

  for (const [grund, inhalt] of abgelehnt) {
    expect(authStateCoversOrigin(inhalt, jetzt), `Ablehnungsgrund "${grund}"`).toBe(false)
  }

  // Kardinalitaet: ohne sie bestuende der Test auch mit einer leergelaufenen Fallliste.
  expect(abgelehnt.length, 'Anzahl geprueter Ablehnungsgruende').toBe(3)
})

test('der Token-Schluessel der Werkzeuge stammt aus dem Frontend', () => {
  const token = repoFile('frontend/src/auth/token.ts')

  const match = /^const TOKEN_STORAGE_KEY = '([^']+)'$/m.exec(token)
  expect(match, 'TOKEN_STORAGE_KEY in frontend/src/auth/token.ts').not.toBeNull()

  // Doku-an-Code-Bindung wie oben beim Seeder: wird der Schluessel im Frontend umbenannt, faellt
  // es hier auf - statt jeden Ad-hoc-Lauf still abgemeldet zu machen.
  expect(TOKEN_STORAGE_KEY, 'Token-Schluessel des e2e-Pakets').toBe(match![1])
})
