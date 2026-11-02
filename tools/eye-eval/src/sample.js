import { cacheKey } from "./cache.js";

/**
 * Stichprobe für den Vergleich: mindestens 100 Fotos je Projekt aus mindestens zwei Projekten
 * unterschiedlicher Art.
 *
 * Die Menge ist die der heutigen Cloud-Bewertung: eine `photo_motif_assessments`-Zeile mit
 * `source='CLOUD'` UND eine Zeile in `photo_album_suitability` — das zusammengesetzte Kriterium,
 * mit dem die Anwendung selbst „vollständig cloud-bewertet" feststellt. Ein Foto, dessen
 * `display`-Datei nicht zum etag passt, fällt aus der Stichprobe und wird gezählt; fällt ein
 * Projekt dadurch unter 100, bricht der Lauf ab statt still zu verkleinern.
 *
 * Die Auswahl ist seed-deterministisch, damit ein abgebrochener Lauf dieselbe Stichprobe
 * wiederverwendet und der Beleg nachvollziehbar bleibt.
 */
export const MIN_PHOTOS_PER_PROJECT = 100;
export const MIN_PROJECTS = 2;
export const DEFAULT_SAMPLE_SEED = 20261102;

export class SampleError extends Error {
  constructor(message) {
    super(message);
    this.name = "SampleError";
  }
}

/** Kandidaten mit beiden Hälften des Cloud-Kriteriums. */
export function eligibleCandidates(rows) {
  return rows.filter((row) => row.cloudMotifAssessment && row.albumSuitability);
}

function normalisierteArt(kind) {
  return typeof kind === "string" ? kind.trim().toLowerCase() : "";
}

function pruefeProjekte(projects) {
  if (!Array.isArray(projects) || projects.length < MIN_PROJECTS) {
    throw new SampleError(
      `Es braucht mindestens zwei Projekte unterschiedlicher Art, angegeben waren ${
        Array.isArray(projects) ? projects.length : 0
      }.`,
    );
  }

  const gesehen = new Map();
  for (const project of projects) {
    const kind = normalisierteArt(project.kind);
    if (kind === "") {
      throw new SampleError(
        `Projekt ${project.projectId} hat keine Art-Angabe; zwei Projekte unterschiedlicher Art sind Pflicht.`,
      );
    }
    if (gesehen.has(kind)) {
      throw new SampleError(
        `Projekt ${project.projectId} und Projekt ${gesehen.get(kind)} tragen dieselbe Art "${kind}"; zwei Projekte unterschiedlicher Art sind Pflicht.`,
      );
    }
    gesehen.set(kind, project.projectId);
  }
}

/** FNV-1a über die Saat und das Projekt: stabil über Läufe und Plattformen. */
function saatFuer(seed, projectId) {
  let hash = 0x811c9dc5;
  for (const zeichen of `${seed}:${projectId}`) {
    hash ^= zeichen.codePointAt(0);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash;
}

function zufallsfolge(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function zieheAuswahl(photos, anzahl, seed) {
  const gemischt = [...photos];
  const zufall = zufallsfolge(saatFuer(seed, photos[0].projectId));
  for (let index = gemischt.length - 1; index > 0; index -= 1) {
    const tausch = Math.floor(zufall() * (index + 1));
    [gemischt[index], gemischt[tausch]] = [gemischt[tausch], gemischt[index]];
  }
  return gemischt
    .slice(0, anzahl)
    .sort((links, rechts) => links.photoId - rechts.photoId);
}

export function selectSample({
  projects,
  candidates,
  cacheExists,
  perProject = MIN_PHOTOS_PER_PROJECT,
  seed = DEFAULT_SAMPLE_SEED,
}) {
  if (typeof cacheExists !== "function") {
    throw new SampleError(
      "cacheExists fehlt: ohne Etag/Cache-Abgleich wäre die Stichprobe blind für abweichende Cache-Stände.",
    );
  }
  pruefeProjekte(projects);

  const kandidaten = eligibleCandidates(candidates ?? []);
  const proProjekt = [];

  for (const project of projects) {
    const eigene = kandidaten.filter((row) => row.projectId === project.projectId);
    const stimmig = eigene.filter((row) => cacheExists(row.photoId, row.etag));
    const ausfaelle = eigene.length - stimmig.length;

    if (stimmig.length < perProject) {
      throw new SampleError(
        `Projekt ${project.projectId} hat nach dem Etag/Cache-Abgleich ${stimmig.length} von ${perProject} nötigen Fotos (${eigene.length} cloud-bewertet, ${ausfaelle} Ausfälle). Die Stichprobe wird nicht still verkleinert.`,
      );
    }

    const photos = zieheAuswahl(stimmig, perProject, seed).map((row) => ({
      photoId: row.photoId,
      projectId: row.projectId,
      etag: row.etag,
      cacheKey: cacheKey(row.photoId, row.etag),
    }));

    proProjekt.push({
      projectId: project.projectId,
      kind: project.kind,
      counts: {
        eligible: eigene.length,
        inconsistent: ausfaelle,
        available: stimmig.length,
        selected: photos.length,
      },
      selected: photos.map((photo) => photo.photoId),
      photos,
    });
  }

  return {
    seed,
    counts: {
      projects: proProjekt.length,
      photos: proProjekt.reduce((summe, project) => summe + project.photos.length, 0),
      inconsistent: proProjekt.reduce(
        (summe, project) => summe + project.counts.inconsistent,
        0,
      ),
    },
    projects: proProjekt,
  };
}
