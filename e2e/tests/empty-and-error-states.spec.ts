/**
 * Leerer Zustand und Fehlerzustand rendern SICHTBAR statt als weisse Flaeche.
 *
 * Der naheliegende Fehler beim Pruefen dieser Zusage ist der immer-gruene Test: "Element
 * vorhanden" ist auch dann erfuellt, wenn das Element auf Hoehe 0 kollabiert ist oder die Seite
 * dauerhaft im Ladezustand haengt (Edge Case E10 der Spec 0174). Jede Zusicherung unten koppelt
 * deshalb sichtbaren Text an eine Geometrie- bzw. Abwesenheitsbedingung.
 *
 * RANDFALL E3 - DER ORDNER-BROWSER OHNE OPENCLOUD: Der Pruefstack enthaelt bewusst keine
 * OpenCloud-Instanz, der Ordner-Browser erzeugt dort also ERWARTETE Fehler. Sie sind hier eng
 * umrissen und im Spec sichtbar (dieser Endpunkt, dieser Statuscode) statt als globale
 * Ausnahmeliste in der Fixture. Der Endpunkt antwortet mit 400 (fehlende Konfiguration ist ein
 * Client-, kein Serverfehler) - die zentrale "keine 5xx"-Zusicherung bleibt damit unangetastet
 * und musste nicht abgesenkt werden.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05), alle drei Tests einzeln - siehe PR-Beschreibung:
 * `main { display: none }` -> "Aussage des Leerzustands: expected visible, received hidden";
 * `[role="img"] { display: none }` -> "Platzhalter fuer das Foto ohne Cache-Datei: expected 1,
 * received 0"; ein zusaetzlich eingehaengter Ladehinweis -> "Ladeanzeige nach dem Fehlschlag:
 * expected 0, received 1".
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/**
 * Der Ordner-Browser laeuft ueber die Wiederholungen des Query-Clients (drei Versuche mit
 * wachsendem Abstand), bevor er in den Fehlerzustand geht. Das ist eine auf den ZIELZUSTAND
 * gerichtete Zeitgrenze, keine feste Wartezeit - der Test wartet nicht ab, sondern hoert auf zu
 * warten, sobald die Fehlermeldung da ist.
 */
const RETRY_BUDGET_MS = 20_000

/** Der Ordner-Browser des Pruefstacks - ohne OpenCloud-Konfiguration eine 400er-Antwort. */
const EXPECTED_BROWSE_ERROR = { path: '/opencloud/browse', status: 400 }

test('leeres Projekt zeigt eine sichtbare Aussage statt einer leeren Flaeche', async ({ page }) => {
  const emptyId = await demoProjectId(page, DEMO_PROJECTS.empty)
  await page.goto(`/projects/${emptyId}/photos`)

  const emptyMessage = page.getByText('Keine Fotos mit diesem Filter.')
  await expect(emptyMessage, 'Aussage des Leerzustands').toBeVisible()

  // Sichtbarkeit allein reichte nicht: ein auf Hoehe 0 kollabierter Container bestuende sie in
  // Playwright nicht, ein leerer Textknoten in einem hohen Container schon.
  const messageBox = await emptyMessage.boundingBox()
  expect(messageBox, 'Rechteck der Leerzustands-Aussage').not.toBeNull()
  expect(messageBox!.height, 'Hoehe der Leerzustands-Aussage').toBeGreaterThan(0)

  // Und die Seite ist WIRKLICH die des leeren Projekts, nicht eine Weiterleitung: keine einzige
  // Foto-Kachel. Exakte Kardinalitaet statt "wenige".
  await expect(
    page.getByRole('listitem').filter({ has: page.locator('a[href*="/photos/"]') }),
    'Foto-Kacheln im leeren Projekt'
  ).toHaveCount(0)
})

test('Fehlerzustands-Projekt zeigt Fehlertext und Platzhalter sichtbar', async ({ page }) => {
  const errorId = await demoProjectId(page, DEMO_PROJECTS.error)

  // 1. Fehlgeschlagener Lauf mit nicht-leerem Fehlertext auf dem Pipeline-Schritt.
  await page.goto(`/projects/${errorId}/pipeline/scan`)
  // "Demo-Fehlerzustand" ist der eigene Marker des Seeders im Fehlertext - ein stabiler Anker,
  // ohne den vollstaendigen Satz zu verdoppeln.
  const errorText = page.getByText(/Demo-Fehlerzustand/).first()
  await expect(errorText, 'Fehlertext des fehlgeschlagenen Laufs').toBeVisible()
  const errorBox = await errorText.boundingBox()
  expect(errorBox, 'Rechteck des Fehlertexts').not.toBeNull()
  expect(errorBox!.height, 'Hoehe des Fehlertexts').toBeGreaterThan(0)

  // 2. Foto ohne Cache-Datei: der Platzhalter "wird noch verarbeitet" statt eines kaputten Bildes
  // oder einer leeren Kachel.
  await page.goto(`/projects/${errorId}/photos`)
  const placeholder = page.getByRole('img', { name: /wird noch verarbeitet$/ })
  await expect(placeholder, 'Platzhalter fuer das Foto ohne Cache-Datei').toHaveCount(1)
  await expect(placeholder).toBeVisible()
  const placeholderBox = await placeholder.boundingBox()
  expect(placeholderBox, 'Rechteck des Platzhalters').not.toBeNull()
  expect(placeholderBox!.height, 'Hoehe des Platzhalters').toBeGreaterThan(0)
})

test('Ordner-Browser zeigt ohne OpenCloud eine Fehlermeldung statt eines Dauer-Ladezustands', async ({
  page,
  sessionLog,
}) => {
  await page.goto('/projects/new')

  const loading = page.getByText('Ordner werden geladen…')
  const alert = page.getByRole('alert')

  await expect(alert, 'Fehlermeldung des Ordner-Browsers').toBeVisible({ timeout: RETRY_BUDGET_MS })
  // Der eigentliche Gehalt der Zusage: die Ladeanzeige ist DANACH weg. Ein Aufbau, der beides
  // gleichzeitig zeigt, ist fuer den Benutzer nicht von "haengt noch" unterscheidbar.
  await expect(loading, 'Ladeanzeige nach dem Fehlschlag').toHaveCount(0)

  const alertBox = await alert.boundingBox()
  expect(alertBox, 'Rechteck der Fehlermeldung').not.toBeNull()
  expect(alertBox!.height, 'Hoehe der Fehlermeldung').toBeGreaterThan(0)

  // Eng umrissene Erwartung an den bewusst fehlenden OpenCloud-Dienst (E3): dieser Endpunkt,
  // dieser Statuscode. Die Zusicherung laeuft ueber die IMMER mitgeschriebene Sitzungsmitschrift -
  // sie belegt zugleich, dass das Werkzeug Laufzeitfehler ohne Zutun des Aufrufers wahrnimmt.
  const browseFailures = sessionLog.failedRequests.filter((request) =>
    request.url.includes(EXPECTED_BROWSE_ERROR.path)
  )
  expect(
    browseFailures.map((request) => request.status),
    `Antwortstatus von ${EXPECTED_BROWSE_ERROR.path} ohne OpenCloud`
  ).toContain(EXPECTED_BROWSE_ERROR.status)
  expect(
    sessionLog.console.filter((message) => message.type === 'error').length,
    'mitgeschriebene Konsolenfehler'
  ).toBeGreaterThan(0)
})
