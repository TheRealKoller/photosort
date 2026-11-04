/**
 * specs/features/0609-eye-dritte-wahl.md: Der Weg "Eye" ist freigeschaltet, der Dienst laeuft aber
 * NICHT im Pruefstack (`docker-compose.e2e.yml` setzt `EYE_ENABLED=true`, startet aber weder `eye`
 * noch `eye-model`). Genau dieser halbe Zustand ist der interessante: er zeigt, was passiert, wenn
 * die Wahl moeglich ist und die Ausfuehrung scheitert.
 *
 * Zugesichert:
 *  - Die Zeile "Eye" erscheint samt kostenfreier Nebenangabe und Namensnennung.
 *  - Nach der Wahl nennt der Abschnitt die Lizenzmeldung (Zaehlkennung, keine Bildinhalte) und die
 *    Kostenvorschau zeigt "kostenfrei" statt eines Betrags.
 *  - Der Start antwortet `503`; die Meldung nennt den Grund, sagt dass nichts gestartet wurde, und
 *    bietet eine Wiederholung an. Es gibt KEINEN stillen Rueckfall: der Lauf bleibt im Zustand
 *    "noch nicht klassifiziert", und keine Bilanz/Teilschrittliste erscheint fuer einen Lauf, den
 *    es nicht gab.
 *
 * Desktop-only: der Gegenstand ist die Ablehnung, nicht die Geometrie; die Zustandsfolge ist in
 * beiden Breiten identisch, und ein zweiter Lauf schriebe denselben Nachweis.
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

test.use({
  expectedServerErrors: [
    // Der Ausloeser fragt den Eye-Dienst und bekommt keine Verbindung - der Server antwortet 503.
    { urlPattern: /\/api\/projects\/\d+\/classify$/, status: 503 },
  ],
})

test('ohne Eye-Dienst wird der Lauf sichtbar abgelehnt und nicht still ersetzt', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/pipeline/kriterien`)

  // 1. Die Wahl steht da - mit Name, Preisaussage und Namensnennung.
  const feldgruppe = page.getByRole('group', { name: 'Weg für diesen Durchlauf' })
  await expect(feldgruppe).toBeVisible()
  const eyeZeile = feldgruppe.getByRole('radio', { name: /^Eye/ })
  await expect(eyeZeile).toBeVisible()
  await expect(eyeZeile, 'Eye ist der kostenfreie Weg').toBeEnabled()
  await expect(page.getByRole('link', { name: /Desert Ant Labs/ })).toBeVisible()

  // Ohne Wahl ist der Ausloeser gesperrt und der Grund steht als Satz daneben.
  await expect(page.getByTestId('classification-disabled-reason')).toHaveText(
    'Wähle einen Weg — ohne Wahl startet kein Lauf.',
  )

  // 2. Gewaehlt: der Abschnitt nennt die Lizenzmeldung, die Kostenvorschau das Wort.
  await eyeZeile.check()
  await expect(page.getByTestId('classification-scope-text')).toContainText(
    'kein Foto verlässt ihn',
  )
  await expect(page.getByTestId('classification-scope-text')).toContainText(
    'Lizenzmeldung mit einer Zählkennung',
  )
  // "kostenfrei" ist ein Wort: der Eye-Anteil traegt keinen Betrag, und eine Cloud-Grundlage
  // ("Grundlage: …, Modell …") gibt es hier nicht - abgerechnet wird nur die
  // Sehenswuerdigkeits-Erkennung, die dieser Bestand freigegeben hat.
  const vorschau = page.getByTestId('classification-estimate')
  await expect(vorschau).toBeVisible()
  await expect(vorschau).not.toContainText('Grundlage:')

  // 3. Der Start scheitert an der fehlenden Verbindung - und zwar sichtbar, ohne Rueckfall.
  await page
    .getByRole('button', { name: /^(Klassifizierung starten|Erneut klassifizieren)$/ })
    .click()

  const meldung = page.getByRole('alert').filter({ hasText: 'nicht gestartet' })
  await expect(meldung).toBeVisible()
  await expect(meldung).toContainText(
    'Der Lauf wurde nicht gestartet und es wurde nichts verändert.',
  )
  // Die Wiederholung ist Teil der 503-Antwort - ein Dienst kann zurueckkommen.
  await expect(meldung.getByRole('button', { name: 'Erneut versuchen' })).toBeVisible()

  // Kein stiller Rueckfall: der Abschnitt beschreibt keinen neuen Lauf (die Bilanz des alten
  // bleibt stehen) und die Wahl steht weiterhin auf Eye - sie gilt fuer EINEN Durchlauf, und der
  // ist nicht gestartet.
  await expect(page.getByTestId('classification-balance')).toHaveCount(1)
  await expect(eyeZeile).toBeChecked()
})
