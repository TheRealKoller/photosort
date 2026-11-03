import { createWriteStream } from "node:fs";
import { readdir, rename, rm } from "node:fs/promises";
import { join } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { pathToFileURL } from "node:url";

import { loadPins, sha256File, verifyPins } from "./pins.js";

/**
 * Der Einmal-Dienst `eye-model` (`--profile eye-setup`): holt die Gewichte des gepinnten Modells
 * in das Volume `eye_model` und prüft jede Datei gegen ihren SHA-256, BEVOR sie an ihren Platz
 * wandert.
 *
 * S4: die Dateien liegen nie im Repository und nie im Image - sie entstehen hier, einmalig, auf
 * dem Heimserver. Gepinnt ist allein ihr Hash (`src/pins.json`); es gibt keinen Weg, den Hash aus
 * der Umgebung zu setzen.
 *
 * Kein Token, keine Umleitung: der Download geht ohne Anmeldung an den öffentlichen Ort des
 * gepinnten Commits, und ein gesetzter Proxy bricht ab - sonst käme der Inhalt von woanders.
 */
export const MODEL_SOURCE = "https://huggingface.co";

export function assertDownloadEnvironment(env = process.env) {
  if (env.HF_TOKEN) {
    throw new Error("Ein Token ist gesetzt; der Modelldownload braucht keins.");
  }
  const proxies = Object.keys(env).filter(
    (name) => name.endsWith("_PROXY") && typeof env[name] === "string" && env[name] !== "",
  );
  if (proxies.length > 0) {
    throw new Error("Eine Proxy-Variable ist gesetzt; der Download darf nicht umgeleitet werden.");
  }
}

export function fileUrl({ revision, name, base = MODEL_SOURCE }) {
  return `${base}/desert-ant-labs/eye/resolve/${revision}/${name}`;
}

async function download({ url, ziel, fetchImpl }) {
  const antwort = await fetchImpl(url, { redirect: "follow" });
  if (!antwort.ok) {
    throw new Error(`Der Abruf ist fehlgeschlagen (Status ${antwort.status}).`);
  }
  await pipeline(Readable.fromWeb(antwort.body), createWriteStream(ziel));
}

/**
 * Lädt jede gepinnte Datei, die fehlt oder deren Hash abweicht, und prüft danach ALLE Dateien
 * gegen die Pins. Ein falscher Hash lässt die Datei nicht an ihrem Platz: der Aufrufer bekommt
 * einen Fehler und das Volume bleibt unbrauchbar, statt halb gefüllt zu sein.
 */
export async function fetchModel({ directory, pins, fetchImpl = fetch, base = MODEL_SOURCE }) {
  const gepinnt = pins ?? (await loadPins());

  const vorhanden = new Set(await readdir(directory).catch(() => []));
  for (const name of Object.keys(gepinnt.files)) {
    if (vorhanden.has(name)) {
      const hash = await sha256File(join(directory, name)).catch(() => null);
      if (hash === gepinnt.files[name]) continue;
      await rm(join(directory, name), { force: true });
    }
    const zwischenstand = join(directory, `${name}.teil`);
    await download({
      url: fileUrl({ revision: gepinnt.revision, name, base }),
      ziel: zwischenstand,
      fetchImpl,
    });
    const hash = await sha256File(zwischenstand);
    if (hash !== gepinnt.files[name]) {
      await rm(zwischenstand, { force: true });
      throw new Error(`SHA-256 von ${name} weicht von den Pins ab.`);
    }
    await rename(zwischenstand, join(directory, name));
  }
  return verifyPins({ directory, pins: gepinnt });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    assertDownloadEnvironment();
    const directory = process.env.EYE_MODEL_DIR ?? "/model";
    const geprueft = await fetchModel({ directory });
    console.log(`Modell ${geprueft.revision} bereitgestellt: ${geprueft.checked.join(", ")}.`);
  } catch (error) {
    console.error(`Der Modelldownload ist fehlgeschlagen: ${error.message}`);
    process.exit(1);
  }
}
