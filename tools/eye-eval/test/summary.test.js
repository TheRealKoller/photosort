import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { main } from "../src/cli.js";
import { EYE_PURPOSE_MAPPING_HASH } from "../src/mapping.js";
import { PURPOSE_ORDER } from "../src/compare.js";

function runJson() {
  return {
    version: 1,
    seed: 7,
    mappingHash: EYE_PURPOSE_MAPPING_HASH,
    sample: {
      projects: [
        {
          projectId: 1,
          kind: "familie",
          photos: [{ photoId: 11, projectId: 1, etag: "e", cacheKey: "k" }],
        },
      ],
    },
    baseline: {
      purposes: Object.fromEntries(PURPOSE_ORDER.map((purpose) => [purpose, { photos: [] }])),
      runs: { projects: [], models: { category: [], landmark: [] } },
    },
  };
}

function entscheidungen() {
  const purposes = Object.fromEntries(
    PURPOSE_ORDER.map((purpose) => [purpose, { index: 0, choices: {} }]),
  );
  purposes.ausschluss.choices = { 11: "a" };
  return { version: 1, seed: 7, purposes };
}

function mitArbeitsverzeichnis(rumpf) {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-summary-"));
  try {
    writeFileSync(join(verzeichnis, "run.json"), JSON.stringify(runJson()));
    writeFileSync(join(verzeichnis, "decisions.json"), JSON.stringify(entscheidungen()));
    return Promise.resolve(rumpf(verzeichnis)).finally(() =>
      rmSync(verzeichnis, { recursive: true, force: true }),
    );
  } catch (fehler) {
    rmSync(verzeichnis, { recursive: true, force: true });
    throw fehler;
  }
}

test("summary ohne ab-map.json bricht ab statt die Stimmen zu raten", () =>
  mitArbeitsverzeichnis(async (verzeichnis) => {
    await assert.rejects(() => main(["summary", "--work-dir", verzeichnis]), /ab-map\.json/);
  }));

test("summary rechnet A über die Seitenzuordnung in Eye-Urteile um", () =>
  mitArbeitsverzeichnis(async (verzeichnis) => {
    writeFileSync(
      join(verzeichnis, "ab-map.json"),
      JSON.stringify({ purposes: { ausschluss: [{ photoId: 11, left: "second" }] } }),
    );
    assert.equal(await main(["summary", "--work-dir", verzeichnis]), 0);
    let summary = JSON.parse(readFileSync(join(verzeichnis, "summary.json"), "utf8"));
    assert.equal(summary.purposes.ausschluss.better, 1);
    assert.equal(summary.purposes.ausschluss.worse, 0);

    writeFileSync(
      join(verzeichnis, "ab-map.json"),
      JSON.stringify({ purposes: { ausschluss: [{ photoId: 11, left: "first" }] } }),
    );
    assert.equal(await main(["summary", "--work-dir", verzeichnis]), 0);
    summary = JSON.parse(readFileSync(join(verzeichnis, "summary.json"), "utf8"));
    assert.equal(summary.purposes.ausschluss.better, 0);
    assert.equal(summary.purposes.ausschluss.worse, 1);
  }));
