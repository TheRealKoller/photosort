import assert from "node:assert/strict";
import { test } from "node:test";

import { RunFileError, parseRun } from "../src/runfile.js";

function lauf(extra = {}) {
  return {
    version: 1,
    seed: 7,
    mappingHash: "sha256:abc",
    sample: {
      projects: [
        {
          projectId: 1,
          kind: "familie",
          photos: [{ photoId: 11, projectId: 1, etag: "e", cacheKey: "k" }],
        },
      ],
    },
    baseline: { purposes: {}, runs: { projects: [], models: { category: [], landmark: [] } } },
    ...extra,
  };
}

const PFAD = "/tmp/eye-smoke/run.json";

test("eine vollständige run.json wird gelesen", () => {
  const gelesen = parseRun(JSON.stringify(lauf()), PFAD);
  assert.equal(gelesen.seed, 7);
  assert.equal(gelesen.sample.projects[0].photos[0].photoId, 11);
});

test("kein JSON bricht mit Meldung und dem Weg zurück ab", () => {
  assert.throws(() => parseRun("{", PFAD), (error) => {
    assert.ok(error instanceof RunFileError);
    assert.match(error.message, /beschädigt/);
    assert.match(error.message, /run\.json/);
    assert.match(error.message, /prepare/);
    return true;
  });
});

test("ein fehlendes baseline.runs bricht mit Meldung ab", () => {
  const ohne = lauf();
  delete ohne.baseline.runs;
  assert.throws(() => parseRun(JSON.stringify(ohne), PFAD), /baseline\.runs/);
});

test("ein fehlendes baseline.purposes bricht mit Meldung ab", () => {
  const ohne = lauf();
  delete ohne.baseline.purposes;
  assert.throws(() => parseRun(JSON.stringify(ohne), PFAD), /baseline\.purposes/);
});

test("ein fehlendes sample.projects bricht mit Meldung ab", () => {
  const ohne = lauf({ sample: {} });
  assert.throws(() => parseRun(JSON.stringify(ohne), PFAD), /sample\.projects/);
});

test("ein Foto ohne photoId bricht mit Meldung ab", () => {
  const kaputt = lauf();
  kaputt.sample.projects[0].photos = [{ projectId: 1, etag: "e", cacheKey: "k" }];
  assert.throws(() => parseRun(JSON.stringify(kaputt), PFAD), /photoId/);
});

test("eine Saat oder Zuordnung ohne Wert bricht ab", () => {
  assert.throws(() => parseRun(JSON.stringify(lauf({ seed: undefined })), PFAD), /seed/);
  assert.throws(() => parseRun(JSON.stringify(lauf({ mappingHash: undefined })), PFAD), /mappingHash/);
});
