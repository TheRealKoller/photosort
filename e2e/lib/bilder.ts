/**
 * Die eine Stelle fuer die Frage "sind die Bilder dieser Messflaeche geladen?".
 *
 * Eine Pruefdatei misst an einer Bildflaeche erst, nachdem `warteAufBilder` zurueckgekehrt ist,
 * und fuehrt kein eigenes Lade-Praedikat. Vorher stammt jeder Messwert aus dem Ladezustand: Die
 * Kachel hat ihre Endform, das Bild aber `naturalWidth` 0, und Kasten wie Treffertest sehen eine
 * leere Flaeche.
 */

import { expect, type Locator } from '@playwright/test'

/**
 * Eine Seite voll einzeln authentifizierter Blob-Abrufe braucht laenger als die fuenf Sekunden,
 * die `expect.poll` ohne Angabe wartet. Dieselbe Grenze gilt fuer jeden Fall, auch das Einzelbild.
 */
const IMAGE_LOAD_TIMEOUT_MS = 30_000

interface Bildstand {
  /** Flaechen, in denen kein passendes Bild steht. */
  ohneBild: number
  /** Flaechen mit mindestens einem noch nicht geladenen Bild. */
  ungeladen: number
  /** Flaechen, deren passende Bilder alle geladen sind. */
  geladen: number
}

/**
 * Laeuft im Browser. Playwright uebertraegt den Quelltext, nicht die Bindungen des Moduls - die
 * Funktion darf deshalb auf nichts ausserhalb ihres Rumpfs zugreifen.
 *
 * `bild` ist der Selektor des Bildes innerhalb der Flaeche; `null` heisst, die Flaeche IST das Bild.
 */
function bildstand(elements: Element[], bild: string | null): Bildstand {
  const stand = { ohneBild: 0, ungeladen: 0, geladen: 0 }
  for (const element of elements) {
    const bilder = bild === null ? [element] : [...element.querySelectorAll(bild)]
    if (bilder.length === 0) {
      stand.ohneBild += 1
    } else if (
      bilder.every(
        (image) => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0,
      )
    ) {
      stand.geladen += 1
    } else {
      stand.ungeladen += 1
    }
  }
  return stand
}

export interface Bildflaeche {
  /** Benennt die Flaeche in der Fehlermeldung, z.B. "Duplikat-Stapel". */
  flaeche: string
  /** Benennt das erwartete Bild in der Fehlermeldung, z.B. "Titelbild". */
  was: string
  /** Selektor des Bildes innerhalb jeder Flaeche; `null`, wenn der Locator selbst das Bild ist. */
  bild: string | null
  /**
   * `true`: Eine Flaeche ohne passendes Bild blockiert nicht (vorhandene Bilder muessen trotzdem
   * geladen sein). Ohne Angabe muss jede Flaeche ein geladenes Bild tragen.
   */
  ohneBildZulaessig?: boolean
}

/**
 * Wartet, bis in JEDER Flaeche des Locators das Bild geladen ist (`complete`, `naturalWidth > 0`).
 *
 * Vorbedingung ist eine sichtbare erste Flaeche - sonst waere eine leere Liste sofort "geladen".
 * Laeuft die Zeitgrenze ab, lautet die Meldung `<flaeche>: <was> nicht geladen` und ist damit von
 * jeder Geometrie-Zusicherung der Pruefdatei unterscheidbar.
 */
export async function warteAufBilder(flaechen: Locator, optionen: Bildflaeche): Promise<void> {
  const { flaeche, was, bild, ohneBildZulaessig = false } = optionen
  await expect(flaechen.first(), `${flaeche} vorhanden`).toBeVisible()
  await expect
    .poll(
      async () => {
        const stand = await flaechen.evaluateAll(bildstand, bild)
        return stand.ungeladen + (ohneBildZulaessig ? 0 : stand.ohneBild)
      },
      { timeout: IMAGE_LOAD_TIMEOUT_MS, message: `${flaeche}: ${was} nicht geladen` },
    )
    .toBe(0)
}

/** Momentaufnahme ohne Warten: Anzahl der Flaechen, deren Bilder bereits geladen sind. */
export async function zaehleGeladeneBilder(
  flaechen: Locator,
  bild: string | null,
): Promise<number> {
  const stand = await flaechen.evaluateAll(bildstand, bild)
  return stand.geladen
}
