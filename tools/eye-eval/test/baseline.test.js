import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BASELINE_TABLES,
  BaselineError,
  assembleBaseline,
  assertReadOnly,
  queriesForPhotos,
  queriesForProjects,
  readOnlyQueryOptions,
  tableNames,
} from "../src/baseline.js";
import { MOTIF_KEYS } from "../src/motifs.js";

const FOTO_IDS = [11, 12, 13];

function basis({ motifs = {}, exclusion = {}, album = {}, fineLabels = [], landmarks = [] } = {}) {
  return assembleBaseline({
    photoIds: FOTO_IDS,
    motifStrengths: Object.entries(motifs).flatMap(([photoId, strengths]) =>
      Object.entries(strengths).map(([motifKey, strength]) => ({
        photoId: Number(photoId),
        motifKey,
        strength,
      })),
    ),
    assessments: Object.entries(exclusion).map(([photoId, excludedDocument]) => ({
      photoId: Number(photoId),
      excludedDocument,
      provider: "anthropic",
    })),
    albumSuitability: Object.entries(album).map(([photoId, level]) => ({
      photoId: Number(photoId),
      level,
      reason: level <= 2 ? "geschlossene Augen" : null,
      provider: "anthropic",
    })),
    fineLabels,
    landmarks,
  });
}

function alleAcht() {
  return Object.fromEntries(MOTIF_KEYS.map((key) => [key, 0.5]));
}

test("die Read-only-Verbindung wird geprüft, nicht angenommen", () => {
  assert.equal(readOnlyQueryOptions(), "-c default_transaction_read_only=on");
  assert.equal(assertReadOnly("on"), "on");
  assert.equal(assertReadOnly(" on\n"), "on");
  assert.throws(() => assertReadOnly("off"), BaselineError);
  assert.throws(() => assertReadOnly(undefined), /default_transaction_read_only/);
});

test("die Abfragen lesen nur die in S14 genannten Tabellen", () => {
  const alle = [
    ...queriesForProjects([1, 2]),
    ...queriesForPhotos(FOTO_IDS),
  ].map((query) => query.sql);

  const gelesen = new Set(alle.flatMap((sql) => tableNames(sql)));
  for (const tabelle of gelesen) {
    assert.ok(
      BASELINE_TABLES.includes(tabelle),
      `Tabelle ${tabelle} steht nicht in der erlaubten Liste (S14)`,
    );
  }
  assert.ok(gelesen.has("photos"));
  assert.ok(gelesen.has("photo_landmark_detections"));
  assert.ok(gelesen.has("criterion_scoring_runs"));
});

test("keine Abfrage schreibt, sperrt oder exportiert (S13)", () => {
  const alle = [...queriesForProjects([1]), ...queriesForPhotos(FOTO_IDS)];
  for (const { sql } of alle) {
    const klein = sql.toLowerCase();
    for (const verboten of [
      "insert ",
      "update ",
      "delete ",
      "alter ",
      "create ",
      "drop ",
      "truncate ",
      "copy ",
      "pg_dump",
      "for update",
    ]) {
      assert.equal(klein.includes(verboten), false, `${verboten.trim()} in: ${sql}`);
    }
    assert.equal(sql.trim().startsWith("SELECT"), true, sql);
    assert.equal(sql.includes(";"), false, sql);
  }
});

test("die Kandidatenabfrage trägt das zusammengesetzte Cloud-Kriterium", () => {
  const [kandidaten] = queriesForProjects([7]);
  assert.match(kandidaten.sql, /photo_motif_assessments/);
  assert.match(kandidaten.sql, /source = 'cloud'/);
  assert.match(kandidaten.sql, /photo_album_suitability/);
  assert.deepEqual(kandidaten.params, [[7]]);
});

test("Motivstärken werden je Foto über alle acht Motive gesammelt", () => {
  const ergebnis = basis({ motifs: { 11: alleAcht(), 12: { menschen: 0.9 } } });
  const zweck = ergebnis.purposes.motivstaerken;

  assert.equal(zweck.counts.total, 3);
  assert.equal(zweck.counts.complete, 1);
  assert.equal(zweck.counts.incomplete, 2);
  const foto = zweck.photos.find((row) => row.photoId === 11);
  assert.deepEqual(Object.keys(foto.strengths).sort(), [...MOTIF_KEYS].sort());
  assert.equal(foto.complete, true);
});

test("fehlende Stärkezeilen eines Motivs machen den Vektor unvollständig statt still null", () => {
  const ergebnis = basis({ motifs: { 13: { ...alleAcht(), tiere: undefined } } });
  const foto = ergebnis.purposes.motivstaerken.photos.find((row) => row.photoId === 13);
  assert.equal(foto.complete, false);
});

