import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";

import { assertDownloadEnvironment, fetchModel, fileUrl } from "../src/fetch-model.js";
import { sha256File } from "../src/pins.js";

const INHALTE = {
  "eye.tflite": "modell-bytes",
  "eye_meta.json": "meta-bytes",
};

let server;
let base;

before(async () => {
  server = createServer((anfrage, antwort) => {
    const name = anfrage.url.split("/").pop();
    const inhalt = INHALTE[name];
    if (inhalt === undefined) {
      antwort.writeHead(404).end();
      return;
    }
    antwort.writeHead(200, { "content-type": "application/octet-stream" });
    antwort.end(inhalt);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => new Promise((resolve) => server.close(resolve)));

async function pinsFor(names = Object.keys(INHALTE)) {
  const files = {};
  for (const name of names) {
    const directory = await mkdtemp(join(tmpdir(), "eye-hash-"));
    const pfad = join(directory, name);
    await import("node:fs/promises").then(({ writeFile }) => writeFile(pfad, INHALTE[name]));
    files[name] = await sha256File(pfad);
  }
  return {
    revision: "v1.0.0",
    commit: "0".repeat(40),
    files,
    mappingTags: ["sky"],
  };
}

test("die Abrufadresse folgt der gepinnten Revision", () => {
  assert.equal(
    fileUrl({ revision: "v1.0.0", name: "eye.tflite", base }),
    `${base}/desert-ant-labs/eye/resolve/v1.0.0/eye.tflite`,
  );
});

test("fetchModel legt beide Dateien ab und bestätigt die Pins", async () => {
  const directory = await mkdtemp(join(tmpdir(), "eye-model-"));

  const ergebnis = await fetchModel({ directory, pins: await pinsFor(), base });

  assert.deepEqual(ergebnis.checked.sort(), ["eye.tflite", "eye_meta.json"]);
  assert.equal(await readFile(join(directory, "eye.tflite"), "utf8"), INHALTE["eye.tflite"]);
});

test("fetchModel lädt eine bereits stimmige Datei nicht erneut", async () => {
  const directory = await mkdtemp(join(tmpdir(), "eye-model-"));
  const pins = await pinsFor();
  await fetchModel({ directory, pins, base });

  let abrufe = 0;
  await fetchModel({
    directory,
    pins,
    base,
    fetchImpl: (...args) => {
      abrufe += 1;
      return fetch(...args);
    },
  });

  assert.equal(abrufe, 0);
});

test("ein abweichender Hash lässt keine Datei zurück", async () => {
  const directory = await mkdtemp(join(tmpdir(), "eye-model-"));
  const pins = await pinsFor();
  pins.files["eye.tflite"] = "f".repeat(64);

  await assert.rejects(() => fetchModel({ directory, pins, base }));

  const uebrig = await readdir(directory);
  assert.deepEqual(uebrig, []);
});

test("ein Fehlerstatus des Abrufs bricht ab", async () => {
  const directory = await mkdtemp(join(tmpdir(), "eye-model-"));
  const pins = await pinsFor();
  pins.files["gibt-es-nicht"] = "a".repeat(64);

  await assert.rejects(() => fetchModel({ directory, pins, base }));
});

test("fetchModel meldet fehlende Bytes als Fehler statt als Datei", async () => {
  const directory = await mkdtemp(join(tmpdir(), "eye-model-"));
  const pins = await pinsFor();

  await assert.rejects(
    () =>
      fetchModel({
        directory,
        pins,
        base,
        fetchImpl: async () => new Response("", { status: 500 }),
      }),
    /Status 500/,
  );
});

test("ein Token oder Proxy bricht den Download ab", () => {
  assert.doesNotThrow(() => assertDownloadEnvironment({}));
  assert.throws(() => assertDownloadEnvironment({ HF_TOKEN: "hf_x" }));
  assert.throws(() => assertDownloadEnvironment({ HTTPS_PROXY: "http://proxy.test:3128" }));
});
