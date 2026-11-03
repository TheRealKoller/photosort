import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Die Pins des Modells: Revision, Commit-SHA und je Datei der SHA-256.
 *
 * S4 (Spec 0609): die Gewichte liegen NIE in Repository oder Image, gepinnt ist aber ihr Hash.
 * `pins.json` steht neben diesem Modul im Image; geprüft wird bei JEDEM Start vor `/health` 200.
 * Ein Env-Wert als Pin gibt es nicht, und es wird nichts nachgeladen.
 *
 * Seit dem Abgleich mit dem echten SDK-Vokabular (`@desert-ant-labs/eye/tags.js`) trägt dieselbe
 * Datei auch `mappingTags`: die Tags, aus denen das Backend Motivstärken bildet. Damit fällt ein
 * Pin-Wechsel, der einen Tag umbenennt, beim Start und im Test auf - und nicht als stille Null in
 * jedem Eye-Ergebnis.
 */
export class PinError extends Error {
  constructor(message) {
    super(message);
    this.name = "PinError";
  }
}

export const PINS_PATH = join(dirname(fileURLToPath(import.meta.url)), "pins.json");
export const REQUIRED_FILES = ["eye.tflite", "eye_meta.json"];
const HASH_PATTERN = /^[0-9a-f]{64}$/;
const COMMIT_PATTERN = /^[0-9a-f]{40}$/;

/** Prüft die Form der Pin-Datei - ohne eine einzige Datei zu lesen. */
export function parsePins(raw) {
  if (!raw || typeof raw !== "object") {
    throw new PinError("pins.json ist kein Objekt.");
  }
  const revision = typeof raw.revision === "string" ? raw.revision.trim() : "";
  if (revision === "") {
    throw new PinError("pins.json nennt keine Revision; ohne Pin gibt es keinen Start.");
  }
  const commit = typeof raw.commit === "string" ? raw.commit.trim() : "";
  if (!COMMIT_PATTERN.test(commit)) {
    throw new PinError("pins.json nennt keinen 40-stelligen Commit-SHA; ohne Pin gibt es keinen Start.");
  }
  if (!raw.files || typeof raw.files !== "object") {
    throw new PinError("pins.json nennt keine Dateien unter „files“.");
  }
  for (const name of REQUIRED_FILES) {
    const hash = raw.files[name];
    if (typeof hash !== "string" || !HASH_PATTERN.test(hash)) {
      throw new PinError(`pins.json nennt keinen gültigen SHA-256 für ${name}.`);
    }
  }
  if (!Array.isArray(raw.mappingTags) || raw.mappingTags.length === 0) {
    throw new PinError("pins.json nennt keine Zuordnungs-Tags unter „mappingTags“.");
  }
  if (raw.mappingTags.some((tag) => typeof tag !== "string" || tag === "")) {
    throw new PinError("pins.json führt unter „mappingTags“ einen leeren oder nicht-textlichen Tag.");
  }
  return raw;
}

/** Liest und prüft die Pin-Datei des Images. */
export async function loadPins(pfad = PINS_PATH) {
  let gelesen;
  try {
    gelesen = JSON.parse(await readFile(pfad, "utf8"));
  } catch (error) {
    throw new PinError(`pins.json ist nicht lesbar: ${error.message}`);
  }
  return parsePins(gelesen);
}

/** Der SHA-256 einer Datei, stückweise - die Gewichte sind 66 MiB, die passen nicht am Stück. */
export async function sha256File(pfad) {
  const hash = createHash("sha256");
  for await (const stueck of createReadStream(pfad)) hash.update(stueck);
  return hash.digest("hex");
}

/** Vergleicht jede genannte Datei im Modellverzeichnis mit ihrem Pin. Bricht beim ersten ab. */
export async function verifyPins({ directory, pins }) {
  const checked = [];
  for (const [name, erwartet] of Object.entries(pins.files)) {
    let gefunden;
    try {
      gefunden = await sha256File(join(directory, name));
    } catch {
      throw new PinError(`${name} fehlt im Modellverzeichnis.`);
    }
    if (gefunden !== erwartet) {
      throw new PinError(`SHA-256 von ${name} weicht von den Pins ab.`);
    }
    checked.push(name);
  }
  return { ok: true, checked, revision: pins.revision, commit: pins.commit };
}
