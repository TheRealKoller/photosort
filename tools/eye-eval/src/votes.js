/**
 * Übersetzt die rohen Seitenwahlen (A = links) in Eye-Urteile. `pages` legt je Foto fest, welche
 * Seite links steht; eine A-Stimme heißt nur dann „Eye besser“, wenn Eye dort auch links stand.
 * Ohne diese Umrechnung mittelt sich jedes Ergebnis gegen 50/50, weil die Seiten gemischt sind.
 */
export class VoteError extends Error {
  constructor(message) {
    super(message);
    this.name = "VoteError";
  }
}

export function mapVotes({ choices, assignments }) {
  const seiten = new Map((assignments ?? []).map((eintrag) => [eintrag.photoId, eintrag.left]));
  let better = 0;
  let same = 0;
  let worse = 0;

  for (const [photoId, choice] of Object.entries(choices ?? {})) {
    if (choice === "same") {
      same += 1;
      continue;
    }
    const links = seiten.get(Number(photoId));
    if (links !== "first" && links !== "second") {
      throw new VoteError(
        `Für Foto ${photoId} fehlt die A/B-Zuordnung in ab-map.json; ohne sie ist die Stimme nicht deutbar.`,
      );
    }
    const eyeStandLinks = links === "second";
    const stimmeFuerLinks = choice === "a";
    if (eyeStandLinks === stimmeFuerLinks) better += 1;
    else worse += 1;
  }

  return { better, same, worse, decided: better + same + worse };
}

export function ladeAbMap(text, pfad) {
  let gelesen;
  try {
    gelesen = JSON.parse(text);
  } catch (error) {
    throw new VoteError(`${pfad} ist beschädigt und nicht lesbar: ${error.message}`);
  }
  if (!gelesen || typeof gelesen !== "object" || !gelesen.purposes || typeof gelesen.purposes !== "object") {
    throw new VoteError(`${pfad} ist beschädigt: „purposes“ fehlt.`);
  }
  return gelesen;
}
