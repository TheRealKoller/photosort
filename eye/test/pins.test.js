import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  PINS_PATH,
  PinError,
  loadPins,
  parsePins,
  sha256File,
  verifyPins,
} from "../src/pins.js";

const HASH = "a".repeat(64);
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

function pins(overrides = {}) {
  return {
    revision: "v1.0.0",
    commit: COMMIT,
    files: { "eye.tflite": HASH, "eye_meta.json": HASH },
    mappingTags: ["sky"],
    ...overrides,
  };
}

async function modelDirectory(files) {
  const directory = await mkdtemp(join(tmpdir(), "eye-pins-"));
  for (const [name, inhalt] of Object.entries(files)) {
    await writeFile(join(directory, name), inhalt);
  }
  return directory;
}

test("die eingecheckte Pin-Datei ist vollständig und nennt Revision, Commit und Zuordnungs-Tags", async () => {
  const geladen = await loadPins();

  assert.equal(geladen.revision, "v1.0.0");
  assert.match(geladen.commit, /^[0-9a-f]{40}$/);
  assert.deepEqual(Object.keys(geladen.files).sort(), ["eye.tflite", "eye_meta.json"]);
  assert.ok(geladen.mappingTags.length > 0);
  assert.equal(PINS_PATH.endsWith("pins.json"), true);
});

test("eine fehlende Revision bricht ab", () => {
  assert.throws(() => parsePins(pins({ revision: "  " })), PinError);
});

test("ein Commit, der kein 40-stelliger SHA ist, bricht ab", () => {
  assert.throws(() => parsePins(pins({ commit: "abc" })), PinError);
  assert.throws(() => parsePins(pins({ commit: "Z".repeat(40) })), PinError);
});

test("ein fehlender Hash für eine Pflichtdatei bricht ab", () => {
  assert.throws(
    () => parsePins(pins({ files: { "eye.tflite": HASH, "eye_meta.json": "kurz" } })),
    PinError,
  );
});

test("eine Pin-Datei ohne Zuordnungs-Tags bricht ab", () => {
  assert.throws(() => parsePins(pins({ mappingTags: [] })), PinError);
  assert.throws(() => parsePins(pins({ mappingTags: ["sky", ""] })), PinError);
});

test("verifyPins bestätigt stimmige Dateien und meldet die geprüften Namen", async () => {
  const directory = await modelDirectory({ "eye.tflite": "modell", "eye_meta.json": "meta" });
  const gepinnt = pins({
    files: {
      "eye.tflite": await sha256File(join(directory, "eye.tflite")),
      "eye_meta.json": await sha256File(join(directory, "eye_meta.json")),
    },
  });

  const ergebnis = await verifyPins({ directory, pins: gepinnt });

  assert.deepEqual(ergebnis.checked.sort(), ["eye.tflite", "eye_meta.json"]);
  assert.equal(ergebnis.revision, "v1.0.0");
});

test("eine fehlende Gewichtsdatei bricht vor dem Modell ab", async () => {
  const directory = await modelDirectory({ "eye_meta.json": "meta" });

  await assert.rejects(() => verifyPins({ directory, pins: pins() }), PinError);
});

test("ein abweichender Hash bricht ab", async () => {
  const directory = await modelDirectory({ "eye.tflite": "modell", "eye_meta.json": "meta" });

  await assert.rejects(() => verifyPins({ directory, pins: pins() }), PinError);
});

test("loadPins meldet eine unlesbare Datei als PinError", async () => {
  const directory = await modelDirectory({ "pins.json": "{kaputt" });

  await assert.rejects(() => loadPins(join(directory, "pins.json")), PinError);
});

test("sha256File rechnet über den ganzen Dateiinhalt", async () => {
  const directory = await modelDirectory({ "a.bin": "abc" });

  assert.equal(
    await sha256File(join(directory, "a.bin")),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
});
