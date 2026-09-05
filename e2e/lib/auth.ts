/**
 * Anmeldung gegen den Pruefstack.
 *
 * Security-Muss-Kriterium M7: Der Anmeldeschritt schlaegt bei Misserfolg HART fehl, ohne Fallback
 * auf einen anonymen Lauf. Die Zugangsdaten unten existieren nur in einer demo-geseedeten
 * Datenbank - ein fehlschlagender Login ist damit selbst die Anzeige "falsches Ziel".
 */

import { expect, type Page } from '@playwright/test'

/**
 * Muss zu AUTH_SEED_USER1_* in `docker-compose.e2e.yml` passen. Bewusst hier im Klartext und
 * nicht ueber eine Umgebungsvariable: der Wert ist Teil der Pruefstack-Definition, nicht ein
 * Geheimnis - und ein Auseinanderlaufen faellt sofort als harter Login-Fehlschlag auf.
 */
export const DEMO_USERNAME = 'e2e-daniel'
export const DEMO_PASSWORD = 'e2e-only-password-1'

export async function logIn(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Benutzername').fill(DEMO_USERNAME)
  await page.getByLabel('Passwort').fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Anmelden' }).click()

  // Zielzustand statt Wartezeit: die App-Huelle erscheint erst nach erfolgreicher Anmeldung.
  // Schlaegt der Login fehl, laeuft diese Zusicherung in ihre Zeitgrenze und der Lauf bricht ab -
  // genau das gewollte harte Scheitern.
  await expect(page.getByRole('banner')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
}
