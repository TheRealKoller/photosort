import type { PhotoOut, RankingOut } from '../api/types'

/* Reine Ableitungen auf `PhotoOut.rankings` (specs/features/0300-nebenkategorien.md,
 * Umsetzungsschritt 9). Bewusst ein eigenes Modul und keine Inline-Ausdruecke in den Seiten: aus
 * `photo.ranking` (genau eine oder keine) ist eine LISTE geworden, und beide naheliegenden
 * Abkuerzungen sind falsch - `rankings[0]` ist nicht "die Hauptzeile", und ein
 * Falsyness-Filter auf `curation_position` verliert die Position 0. */

/**
 * Die HAUPTzugehoerigkeit eines Fotos, oder `null`, wenn es keine gibt (noch kein erfolgreicher
 * Lauf - oder, was nicht vorkommen darf, eine Liste ohne Hauptzeile).
 *
 * Ausdruecklich NICHT "das erste Element": die Reihenfolge der Antwort stellt die Hauptzeile zwar
 * nach vorn, aber die Rolle kommt aus `is_primary` und aus nichts sonst.
 */
export function primaryRanking(photo: PhotoOut): RankingOut | null {
  return photo.rankings.find((ranking) => ranking.is_primary) ?? null
}

/**
 * Die Zugehoerigkeiten, die zur angeforderten Kuratierungsauswahl gehoeren - also die, unter denen
 * die Kuratierung dieses Foto zeigen soll. Leer, wenn keine Auswahl angefordert wurde.
 *
 * Geprueft wird auf `!== null` und nicht auf Falsyness: `0` ist eine Zahl, keine Abwesenheit.
 * Die Reihenfolge der Antwort bleibt erhalten (Hauptzeile zuerst, dann Registry-Reihenfolge).
 */
export function curatedRankings(photo: PhotoOut): RankingOut[] {
  return photo.rankings.filter((ranking) => ranking.curation_position !== null)
}
