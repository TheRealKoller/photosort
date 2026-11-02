import { MOTIF_KEYS } from "./motifs.js";

/**
 * Maßstab des Vergleichs: der heutige Cloud-Stand je Foto, gelesen aus Postgres über eine
 * Verbindung, die sich selbst als read-only ausweist (S13) und ausschließlich die Tabellen aus
 * S14 liest.
 *
 * `assertReadOnly` prüft `SHOW default_transaction_read_only` und bricht bei allem außer `on` ab:
 * die Sitzungsvariable ist der einzige Schutz, den dieses Werkzeug hat, und sie wird gemessen,
 * nicht angenommen. Die Abfragen sind reine `SELECT`s auf einer festen Tabellenliste; `tableNames`
 * macht die Liste prüfbar.
 */
export const BASELINE_TABLES = Object.freeze([
  "photos",
  "photo_motif_strengths",
  "photo_motif_assessments",
  "photo_album_suitability",
  "photo_fine_labels",
  "fine_labels",
  "photo_landmark_detections",
  "remote_category_classification_runs",
  "criterion_scoring_runs",
]);

export class BaselineError extends Error {
  constructor(message) {
    super(message);
    this.name = "BaselineError";
  }
}

export function readOnlyQueryOptions() {
  return "-c default_transaction_read_only=on";
}

export function assertReadOnly(showValue) {
  const wert = typeof showValue === "string" ? showValue.trim() : "";
  if (wert !== "on") {
    throw new BaselineError(
      `default_transaction_read_only steht auf "${wert || "(leer)"}" statt "on"; der Lauf bricht ab, bevor eine Zeile gelesen wird.`,
    );
  }
  return wert;
}

/** Tabellennamen aus `FROM`/`JOIN` einer Anweisung, klein geschrieben. */
export function tableNames(sql) {
  const treffer = sql.matchAll(/\b(?:from|join)\s+([a-z_][a-z0-9_]*)/gi);
  return [...new Set([...treffer].map((match) => match[1].toLowerCase()))];
}

export function queriesForProjects(projectIds) {
  const params = [[...projectIds]];
  return [
    {
      name: "candidates",
      params,
      sql: `SELECT p.id AS photo_id, p.project_id, p.etag,
       true AS cloud_motif_assessment,
       true AS album_suitability
FROM photos p
JOIN photo_motif_assessments ma ON ma.photo_id = p.id AND ma.source = 'CLOUD'
JOIN photo_album_suitability pas ON pas.photo_id = p.id
WHERE p.project_id = ANY($1::int[])
ORDER BY p.project_id, p.id`,
    },
    {
      name: "remoteRuns",
      params,
      sql: `SELECT project_id, id, model, started_at, finished_at, photos_processed, api_calls
FROM remote_category_classification_runs
WHERE project_id = ANY($1::int[])
ORDER BY finished_at DESC NULLS LAST, id DESC`,
    },
    {
      name: "criterionRuns",
      params,
      sql: `SELECT project_id, id, landmark_model, started_at, finished_at, photos_processed,
       landmark_api_calls, landmark_photos_total
FROM criterion_scoring_runs
WHERE project_id = ANY($1::int[])
ORDER BY finished_at DESC NULLS LAST, id DESC`,
    },
  ];
}

export function queriesForPhotos(photoIds) {
  const params = [[...photoIds]];
  return [
    {
      name: "motifStrengths",
      params,
      sql: `SELECT ms.photo_id, ms.motif_key, ms.strength
FROM photo_motif_strengths ms
JOIN photo_motif_assessments ma ON ma.photo_id = ms.photo_id AND ma.source = 'CLOUD'
WHERE ms.photo_id = ANY($1::bigint[])
ORDER BY ms.photo_id, ms.motif_key`,
    },
    {
      name: "assessments",
      params,
      sql: `SELECT photo_id, excluded_document, provider
FROM photo_motif_assessments
WHERE photo_id = ANY($1::bigint[]) AND source = 'CLOUD'`,
    },
    {
      name: "albumSuitability",
      params,
      sql: `SELECT photo_id, level, reason, provider
FROM photo_album_suitability
WHERE photo_id = ANY($1::bigint[])`,
    },
    {
      name: "fineLabels",
      params,
      sql: `SELECT pfl.photo_id, pfl.raw_label, fl.canonical_key
FROM photo_fine_labels pfl
JOIN fine_labels fl ON fl.id = pfl.fine_label_id
WHERE pfl.photo_id = ANY($1::bigint[])
ORDER BY pfl.photo_id, fl.canonical_key, pfl.id`,
    },
    {
      name: "landmarks",
      params,
      sql: `SELECT photo_id, name, canonical_name, confidence
FROM photo_landmark_detections
WHERE photo_id = ANY($1::bigint[])`,
    },
  ];
}

function gruppiere(rows, key) {
  const karte = new Map();
  for (const row of rows) {
    const wert = row[key];
    if (!karte.has(wert)) karte.set(wert, []);
    karte.get(wert).push(row);
  }
  return karte;
}

function sekundenZwischen(start, ende) {
  const von = Date.parse(start);
  const bis = Date.parse(ende);
  if (Number.isNaN(von) || Number.isNaN(bis)) return null;
  return Math.round((bis - von) / 1000);
}

function abgeschlosseneLaeufe(rows) {
  return rows
    .filter((row) => row.finishedAt)
    .sort((links, rechts) => {
      const zeit = Date.parse(rechts.finishedAt) - Date.parse(links.finishedAt);
      return zeit !== 0 ? zeit : rechts.id - links.id;
    });
}

