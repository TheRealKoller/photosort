import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";

import { prepare, prepareZiel } from "../src/cli.js";
import { displayPath } from "../src/cache.js";

const PROJEKTE = [
  { projectId: 3, kind: "familie" },
  { projectId: 5, kind: "reise" },
];

function kandidaten() {
  return PROJEKTE.flatMap(({ projectId }) =>
    Array.from({ length: 100 }, (_, index) => ({
      photoId: projectId * 1000 + index,
      projectId,
      etag: `etag-${projectId}-${index}`,
      cloudMotifAssessment: true,
      albumSuitability: true,
    })),
  );
}

function fakeDeps(zustand) {
  const rowSets = {
    candidates: kandidaten(),
    remoteRuns: [
      {
        projectId: 3,
        id: 1,
        model: "cloud-a",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:10:00Z",
        photosProcessed: 100,
        apiCalls: 120,
      },
    ],
    criterionRuns: [
      {
        projectId: 5,
        id: 2,
        landmarkModel: "cloud-b",
        startedAt: "2026-01-02T00:00:00Z",
        finishedAt: "2026-01-02T00:05:00Z",
        photosProcessed: 100,
        landmarkApiCalls: 9,
        landmarkPhotosTotal: 100,
      },
    ],
    motifStrengths: [],
    assessments: [],
    albumSuitability: [],
    fineLabels: [],
    landmarks: [],
  };
  return {
    connect: async () => {
      zustand.verbunden = true;
      return { end: async () => {} };
    },
    query: async (_client, abfrage) => rowSets[abfrage.name],
    copy: async (von, nach) => {
      mkdirSync(dirname(nach), { recursive: true });
      writeFileSync(nach, readFileSync(von));
    },
  };
}

function mitLauf(rumpf) {
  const basis = mkdtempSync(join(tmpdir(), "eye-eval-prepare-"));
  const workDir = join(basis, "work");
  const cacheDir = join(basis, "cache");
  mkdirSync(workDir);
  mkdirSync(cacheDir);
  writeFileSync(join(workDir, "projects.json"), JSON.stringify(PROJEKTE));
  for (const foto of kandidaten()) {
    writeFileSync(displayPath(cacheDir, foto.photoId, foto.etag), `bild-${foto.photoId}`);
  }
  return Promise.resolve(
    rumpf({ workDir, cacheDir, basis }).finally(() => rmSync(basis, { recursive: true, force: true })),
  );
}

test("prepare schreibt aus der Stichprobe eine vollständige run.json", () =>
  mitLauf(async ({ workDir, cacheDir }) => {
    const zustand = { verbunden: false };
    const deps = fakeDeps(zustand);
    await prepare(
      { seed: 7, perProject: 100, photoCache: cacheDir, databaseUrl: "postgres://test" },
      workDir,
      deps,
    );

    assert.equal(zustand.verbunden, true);
    const run = JSON.parse(readFileSync(join(workDir, "run.json"), "utf8"));
    assert.equal(run.sample.projects.length, 2);
    assert.equal(run.sample.counts.photos, 200);
    const foto = run.sample.projects[0].photos[0];
    assert.equal(typeof foto.cacheKey, "string");
    assert.equal(foto.cacheKey.length, 64);
    for (const projekt of run.sample.projects) {
      assert.equal(projekt.photos.length, 100);
      for (const bild of projekt.photos) {
        assert.equal(existsSync(join(workDir, "images", `${bild.photoId}.jpg`)), true);
      }
    }
    assert.deepEqual(Object.keys(run.baseline.purposes).sort(), [
      "albumtauglichkeit",
      "ausschluss",
      "feinlabels",
      "motivstaerken",
      "sehenswuerdigkeit",
    ]);
    assert.equal(run.baseline.runs.projects.length, 2);
    const projekt3 = run.baseline.runs.projects.find((eintrag) => eintrag.projectId === 3);
    assert.equal(projekt3.category.apiCalls, 120);
  }));

test("ein zweites prepare bricht ab und nennt --force", () =>
  mitLauf(async ({ workDir, cacheDir }) => {
    writeFileSync(join(workDir, "run.json"), "{}");
    const zustand = { verbunden: false };
    await assert.rejects(
      () => prepare({ seed: 7, perProject: 100, photoCache: cacheDir, databaseUrl: "postgres://test" }, workDir, fakeDeps(zustand)),
      (error) => {
        assert.match(error.message, /run\.json/);
        assert.match(error.message, /--force/);
        assert.equal(zustand.verbunden, false, "kein Datenbankzugriff vor dem Abbruch");
        return true;
      },
    );
  }));

test("--force wählt ein neues Arbeitsverzeichnis statt Dateien zu mischen", () => {
  assert.equal(prepareZiel("/work", { force: false }), "/work");
  const frisch = prepareZiel("/work", { force: true, zeit: "2026-11-02T10:00:00.000Z" });
  assert.notEqual(frisch, "/work");
  assert.match(frisch, /^\/work-lauf-2026-11-02T10-00-00/);
});
