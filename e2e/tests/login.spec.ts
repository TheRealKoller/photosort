/**
 * Das Anmeldeformular selbst - der einzige Pfad, den das vorgelagerte Setup-Projekt verdeckt.
 *
 * Bewusst funktional statt geometrisch: hier geht es nicht um eine Zusage, die jsdom nicht
 * pruefen kann, sondern um den einen Ablauf, den ALLE uebrigen Specs ueberspringen, weil sie mit
 * gespeichertem Sitzungszustand starten. Faellt die Anmeldung aus, waeren alle anderen Specs
 * still auf die Login-Weiterleitung gelaufen.
 *
 * `storageState` wird hier ausdruecklich auf leer gesetzt und ueberschreibt damit den des
 * Projekts - sonst waere der Benutzer bereits angemeldet und die Seite leitete sofort weiter.
 *
 * ZAHLENGRENZE, DIE MAN KENNEN MUSS: `POST /auth/login` ist serverseitig auf 5 Anfragen pro
 * Minute und IP begrenzt. Ein vollstaendiger Lauf braucht drei (Setup-Projekt + die zwei Tests
 * hier) und bleibt damit darunter - mehrere Laeufe kurz hintereinander (typisch beim lokalen
 * Entwickeln an genau diesem Spec) laufen dagegen in eine 429-Antwort, die sich wie ein
 * fehlgeschlagener Login anfuehlt. Kein Fehler des Specs, aber der erste Verdacht bei einem
 * unerwartet roten Anmeldelauf.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit dem RICHTIGEN Passwort
 * im Falschanmeldungs-Test meldete der Spec "Fehlermeldung nach falscher Anmeldung: expected
 * visible, received hidden"; die Zusicherung haengt also tatsaechlich an der Abweisung und nicht
 * daran, dass irgendein Alert auf der Seite steht.
 */

import { DEMO_PASSWORD, DEMO_USERNAME } from '../lib/auth.ts'
import { expect, test } from '../lib/fixtures.ts'

test.use({ storageState: { cookies: [], origins: [] } })

test('falsche Zugangsdaten zeigen eine sichtbare Fehlermeldung', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel('Benutzername').fill(DEMO_USERNAME)
  await page.getByLabel('Passwort').fill(`${DEMO_PASSWORD}-falsch`)
  await page.getByRole('button', { name: 'Anmelden' }).click()

  const alert = page.getByRole('alert')
  await expect(alert, 'Fehlermeldung nach falscher Anmeldung').toBeVisible()
  const alertBox = await alert.boundingBox()
  expect(alertBox, 'Rechteck der Fehlermeldung').not.toBeNull()
  expect(alertBox!.height, 'Hoehe der Fehlermeldung').toBeGreaterThan(0)

  // Vorbedingung gegen den trivialen Grün-Fall in die andere Richtung: die Abweisung hat auch
  // wirklich NICHT angemeldet. Ein sichtbarer Alert bei gleichzeitig geoeffneter App-Huelle waere
  // der schlimmere Fehler von beiden.
  await expect(page, 'Verbleib auf der Anmeldeseite').toHaveURL(/\/login$/)
  await expect(page.getByRole('banner'), 'App-Huelle nach abgewiesener Anmeldung').toHaveCount(0)
})

test('richtige Zugangsdaten fuehren in die Anwendung', async ({ page }) => {
  await page.goto('/login')
  // Ohne diese Zusicherung koennte der Test auf einer bereits angemeldeten Sitzung laufen und
  // waere dann gruen, ohne das Formular je benutzt zu haben.
  await expect(page.getByRole('banner'), 'App-Huelle vor der Anmeldung').toHaveCount(0)

  await page.getByLabel('Benutzername').fill(DEMO_USERNAME)
  await page.getByLabel('Passwort').fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Anmelden' }).click()

  await expect(page.getByRole('banner'), 'App-Huelle nach der Anmeldung').toBeVisible()
  await expect(page.getByRole('heading', { name: 'Projekte' })).toBeVisible()
  await expect(page, 'Weiterleitung weg von der Anmeldeseite').not.toHaveURL(/\/login$/)

  // Der Token liegt im localStorage (nicht in einem Cookie) - genau deshalb traegt der
  // gespeicherte Sitzungszustand der uebrigen Specs ihn ueber `origins` statt ueber `cookies`.
  const token = await page.evaluate(() => window.localStorage.getItem('photosort_token'))
  expect(token, 'Anmelde-Token im localStorage').not.toBeNull()
})