function juengsterProProjekt(rows) {
  const karte = new Map();
  for (const row of rows) {
    if (!karte.has(row.projectId)) karte.set(row.projectId, row);
  }
  return karte;
}

function laufzeile(row, art) {
  if (!row) return null;
  return {
    id: row.id,
    model: art === "landmark" ? (row.landmarkModel ?? null) : (row.model ?? null),
    startedAt: row.startedAt ?? null,
    finishedAt: row.finishedAt ?? null,
    durationSeconds: sekundenZwischen(row.startedAt, row.finishedAt),
    photosProcessed: row.photosProcessed ?? null,
    apiCalls: art === "landmark" ? (row.landmarkApiCalls ?? null) : (row.apiCalls ?? null),
  };
}

function modelle(rows, feld) {
  const werte = rows.map((row) => row[feld]).filter((wert) => typeof wert === "string");
  return [...new Set(werte)].sort();
}

export function assembleBaseline({
  photoIds,
  motifStrengths = [],
  assessments = [],
  albumSuitability = [],
  fineLabels = [],
  landmarks = [],
  remoteRuns = [],
  criterionRuns = [],
}) {
  const photoSet = new Set(photoIds);
  let ignoredRows = 0;
  const innerhalb = (row) => {
    const drin = photoSet.has(row.photoId);
    if (!drin) ignoredRows += 1;
    return drin;
  };

  const staerkenProFoto = gruppiere(
    motifStrengths.filter(innerhalb),
    "photoId",
  );
  const motPh = photoIds.map((photoId) => {
    const staerken = {};
    for (const row of staerkenProFoto.get(photoId) ?? []) {
      if (typeof row.strength === "number" && Number.isFinite(row.strength)) {
        staerken[row.motifKey] = row.strength;
      }
    }
    const fehlend = MOTIF_KEYS.filter((key) => !(key in staerken));
    return {
      photoId,
      strengths: staerken,
      complete: fehlend.length === 0,
      missingMotifs: fehlend,
    };
  });

  const ausschluss = assessments.filter(innerhalb);
  const album = albumSuitability.filter(innerhalb);
  const labelsProFoto = gruppiere(fineLabels.filter(innerhalb), "photoId");
  const landmarkProFoto = new Map(landmarks.filter(innerhalb).map((row) => [row.photoId, row]));

  const sehenswuerdig = photoIds.map((photoId) => {
    const row = landmarkProFoto.get(photoId);
    return {
      photoId,
      name: row?.name ?? null,
      canonicalName: row?.canonicalName ?? null,
      confidence: row?.confidence ?? null,
    };
  });

  const abgeschlossen = abgeschlosseneLaeufe(remoteRuns);
  const abgeschlossenKriterium = abgeschlosseneLaeufe(criterionRuns);
  const kategorieProProjekt = juengsterProProjekt(abgeschlossen);
  const landmarkProProjekt = juengsterProProjekt(abgeschlossenKriterium);
  const projektIds = [...new Set([...kategorieProProjekt.keys(), ...landmarkProProjekt.keys()])].sort(
    (links, rechts) => links - rechts,
  );

  const laeufe = projektIds.map((projectId) => ({
    projectId,
    category: laufzeile(kategorieProProjekt.get(projectId), "category"),
    landmark: laufzeile(landmarkProProjekt.get(projectId), "landmark"),
  }));

  return {
    counts: {
      photos: photoIds.length,
      ignoredRows,
      incompleteRuns: remoteRuns.filter((row) => !row.finishedAt).length,
    },
    runs: {
      projects: laeufe,
      models: {
        category: modelle(abgeschlossen, "model"),
        landmark: modelle(abgeschlossenKriterium, "landmarkModel"),
      },
    },
    purposes: {
      motivstaerken: {
        photos: motPh,
        counts: {
          total: photoIds.length,
          complete: motPh.filter((row) => row.complete).length,
          incomplete: motPh.filter((row) => !row.complete).length,
        },
      },
      ausschluss: {
        photos: ausschluss.map((row) => ({
          photoId: row.photoId,
          excludedDocument: row.excludedDocument,
        })),
        counts: {
          total: photoIds.length,
          withBaseline: ausschluss.length,
          withoutBaseline: photoIds.length - ausschluss.length,
        },
      },
      albumtauglichkeit: {
        photos: album.map((row) => ({
          photoId: row.photoId,
          level: row.level,
          reason: row.reason ?? null,
        })),
        counts: {
          total: photoIds.length,
          withBaseline: album.length,
          withoutBaseline: photoIds.length - album.length,
        },
      },
      feinlabels: {
        photos: photoIds
          .filter((photoId) => labelsProFoto.has(photoId))
          .map((photoId) => ({
            photoId,
            labels: labelsProFoto.get(photoId).map((row) => ({
              rawLabel: row.rawLabel,
              canonicalKey: row.canonicalKey,
            })),
          })),
        counts: {
          total: photoIds.length,
          withBaseline: labelsProFoto.size,
          withoutBaseline: photoIds.length - labelsProFoto.size,
        },
      },
      sehenswuerdigkeit: {
        photos: sehenswuerdig,
        counts: {
          total: photoIds.length,
          named: sehenswuerdig.filter((row) => row.name !== null).length,
          unnamed: sehenswuerdig.filter((row) => row.name === null).length,
        },
      },
    },
  };
}
