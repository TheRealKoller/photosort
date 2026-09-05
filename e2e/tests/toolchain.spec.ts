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

import { expect, test } from '../lib/fixtures.ts'
import { VIEWPORTS } from '../lib/viewports.ts'

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
