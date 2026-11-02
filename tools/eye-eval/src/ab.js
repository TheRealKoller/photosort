import { createHash } from "node:crypto";

/**
 * A/B-Zuordnung je Foto: seed-deterministisch aus Saat, Zweck und Foto-Id.
 *
 * Warum nicht die Position in der Liste: eine feste Alternation („gerade links“) ist nach zwei
 * Fotos durchschaut und macht den Vergleich wertlos. Die Id geht in den Hash ein, damit dieselbe
 * Wahl über ein Neuladen stabil bleibt und trotzdem kein Muster entsteht.
 */
export function assignSides({ seed, purpose, photoId }) {
  const bytes = createHash("sha256").update(`${seed}:${purpose}:${photoId}`).digest();
  return (bytes[0] & 1) === 1 ? "first" : "second";
}
