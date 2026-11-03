import assert from "node:assert/strict";
import { request } from "node:http";
import { after, before, test } from "node:test";

import { MAX_BODY_BYTES, createApp } from "../src/server.js";

let server;
let base;

async function start(state, analyze = async () => ({ kind: "landscape" })) {
  server = createApp({ state, analyze });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
}

async function stop() {
  if (server) await new Promise((resolve) => server.close(resolve));
  server = undefined;
}

before(async () => {
  await start({ ready: false, revision: null });
});

after(stop);

const jpeg = () => ({
  method: "POST",
  headers: { "content-type": "image/jpeg" },
  body: Buffer.from([0xff, 0xd8, 0xff]),
});

test("GET /health antwortet vor der Bereitschaft 503 ohne Version", async () => {
  const antwort = await fetch(`${base}/health`);

  assert.equal(antwort.status, 503);
  const koerper = await antwort.json();
  assert.equal(koerper.status, "starting");
  assert.equal("model_revision" in koerper, false);
});

test("GET /health antwortet nach der Bereitschaft 200 mit der Modellrevision", async () => {
  await stop();
  await start({ ready: true, revision: "v1.0.0" });

  const antwort = await fetch(`${base}/health`);

  assert.equal(antwort.status, 200);
  assert.deepEqual(await antwort.json(), { status: "ok", model_revision: "v1.0.0" });
});

test("POST /analyze gibt die Analyse als JSON zurück und ruft sie genau einmal", async () => {
  const aufrufe = [];
  await stop();
  await start({ ready: true, revision: "v1.0.0" }, async (bytes) => {
    aufrufe.push(bytes);
    return { kind: "landscape", confidences: { sky: 0.9 } };
  });

  const antwort = await fetch(`${base}/analyze`, jpeg());
  const koerper = await antwort.json();

  assert.equal(antwort.status, 200);
  assert.deepEqual(koerper, { kind: "landscape", confidences: { sky: 0.9 } });
  assert.equal(aufrufe.length, 1);
});

test("ein anderer Content-Type wird mit 415 abgewiesen, bevor das Modell läuft", async () => {
  const aufrufe = [];
  await stop();
  await start({ ready: true, revision: "v1.0.0" }, async () => aufrufe.push(1));

  for (const content_type of ["image/png", "multipart/form-data", "application/json"]) {
    const antwort = await fetch(`${base}/analyze`, {
      method: "POST",
      headers: { "content-type": content_type },
      body: "x",
    });
    assert.equal(antwort.status, 415);
    assert.equal((await antwort.json()).error, "Nur JPEG wird angenommen.");
  }
  const ohne = await fetch(`${base}/analyze`, { method: "POST", body: "x" });
  assert.equal(ohne.status, 415);
  assert.equal(aufrufe.length, 0);
});

test("ein angekündigter Körper über 8 MiB wird mit 413 abgewiesen", async () => {
  const aufrufe = [];
  await stop();
  await start({ ready: true, revision: "v1.0.0" }, async () => aufrufe.push(1));

  // `fetch` verbietet einen Körper, der nicht zur angekündigten Länge passt - deshalb die rohe
  // Anfrage: geprüft wird die Ankündigung, nicht der tatsächliche Strom.
  const port = server.address().port;
  const status = await new Promise((resolve, reject) => {
    const anfrage = request(
      {
        host: "127.0.0.1",
        port,
        path: "/analyze",
        method: "POST",
        headers: {
          "content-type": "image/jpeg",
          "content-length": String(MAX_BODY_BYTES + 1),
        },
      },
      (antwort) => {
        antwort.resume();
        resolve(antwort.statusCode);
      },
    );
    anfrage.on("error", reject);
    anfrage.write("x");
    anfrage.end();
  });

  assert.equal(status, 413);
  assert.equal(aufrufe.length, 0);
});

test("ein tatsächlich zu großer Körper wird mit 413 abgewiesen", async () => {
  const aufrufe = [];
  await stop();
  await start({ ready: true, revision: "v1.0.0" }, async () => aufrufe.push(1));

  const antwort = await fetch(`${base}/analyze`, {
    method: "POST",
    headers: { "content-type": "image/jpeg" },
    body: Buffer.alloc(MAX_BODY_BYTES + 1),
  });

  assert.equal(antwort.status, 413);
  assert.equal(aufrufe.length, 0);
});

test("ein Fehler des Modells wird zu 500 mit festem Satz ohne Stacktrace", async () => {
  await stop();
  await start({ ready: true, revision: "v1.0.0" }, async () => {
    throw new Error("sharp: /geheim/pfad.jpg: korrupt");
  });

  const antwort = await fetch(`${base}/analyze`, jpeg());
  const koerper = await antwort.json();

  assert.equal(antwort.status, 500);
  assert.deepEqual(koerper, { error: "Die Auswertung ist fehlgeschlagen." });
});

test("ohne Bereitschaft wird POST /analyze mit 503 beantwortet", async () => {
  await stop();
  await start({ ready: false, revision: null });

  const antwort = await fetch(`${base}/analyze`, jpeg());

  assert.equal(antwort.status, 503);
});

test("unbekannte Pfade und Methoden antworten 404", async () => {
  for (const [pfad, methode] of [["/", "GET"], ["/analyze", "GET"], ["/health", "POST"]]) {
    const antwort = await fetch(`${base}${pfad}`, { method: methode });
    assert.equal(antwort.status, 404);
  }
});

test("die Fehlerkörper sind JSON mit genau einem Feld", async () => {
  const antwort = await fetch(`${base}/gibt-es-nicht`);

  assert.match(antwort.headers.get("content-type"), /application\/json/);
  assert.deepEqual(Object.keys(await antwort.json()), ["error"]);
});
