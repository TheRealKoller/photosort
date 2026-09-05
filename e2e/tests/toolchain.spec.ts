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
