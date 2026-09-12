import type { MotifKey, MotifOut } from '../api/types'

// Die Anzeigetabelle kommt zur LAUFZEIT vom Server (`GET /motifs`); im Frontend wird keine zweite
// gepflegt.
//
// Beide Helfer sind bewusst REINE FUNKTIONEN mit dem geladenen Set als EXPLIZITEM Parameter: eine
// modul-globale, vom Query-Cache befuellte Variable machte sie nur noch mit
// `QueryClientProvider` testbar und ihre Tests von Query-Zustand abhaengig.
//
// `motifs` darf jederzeit leer sein (Set noch nicht geladen) - dann greift der generische
// Fallback, kein Absturz und kein leeres Label.

export type MotifSet = readonly MotifOut[]

/**
 * Generischer Fallback fuer einen Schluessel, der NICHT im geladenen Set steht - praktisch nur fuer
 * einen Altwert aus der Laufhistorie und fuer die kurze Phase, in der das Set noch laedt. Reine
 * Kosmetik (erster Buchstabe gross), kein Uebersetzungsschritt.
 */
function genericFallback(motifKey: string): string {
  if (motifKey.length === 0) {
    return motifKey
  }
  return motifKey.charAt(0).toUpperCase() + motifKey.slice(1)
}

function findEntry(motifKey: string, motifs: MotifSet): MotifOut | null {
  for (const entry of motifs) {
    if (entry.key === motifKey) {
      return entry
    }
  }
  return null
}

/**
 * Anzeigename eines `motif_key`: der `display_name` aus dem geladenen Set, sonst der generische
 * Fallback. Bewusst eine lineare Suche ueber genau acht Eintraege statt eines aus dem Set gebauten
 * Objekt-Lookups: so gibt es keinen `Object.prototype`-Durchgriff. Ein Schluessel wie `"toString"`
 * trifft hier strukturell keinen Eintrag und faellt korrekt auf den Fallback.
 */
export function formatMotifKey(motifKey: MotifKey, motifs: MotifSet): string {
  return findEntry(motifKey, motifs)?.display_name ?? genericFallback(motifKey)
}

/**
 * Ob ein Motiv OHNE Cloud-Aussage beurteilbar ist - ausschliesslich aus der Serverantwort, nie aus
 * einer im Frontend gepflegten Schluesselliste.
 *
 * AUSFALLRICHTUNG: ein unbekannter Schluessel (Altwert, Set noch nicht geladen) gilt als
 * beurteilbar. Damit zeigt die Zeile ihre ZAHL statt des Satzes "lokal nicht beurteilbar" - der
 * waere eine Aussage, die niemand getroffen hat.
 */
export function isLocallyAssessable(motifKey: MotifKey, motifs: MotifSet): boolean {
  return findEntry(motifKey, motifs)?.locally_assessable ?? true
}