test("Ausschluss ist je Foto ein Wahrheitswert aus excluded_document", () => {
  const ergebnis = basis({ exclusion: { 11: true, 12: false } });
  const zweck = ergebnis.purposes.ausschluss;

  assert.equal(zweck.counts.withBaseline, 2);
  assert.equal(zweck.counts.withoutBaseline, 1);
  assert.deepEqual(zweck.photos, [
    { photoId: 11, excludedDocument: true },
    { photoId: 12, excludedDocument: false },
  ]);
});

test("Albumtauglichkeit trägt Stufe und Begründung", () => {
  const ergebnis = basis({ album: { 11: 1, 12: 5 } });
  const zweck = ergebnis.purposes.albumtauglichkeit;

  assert.deepEqual(zweck.photos[0], {
    photoId: 11,
    level: 1,
    reason: "geschlossene Augen",
  });
  assert.equal(zweck.photos[1].level, 5);
  assert.equal(zweck.counts.withBaseline, 2);
  assert.equal(zweck.counts.withoutBaseline, 1);
});

test("eine fehlende Feinlabel-Zeile heißt keine Basis für diesen Zweck, kein Abbruch", () => {
  const ergebnis = basis({
    fineLabels: [
      { photoId: 11, rawLabel: "Hund", canonicalKey: "hund" },
      { photoId: 11, rawLabel: "Hunde", canonicalKey: "hund" },
      { photoId: 12, rawLabel: "Strand", canonicalKey: "strand" },
    ],
  });
  const zweck = ergebnis.purposes.feinlabels;

  assert.equal(zweck.counts.total, 3);
  assert.equal(zweck.counts.withBaseline, 2);
  assert.equal(zweck.counts.withoutBaseline, 1);
  assert.equal(zweck.photos[0].labels.length, 2);
});

test("eine fehlende Landmark-Zeile heißt „kein Name“ statt eines Platzhalters", () => {
  const ergebnis = basis({
    landmarks: [
      {
        photoId: 11,
        name: "Eiffelturm",
        canonicalName: "eiffelturm",
        confidence: 0.93,
      },
    ],
  });
  const zweck = ergebnis.purposes.sehenswuerdigkeit;

  assert.equal(zweck.counts.total, 3);
  assert.equal(zweck.counts.named, 1);
  assert.equal(zweck.counts.unnamed, 2);
  assert.deepEqual(zweck.photos[1], {
    photoId: 12,
    name: null,
    canonicalName: null,
    confidence: null,
  });
});

test("Fotos außerhalb der Stichprobe gelangen nicht in die Basis", () => {
  const ergebnis = basis({
    exclusion: { 99: true },
    landmarks: [
      { photoId: 99, name: "Fremd", canonicalName: "fremd", confidence: 0.9 },
    ],
  });

  assert.deepEqual(
    ergebnis.purposes.ausschluss.photos.map((row) => row.photoId),
    [],
  );
  assert.equal(ergebnis.purposes.sehenswuerdigkeit.counts.named, 0);
  assert.equal(ergebnis.counts.ignoredRows, 2);
});

test("Anbieter, Modell, Laufzeit und Aufrufe kommen aus den Laufzeilen", () => {
  const ergebnis = assembleBaseline({
    photoIds: FOTO_IDS,
    remoteRuns: [
      {
        projectId: 1,
        id: 9,
        model: "claude-sonnet-4",
        provider: "anthropic",
        startedAt: "2026-10-01T10:00:00Z",
        finishedAt: "2026-10-01T10:07:30Z",
        photosProcessed: 120,
        apiCalls: 120,
      },
    ],
    criterionRuns: [
      {
        projectId: 1,
        id: 8,
        landmarkModel: "claude-haiku-4",
        startedAt: "2026-10-01T10:07:30Z",
        finishedAt: "2026-10-01T10:12:30Z",
        photosProcessed: 120,
        landmarkApiCalls: 40,
      },
    ],
  });

  const lauf = ergebnis.runs.projects[0];
  assert.equal(lauf.category.model, "claude-sonnet-4");
  assert.equal(lauf.category.apiCalls, 120);
  assert.equal(lauf.category.durationSeconds, 450);
  assert.equal(lauf.landmark.model, "claude-haiku-4");
  assert.equal(lauf.landmark.apiCalls, 40);
  assert.equal(lauf.landmark.durationSeconds, 300);
  assert.deepEqual(ergebnis.runs.models, {
    category: ["claude-sonnet-4"],
    landmark: ["claude-haiku-4"],
  });
});

test("eine Laufzeile ohne Abschluss zählt nicht als Laufzeitmaßstab", () => {
  const ergebnis = assembleBaseline({
    photoIds: FOTO_IDS,
    remoteRuns: [
      {
        projectId: 1,
        id: 9,
        model: "m",
        startedAt: "2026-10-01T10:00:00Z",
        finishedAt: null,
        apiCalls: 3,
      },
    ],
    criterionRuns: [],
  });

  assert.deepEqual(ergebnis.runs.projects, []);
  assert.equal(ergebnis.counts.incompleteRuns, 1);
});
