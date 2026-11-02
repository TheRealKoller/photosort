import { createHash } from "node:crypto";
import { existsSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Cache-Schlüssel und -Pfad der `display`-Variante, wortgleich zu
 * `backend/src/photosort/thumbnails.py::cache_key`/`display_path`.
 *
 * Die Bindung ist funktional nötig: Das Werkzeug muss genau die Datei finden, die die Cloud
 * bekommen hat, und beide Seiten müssen identische Pixel sehen. Ändert sich die Schlüsselbildung
 * im Backend, findet das Werkzeug keine Datei und zählt jedes Foto als Ausfall — der Lauf bricht
 * dann über die Mindestgröße ab, statt still auf einem anderen Bild zu vergleichen.
 */
export function cacheKey(photoId, etag) {
  return createHash("sha256").update(`${photoId}:${etag}`).digest("hex");
}

export function displayVariantName(photoId, etag) {
  return `${cacheKey(photoId, etag)}_display.jpg`;
}

export function displayPath(cacheDir, photoId, etag) {
  return join(cacheDir, displayVariantName(photoId, etag));
}

/**
 * Prüfprädikat für die Stichprobe: existiert die `display`-Datei zum AKTUELLEN etag und ist sie
 * nicht leer? Eine fehlende Datei ist der Ausfall — sie entsteht genau dann, wenn der Cache zu
 * einem älteren etag gehört oder die Variante nie erzeugt wurde.
 */
export function cacheExistsIn(cacheDir) {
  return (photoId, etag) => {
    const path = displayPath(cacheDir, photoId, etag);
    return existsSync(path) && statSync(path).size > 0;
  };
}
