import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { main } from "../src/cli.js";
import { assembleBaseline } from "../src/baseline.js";
import { PURPOSE_ORDER } from "../src/compare.js";
import { EYE_PURPOSE_MAPPING_HASH } from "../src/mapping.js";
import { MOTIF_KEYS } from "../src/motifs.js";

const TOOL_DIR = fileURLToPath(new URL("..", import.meta.url));

function mitArbeitsverzeichnis(rumpf) {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-cli-"));
  try {
    writeFileSync(join(verzeichnis, "projects.json"), "[]");
    return Promise.resolve(rumpf(verzeichnis)).finally(() =>
      rmSync(verzeichnis, { recursive: true, force: true }),
    );
  } catch (fehler) {
    rmSync(verzeichnis, { recursive: true, force: true });
    throw fehler;
  }
}

function ohneUmgebung(variablen, rumpf) {
  const gemerkt = variablen.map((name) => [name, process.env[name]]);
  for (const name of variablen) delete process.env[name];
  return Promise.resolve(rumpf()).finally(() => {
    for (const [name, wert] of gemerkt) {
      if (wert === undefined) delete process.env[name];
      else process.env[name] = wert;
    }
  });
}

test("prepare ohne Bildcache nennt --photo-cache und die Variable", () =>
  mitArbeitsverzeichnis((verzeichnis) =>
    ohneUmgebung(["EYE_EVAL_PHOTO_CACHE_DIR"], async () => {
      await assert.rejects(() => main(["prepare", "--work-dir", verzeichnis]), (error) => {
        assert.match(error.message, /--photo-cache/);
        assert.match(error.message, /EYE_EVAL_PHOTO_CACHE_DIR/);
        assert.match(error.message, /\/cache/);
        return true;
      });
    }),
  ));

test("prepare ohne Datenbank nennt die Env-Datei statt einer Verbindung", () =>
  mitArbeitsverzeichnis((verzeichnis) =>
    ohneUmgebung(["EYE_EVAL_DATABASE_URL"], async () => {
      await assert.rejects(
        () => main(["prepare", "--work-dir", verzeichnis, "--photo-cache", verzeichnis]),
        /EYE_EVAL_DATABASE_URL/,
      );
    }),
  ));

const FOTOS = [11, 12, 13];
const ANALYSE = {
  model: "eye@v1.0.0",
  kind: "photo",
  confidences: { beach: 0.9 },
  scores: { aesthetic: 0.7, keeper: 0.6, cover: 0.5 },
  faces: [],
  pets: [],
  details: { layout: { shot: { wide: 0.8 } } },
};

function pagesLauf() {
  const sample = {
    seed: 7,
    projects: [
      {
        projectId: 1,
        kind: "familie",
        photos: FOTOS.map((photoId) => ({
          photoId,
          projectId: 1,
          etag: `etag-${photoId}`,
          cacheKey: `key-${photoId}`,
        })),
      },
    ],
  };
  const baseline = assembleBaseline({
    photoIds: FOTOS,
    motifStrengths: FOTOS.flatMap((photoId) =>
      MOTIF_KEYS.map((motifKey) => ({ photoId, motifKey, strength: 0.5 })),
    ),
    assessments: FOTOS.map((photoId) => ({ photoId, excludedDocument: false })),
    albumSuitability: FOTOS.map((photoId) => ({ photoId, level: 3, reason: null })),
    fineLabels: FOTOS.map((photoId) => ({ photoId, rawLabel: "Strand", canonicalKey: "strand" })),
    criterionScores: FOTOS.map((photoId) => ({
      photoId,
      criterionKey: "landschaft",
      value: 1,
    })),
  });
  const purposes = Object.fromEntries(
    PURPOSE_ORDER.map((purpose) => [purpose, { index: 0, choices: {} }]),
  );
  purposes.ausschluss.index = 1;
  return {
    run: { version: 1, seed: 7, mappingHash: EYE_PURPOSE_MAPPING_HASH, sample, baseline },
    decisions: { version: 1, seed: 7, purposes },
  };
}

test("pages beginnt je Zweck am gespeicherten Zeiger aus decisions.json", () =>
  mitArbeitsverzeichnis(async (verzeichnis) => {
    const { run, decisions } = pagesLauf();
    writeFileSync(join(verzeichnis, "run.json"), JSON.stringify(run));
    writeFileSync(join(verzeichnis, "decisions.json"), JSON.stringify(decisions));
    mkdirSync(join(verzeichnis, "analysis"));
    for (const photoId of [11, 13]) {
      writeFileSync(join(verzeichnis, "analysis", `${photoId}.json`), JSON.stringify(ANALYSE));
    }

    assert.equal(await main(["pages", "--work-dir", verzeichnis]), 0);
    const html = readFileSync(join(verzeichnis, "page-ausschluss.html"), "utf8");
    assert.match(html, /data-start="1"/);
    assert.match(html, /"startIndex":1/);
  }));

test("serve liefert den gespeicherten Stand über GET /state", { timeout: 20000 }, () =>
  mitArbeitsverzeichnis(async (verzeichnis) => {
    const { run, decisions } = pagesLauf();
    decisions.purposes.ausschluss.index = 1;
    decisions.purposes.ausschluss.choices = { 11: "a" };
    writeFileSync(join(verzeichnis, "run.json"), JSON.stringify(run));
    writeFileSync(join(verzeichnis, "decisions.json"), JSON.stringify(decisions));
    mkdirSync(join(verzeichnis, "analysis"));
    for (const photoId of [11, 13]) {
      writeFileSync(join(verzeichnis, "analysis", `${photoId}.json`), JSON.stringify(ANALYSE));
    }

    const kind = spawn(
      process.execPath,
      ["src/cli.js", "serve", "--work-dir", verzeichnis, "--port", "0"],
      { cwd: TOOL_DIR, stdio: ["ignore", "pipe", "pipe"] },
    );
    let ausgabe = "";
    let fehler = "";
    kind.stderr.on("data", (stueck) => {
      fehler += stueck;
    });
    try {
      const port = await new Promise((fertig, scheitern) => {
        kind.stdout.on("data", (stueck) => {
          ausgabe += stueck;
          const treffer = ausgabe.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
          if (treffer) fertig(treffer[1]);
        });
        kind.once("exit", (code) =>
          scheitern(new Error(`serve endete mit ${code}: ${ausgabe}${fehler}`)),
        );
      });

      const antwort = await fetch(`http://127.0.0.1:${port}/state`);
      assert.equal(antwort.status, 200);
      assert.match(antwort.headers.get("content-type"), /application\/json/);
      const stand = await antwort.json();
      assert.equal(stand.purposes.ausschluss.index, 1);
      assert.deepEqual(stand.purposes.ausschluss.choices, { 11: "a" });
    } finally {
      kind.kill("SIGTERM");
      await new Promise((fertig) => kind.once("exit", fertig));
    }
  }));
