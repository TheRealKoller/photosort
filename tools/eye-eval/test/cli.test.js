import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { main } from "../src/cli.js";

function mitArbeitsverzeichnis(rumpf) {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-cli-"));
  try {
    writeFileSync(join(verzeichnis, "projects.json"), "[]");
    return rumpf(verzeichnis);
  } finally {
    rmSync(verzeichnis, { recursive: true, force: true });
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
