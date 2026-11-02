import assert from "node:assert/strict";
import { test } from "node:test";

import { SampleError, eligibleCandidates, selectSample } from "../src/sample.js";

/** Ein Kandidat, wie ihn die Basis-Abfrage liefert. */
function candidate(photoId, projectId, extra = {}) {
  return {
    photoId,
    projectId,
    etag: `etag-${photoId}`,
    cloudMotifAssessment: true,
    albumSuitability: true,
    ...extra,
  };
}

/** `count` Kandidaten eines Projekts, fortlaufend nummeriert. */
function candidates(count, projectId, offset = 0) {
  return Array.from({ length: count }, (_, index) =>
    candidate(offset + index + 1, projectId),
  );
}

function cachePresent(photoId) {
  return () => true;
}

test("genau 100 Fotos je Projekt sind zulässig", () => {
  const sample = selectSample({
    projects: [
      { id: 1, kind: "reise" },
      { id: 2, kind: "familie" },
    ],
    candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
    cacheExists: cachePresent(),
  });

  assert.equal(sample.projects.length, 2);
  for (const project of sample.projects) {
    assert.equal(project.selected.length, 100);
  }
});

test("99 zulässige Fotos brechen ab statt still zu verkleinern", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [
          { id: 1, kind: "reise" },
          { id: 2, kind: "familie" },
        ],
        candidates: [...candidates(99, 1), ...candidates(100, 2, 500)],
        cacheExists: cachePresent(),
      }),
    (error) => {
      assert.ok(error instanceof SampleError);
      assert.match(error.message, /Projekt 1/);
      assert.match(error.message, /99/);
      assert.match(error.message, /100/);
      return true;
    },
  );
});

test("fehlende Cloud-Basis oder Albumtauglichkeit fällt aus der Stichprobe", () => {
  const rows = [
    candidate(1, 1),
    candidate(2, 1, { cloudMotifAssessment: false }),
    candidate(3, 1, { albumSuitability: false }),
    candidate(4, 1, { cloudMotifAssessment: false, albumSuitability: false }),
    candidate(5, 2),
  ];

  assert.deepEqual(
    eligibleCandidates(rows).map((row) => row.photoId),
    [1, 5],
  );
});

test("ein fehlender oder abweichender Cache-Stand zählt als Ausfall", () => {
  const sample = selectSample({
    projects: [
      { id: 1, kind: "reise" },
      { id: 2, kind: "familie" },
    ],
    candidates: [...candidates(103, 1), ...candidates(100, 2, 500)],
    // Drei Fotos des ersten Projekts haben keine Cache-Datei zum etag.
    cacheExists: (photoId) => photoId > 3,
  });

  const first = sample.projects.find((project) => project.projectId === 1);
  assert.equal(first.counts.inconsistent, 3);
  assert.equal(first.counts.eligible, 103);
  assert.equal(first.selected.length, 100);
  assert.equal(sample.counts.inconsistent, 3);
});

test("fällt ein Projekt durch Ausfälle unter 100, bricht der Lauf ab", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [
          { id: 1, kind: "reise" },
          { id: 2, kind: "familie" },
        ],
        candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
        cacheExists: (photoId) => photoId > 1,
      }),
    /Projekt 1.*99/s,
  );
});

test("zwei Projekte mit gleicher Art brechen ab", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [
          { id: 1, kind: "reise" },
          { id: 2, kind: "Reise" },
        ],
        candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
        cacheExists: cachePresent(),
      }),
    /Art/,
  );
});

test("eine leere Art-Angabe bricht ab", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [
          { id: 1, kind: "" },
          { id: 2, kind: "familie" },
        ],
        candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
        cacheExists: cachePresent(),
      }),
    /Art/,
  );
});

test("weniger als zwei Projekte brechen ab", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [{ id: 1, kind: "reise" }],
        candidates: candidates(100, 1),
        cacheExists: cachePresent(),
      }),
    /mindestens zwei/,
  );
});

test("dieselbe Saat liefert dieselbe Auswahl, eine andere eine andere", () => {
  const input = {
    projects: [
      { id: 1, kind: "reise" },
      { id: 2, kind: "familie" },
    ],
    candidates: [...candidates(140, 1), ...candidates(140, 2, 500)],
    cacheExists: cachePresent(),
  };

  const first = selectSample({ ...input, seed: 7 });
  const again = selectSample({ ...input, seed: 7 });
  const other = selectSample({ ...input, seed: 8 });

  assert.deepEqual(
    first.projects.map((project) => project.selected),
    again.projects.map((project) => project.selected),
  );
  assert.notDeepEqual(
    first.projects.map((project) => project.selected),
    other.projects.map((project) => project.selected),
  );
  assert.equal(first.seed, 7);
});

test("die Auswahl ist aufsteigend sortiert und ohne Doppelung", () => {
  const sample = selectSample({
    projects: [
      { id: 1, kind: "reise" },
      { id: 2, kind: "familie" },
    ],
    candidates: [...candidates(130, 1), ...candidates(130, 2, 500)],
    cacheExists: cachePresent(),
  });

  for (const project of sample.projects) {
    const selected = [...project.selected];
    assert.deepEqual(selected, [...selected].sort((a, b) => a - b));
    assert.equal(new Set(selected).size, selected.length);
  }
});

test("jedes ausgewählte Foto trägt einen Cache-Schlüssel aus photo_id und etag", () => {
  const sample = selectSample({
    projects: [
      { id: 1, kind: "reise" },
      { id: 2, kind: "familie" },
    ],
    candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
    cacheExists: cachePresent(),
  });

  const first = sample.projects[0];
  assert.equal(first.photos.length, first.selected.length);
  for (const photo of first.photos) {
    assert.equal(typeof photo.cacheKey, "string");
    assert.match(photo.cacheKey, /^[0-9a-f]{64}$/);
  }
  assert.equal(first.photos[0].photoId, first.selected[0]);
});

test("Photos ohne Cache-Prüfung werden nie stillschweigend aufgenommen", () => {
  assert.throws(
    () =>
      selectSample({
        projects: [
          { id: 1, kind: "reise" },
          { id: 2, kind: "familie" },
        ],
        candidates: [...candidates(100, 1), ...candidates(100, 2, 500)],
      }),
    /cacheExists/,
  );
});
