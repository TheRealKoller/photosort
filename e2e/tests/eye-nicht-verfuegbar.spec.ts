/**
 * specs/features/0383-modellwahl-je-projekt.md, Schritt 12: Die Kategorisierung steht auf Eye, der
 * Eye-Dienst läuft aber NICHT im Prüfstack (`docker-compose.e2e.yml` setzt `EYE_ENABLED=true`,
 * startet aber weder `eye` noch `eye-model`). Die Auswahl in den Projekteinstellungen ist also
 * möglich, die Ausführung scheitert - genau der halbe Zustand, der interessant ist.
 *
 * Zugesichert:
 *  - In den Projekteinstellungen lässt sich "Kategorisierung: Eye" wählen und speichern; die
 *    Bestätigung sagt, dass die Änderung für künftige Läufe gilt, und die API bestätigt den
 *    gespeicherten Wert (nicht nur die Oberfläche).
 *  - Die Laufwahl bietet GENAU ZWEI Wege; die Kurzfassung der Projektwahl nennt die Eye-Kategorie.
 *  - Nach der Wahl "Wie im Projekt eingestellt" nennt der Abschnitt die Lizenzmeldung
 *    (Zählkennung, keine Bildinhalte) und die Kostenvorschau "kostenfrei" für die Kategorisierung.
 *  - Der Start antwortet `503`; die Meldung sagt, dass nichts gestartet wurde, und bietet eine
 *    Wiederholung an. Es gibt KEINEN stillen Rückfall: der Lauf bleibt im Zustand "noch nicht
 *    klassifiziert", die Bilanz des alten Laufs bleibt stehen und die Wahl steht weiterhin auf
 *    "Wie im Projekt eingestellt".
 *
 * KEIN `finally`-Rückschreiben - und das ist keine Nachlässigkeit, sondern die Folge zweier
 * festgelegter Regeln: der Schreibendpunkt nimmt für `cloud` nur ein Modell mit hinterlegtem
 * API-Schlüssel an (`422` sonst), und der Prüfstack setzt beide Schlüssel bewusst leer. Eine
 * gespeicherte Eye-Wahl ist damit über die Schnittstelle nicht rücknehmbar (`e2e/lib/modelChoice.ts`
 * führt das aus). Ausgangspunkt jedes Laufs im Prüfstack ist deshalb der dokumentierte
 * Seed-Schritt; keine andere Spec liest die Laufwahl des Kriterien-Schritts.
 *
 * Desktop-only: der Gegenstand ist die Ablehnung, nicht die Geometrie; die Zustandsfolge ist in
 * beiden Breiten identisch, und ein zweiter Lauf schriebe denselben Nachweis.
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'
import { readModelChoice } from '../lib/modelChoice.ts'

test.use({
  expectedServerErrors: [
    // Der Ausloeser fragt den Eye-Dienst und bekommt keine Verbindung - der Server antwortet 503.
    { urlPattern: /\/api\/projects\/\d+\/classify$/, status: 503 },
  ],
})

test('ohne Eye-Dienst wird der Lauf sichtbar abgelehnt und nicht still ersetzt', async ({
  page,
}) => {
  // Der Ablauf besucht ZWEI Seiten (Einstellungen, Kriterien) und der 503 kommt erst nach der
  // Gesundheitspruefung des nicht laufenden Eye-Dienstes - die Standardgrenze von 30 s ist dafuer
  // knapp bemessen.
  test.setTimeout(120_000)
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  // Vorbedingung: der geseedete Bestand steht auf Cloud. Steht er schon auf Eye, belegt der Fall
  // die Auswahl nicht - dann bricht er hier mit dem Hinweis ab, neu zu seeden, statt still
  // durchzulaufen.
  const before = await readModelChoice(page, projectId)
  expect(
    before.category_method,
    'Ausgangszustand des Demo-Projekts (neu seeden, siehe docs/setup.md)',
  ).toBe('cloud')

  // 1. Einstellungen: Eye als Kategorisierung wählen und speichern.
  await page.goto(`/projects/${projectId}/settings`)
  const modellwahl = page.getByTestId('model-choice-section')
  await expect(modellwahl).toBeVisible()
  await modellwahl.getByRole('radio', { name: 'Kategorisierung: Eye' }).check()
  await modellwahl.getByRole('button', { name: 'Speichern' }).click()
  await expect(modellwahl.getByRole('status')).toHaveText('Gespeichert — gilt für künftige Läufe.')

  // Die API bestätigt den gespeicherten Wert - die Bestätigung der Oberfläche allein wäre ein
  // Versprechen, keine Zusage.
  expect(await readModelChoice(page, projectId)).toEqual({
    category_method: 'eye',
    category_model: null,
    landmark_model: before.landmark_model,
  })

  // 2. Laufwahl: genau zwei Wege, die Projektwahl nennt die Eye-Kategorie.
  await page.goto(`/projects/${projectId}/pipeline/kriterien`)
  const feldgruppe = page.getByRole('group', { name: 'Weg für diesen Durchlauf' })
  await expect(feldgruppe).toBeVisible()
  await expect(feldgruppe.getByRole('radio')).toHaveCount(2)
  const projektWeg = feldgruppe.getByRole('radio', { name: /^Wie im Projekt eingestellt/ })
  await expect(projektWeg).toBeEnabled()
  await expect(page.getByTestId('way-project-meta')).toContainText('Kategorisierung: Eye')

  // Ohne Wahl ist der Ausloeser gesperrt und der Grund steht als Satz daneben.
  await expect(page.getByTestId('classification-disabled-reason')).toHaveText(
    'Wähle einen Weg — ohne Wahl startet kein Lauf.',
  )

  // 3. Gewählt: der Abschnitt nennt die Lizenzmeldung, die Kostenvorschau das Wort.
  await projektWeg.check()
  await expect(page.getByTestId('classification-scope-text')).toContainText(
    'Für die Kategorisierung verlässt kein Foto diesen Server.',
  )
  await expect(page.getByTestId('classification-scope-text')).toContainText(
    'Lizenzmeldung mit einer Zählkennung',
  )
  const vorschau = page.getByTestId('classification-estimate')
  await expect(vorschau).toBeVisible()
  // "kostenfrei" ist ein Wort: die Eye-Kategorisierung trägt keinen Betrag, und ihre Grundlage
  // ist "Eye, auf diesem Server" - kein Anbieter, kein Modell.
  const kategorisierung = page.getByTestId('classification-estimate-part-categorization')
  await expect(kategorisierung).toContainText('kostenfrei')
  await expect(kategorisierung).toContainText('Eye, auf diesem Server')
  await expect(kategorisierung).not.toContainText('USD')

  // 4. Der Start scheitert an der fehlenden Verbindung - und zwar sichtbar, ohne Rückfall.
  await page
    .getByRole('button', { name: /^(Klassifizierung starten|Erneut klassifizieren)$/ })
    .click()

  const meldung = page.getByRole('alert').filter({ hasText: 'nicht gestartet' })
  await expect(meldung).toBeVisible()
  await expect(meldung).toContainText(
    'Der Lauf wurde nicht gestartet und es wurde nichts verändert.',
  )
  // Die Wiederholung ist Teil der 503-Antwort - ein Dienst kann zurückkommen.
  await expect(meldung.getByRole('button', { name: 'Erneut versuchen' })).toBeVisible()

  // Kein stiller Rückfall: der Abschnitt beschreibt keinen neuen Lauf (die Bilanz des alten
  // bleibt stehen) und die Wahl steht weiterhin auf "Wie im Projekt eingestellt" - sie gilt
  // für EINEN Durchlauf, und der ist nicht gestartet.
  await expect(page.getByTestId('classification-balance')).toHaveCount(1)
  await expect(projektWeg).toBeChecked()
})
