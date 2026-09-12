import type { MotifSetOut } from '../api/types'

/**
 * Das feste Achter-Motivset in Anzeigereihenfolge, genau wie es `GET /motifs` liefert
 * (specs/features/0427-motive-mit-staerke.md, Registry in `backend/src/photosort/motifs.py`).
 *
 * DIE EINZIGE Motivliste im Frontend - und sie ist eine TEST-Fixture, kein Produktivcode: das Set
 * kommt zur Laufzeit vom Server, und eine gepflegte Kopie im Produktivpfad waere eine dauerhaft
 * driftende zweite Liste. Hier liegt sie GETEILT statt je Testdatei erneut, weil sie auf mehreren
 * Ebenen gebraucht wird: als Parameter der reinen Anzeigehelfer (`utils/motifLabels`) und als
 * Rueckgabewert des gemockten `listMotifs` in Baustein- und Seitentests.
 *
 * `definition`/`delimitation` sind gekuerzt, wo keine Anzeigestelle sie auswertet - das Glossar
 * der Staerkeliste tut es, deshalb tragen sie unterscheidbare Werte statt ueberall dasselbe `d`.
 *
 * `locally_assessable` spiegelt die Serverantwort: `aktivitaet` und `detail_stimmung` sind ohne
 * Cloud-Aussage strukturell nicht erreichbar.
 */
export const MOTIF_SET: MotifSetOut = {
  items: [
    {
      key: 'menschen',
      display_name: 'Menschen',
      definition: 'Personen sind zu sehen.',
      delimitation: 'Nicht bei Personendarstellungen als Skulptur.',
      locally_assessable: true,
    },
    {
      key: 'landschaft',
      display_name: 'Landschaft',
      definition: 'Eine weiträumige Außenszene ist zu sehen.',
      delimitation: 'Nicht bei Detailaufnahmen einzelner Naturelemente.',
      locally_assessable: true,
    },
    {
      key: 'bauwerk_sehenswuerdigkeit',
      display_name: 'Bauwerk und Sehenswürdigkeit',
      definition: 'Ein Bauwerk oder eine Sehenswürdigkeit ist zu sehen.',
      delimitation: 'Nicht für eine Bebauung als bloßen Hintergrund.',
      locally_assessable: true,
    },
    {
      key: 'stadt_strasse',
      display_name: 'Stadt und Straße',
      definition: 'Eine Stadt- oder Straßenszene ist zu sehen.',
      delimitation: 'Ein Fahrzeug ist Teil der Straßenszene.',
      locally_assessable: true,
    },
    {
      key: 'tiere',
      display_name: 'Tiere',
      definition: 'Tiere sind zu sehen.',
      delimitation: 'Nicht bei zubereitetem Fleisch als Speise.',
      locally_assessable: true,
    },
    {
      key: 'essen_trinken',
      display_name: 'Essen und Trinken',
      definition: 'Speisen oder Getränke sind zu sehen.',
      delimitation: 'Nicht bei lebenden Nutzpflanzen im Feld.',
      locally_assessable: true,
    },
    {
      key: 'aktivitaet',
      display_name: 'Aktivität',
      definition: 'Eine erkennbare Handlung ist im Bild.',
      delimitation: 'Nicht bei bloßem Posieren mit Sportgerät.',
      locally_assessable: false,
    },
    {
      key: 'detail_stimmung',
      display_name: 'Detail und Stimmung',
      definition: 'Eine Nah- oder Stimmungsaufnahme ist zu sehen.',
      delimitation: 'Nicht als Auffangwert für „nichts erkannt“.',
      locally_assessable: false,
    },
  ],
  strength_bands: { strong: 2 / 3, medium: 1 / 3 },
}

/** Die acht Schluessel in Registry-Reihenfolge - fuer Reihenfolge-Assertions. */
export const MOTIF_KEYS = MOTIF_SET.items.map((item) => item.key)
