/**
 * Die acht Motive aus `backend/src/photosort/motifs.py::MOTIF_REGISTRY`, in deren Anzeigereihenfolge.
 *
 * Die Liste ist eine Kopie und keine Ableitung: der Werkzeugbaum läuft in einem eigenen Container
 * ohne das Backend-Paket. Ein Motiv, das hier fehlt, macht den Stärkevektor eines Fotos
 * unvollständig und wird gezählt, statt still auf sieben Motive zu vergleichen.
 */
export const MOTIF_KEYS = Object.freeze([
  "menschen",
  "landschaft",
  "bauwerk_sehenswuerdigkeit",
  "stadt_strasse",
  "tiere",
  "essen_trinken",
  "aktivitaet",
  "detail_stimmung",
]);
