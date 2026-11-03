import { createServer } from "node:http";
import { pathToFileURL } from "node:url";

import { analyzeBytes, assertLicenseEnvironment, openModel } from "./model.js";

/**
 * Der Eye-Sidecar: zwei Routen, sonst nichts.
 *
 * S3 (Spec 0609): `POST /analyze` nimmt BYTES, keine Pfade, keine Felder, kein Multipart - nur
 * `Content-Type: image/jpeg` und höchstens 8 MiB, geprüft VOR dem Modell. Antworten und Fehler
 * sind JSON mit festen Sätzen; ein Stacktrace, ein Host oder ein Pin verlässt den Dienst nicht.
 *
 * S4: `/health` antwortet erst `200`, wenn die Pins geprüft und das Modell geladen ist. Scheitert
 * der Start, endet der Prozess - es gibt keinen Zustand „läuft, aber tut nichts".
 */
export const MAX_BODY_BYTES = 8 * 1024 * 1024;
export const DEFAULT_PORT = 8090;
const CONTENT_TYPE = "image/jpeg";

const FIXED = Object.freeze({
  onlyJpeg: "Nur JPEG wird angenommen.",
  tooLarge: "Das Bild ist zu groß.",
  notReady: "Das Modell ist noch nicht bereit.",
  failed: "Die Auswertung ist fehlgeschlagen.",
  notFound: "Unbekannter Pfad.",
});

function sendJson(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store",
  });
  response.end(payload);
}

async function readBody(request, limit) {
  const chunks = [];
  let gelesen = 0;
  for await (const chunk of request) {
    gelesen += chunk.length;
    if (gelesen > limit) {
      throw Object.assign(new Error("zu gross"), { code: "TOO_LARGE" });
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

/**
 * Baut den Server um eine Analyse-Funktion und einen Zustand. Beides ist injizierbar, damit die
 * Tests ohne Modell laufen (CI hat keine Gewichte).
 */
export function createApp({ analyze, state }) {
  return createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://eye.local");

    if (request.method === "GET" && url.pathname === "/health") {
      if (!state.ready) {
        sendJson(response, 503, { status: "starting", detail: FIXED.notReady });
        return;
      }
      sendJson(response, 200, { status: "ok", model_revision: state.revision });
      return;
    }

    if (request.method === "POST" && url.pathname === "/analyze") {
      if (request.headers["content-type"] !== CONTENT_TYPE) {
        sendJson(response, 415, { error: FIXED.onlyJpeg });
        return;
      }
      const angekuendigt = Number(request.headers["content-length"] ?? "0");
      if (Number.isFinite(angekuendigt) && angekuendigt > MAX_BODY_BYTES) {
        sendJson(response, 413, { error: FIXED.tooLarge });
        return;
      }
      let bytes;
      try {
        bytes = await readBody(request, MAX_BODY_BYTES);
      } catch {
        sendJson(response, 413, { error: FIXED.tooLarge });
        return;
      }
      if (!state.ready) {
        sendJson(response, 503, { error: FIXED.notReady });
        return;
      }
      try {
        sendJson(response, 200, await analyze(bytes));
      } catch {
        sendJson(response, 500, { error: FIXED.failed });
      }
      return;
    }

    sendJson(response, 404, { error: FIXED.notFound });
  });
}

async function main() {
  assertLicenseEnvironment();
  const directory = process.env.EYE_MODEL_DIR ?? "/model";
  const port = Number(process.env.EYE_PORT ?? DEFAULT_PORT);
  const state = { ready: false, revision: null };

  let eye = null;
  const server = createApp({
    state,
    analyze: async (bytes) => {
      if (eye === null) throw new Error("kein Modell");
      return analyzeBytes(eye, bytes);
    },
  });
  server.listen(port, "0.0.0.0");

  try {
    const model = await openModel({ directory });
    eye = model.eye;
    state.revision = model.pins.revision;
    state.ready = true;
  } catch {
    // Fail-closed: kein Zustand "läuft, aber ohne geprüftes Modell".
    console.error("Der Eye-Dienst konnte nicht starten: Modell oder Pins sind nicht in Ordnung.");
    process.exit(1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
