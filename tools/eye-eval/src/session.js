/**
 * Zustandslogik der Vergleichsseite, ohne DOM. `page.js` bettet diese Datei beim Rendern ein
 * (ohne die `export`-Schlüsselwörter) und zeichnet nur noch das Ergebnis; keine Regel steht
 * doppelt in der Seite. Die Tests prüfen hier, wann „weiter“ erlaubt ist, was ein Bildfehler
 * sperrt und wie „zurück“ die frühere Wahl wieder zeigt.
 */
export function createSession({ photoIds, startIndex = 0, saved = {} } = {}) {
  const ids = [...photoIds];
  const gespeichert = saved;
  const start = Number(startIndex);
  let index = Number.isFinite(start) ? Math.max(0, Math.min(start, ids.length)) : 0;
  let choice = null;
  let bildKaputt = false;

  function aktuell() {
    return index < ids.length ? ids[index] : null;
  }

  function zustand() {
    const photoId = aktuell();
    const fertig = photoId === null;
    return {
      index,
      total: ids.length,
      photoId,
      fertig,
      choice,
      bildKaputt,
      canChoose: !fertig && !bildKaputt,
      nextEnabled: !fertig && (choice !== null || bildKaputt),
      backEnabled: index > 0,
      skipEnabled: !fertig,
    };
  }

  function zeige() {
    const photoId = aktuell();
    bildKaputt = false;
    choice = photoId === null ? null : (gespeichert[photoId] ?? null);
    return zustand();
  }

  function setzeWahl(wert) {
    const photoId = aktuell();
    if (photoId === null || bildKaputt) return zustand();
    choice = wert;
    gespeichert[photoId] = wert;
    return zustand();
  }

  /** Kein Bild, kein Urteil: die Wahlmöglichkeit fällt weg, das Weiterblättern bleibt. */
  function bildFehler() {
    if (aktuell() !== null) bildKaputt = true;
    return zustand();
  }

  function weiter() {
    if (aktuell() === null) return zustand();
    if (choice === null && !bildKaputt) return zustand();
    index += 1;
    return zeige();
  }

  function zurueck() {
    if (index > 0) index -= 1;
    return zeige();
  }

  function ueberspringen() {
    if (aktuell() !== null) index += 1;
    return zeige();
  }

  return { zeige, setzeWahl, bildFehler, weiter, zurueck, ueberspringen, zustand, aktuell };
}
