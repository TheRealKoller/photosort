import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { access, readFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Modellgewichte werden gepinnt und gehasht (S20): `pins.json` im Modellverzeichnis hält die
 * HF-Revision, den Commit-SHA und je Datei den SHA-256. Weichen Datei oder Hash ab, bricht der
 * Lauf ab, bevor das SDK lädt — im Lauf findet kein Download statt.
 */
export class PinError extends Error {
  constructor(message) {
    super(message);
    this.name = "PinError";
  }
}

export const PIN_FILE = "pins.json";
export const REQUIRED_FILES = ["eye.tflite", "eye_meta.json"];

export async function sha256File(pfad) {
  const hash = createHash("sha256");
  for await (const stueck of createReadStream(pfad)) hash.update(stueck);
  return hash.digest("hex");
}

export async function loadPins(directory) {
  const pfad = join(directory, PIN_FILE);
  try {
    await access(pfad);
  } catch {
    throw new PinError(
      `${pfad} fehlt. pins.json hält Revision, Commit-SHA und SHA-256 je Datei (S20); ohne Pins gibt es keinen Lauf.`,
    );
  }
  let gelesen;
  try {
    gelesen = JSON.parse(await readFile(pfad, "utf8"));
  } catch (error) {
    throw new PinError(`${pfad} ist nicht lesbar: ${error.message}`);
  }
  if (!gelesen?.files || typeof gelesen.files !== "object") {
    throw new PinError(`${pfad} nennt keine Dateien unter „files“.`);
  }
  return gelesen;
}

export async function verifyPins({ directory, pins }) {
  const erwartet = { ...pins?.files };
  for (const name of REQUIRED_FILES) {
    if (!erwartet[name]) {
      throw new PinError(`pins.json nennt keinen SHA-256 für ${name}.`);
    }
  }

  const geprueft = [];
  for (const [name, erwartetHash] of Object.entries(erwartet)) {
    const pfad = join(directory, name);
    let istHash;
    try {
      istHash = await sha256File(pfad);
    } catch {
      throw new PinError(`${name} fehlt im Modellverzeichnis ${directory}; erwartet wurde SHA-256 ${erwartetHash}.`);
    }
    if (istHash !== erwartetHash) {
      throw new PinError(
        `SHA-256 von ${name} weicht ab: erwartet ${erwartetHash}, gefunden ${istHash}. Der Lauf bricht ab, bevor das SDK lädt.`,
      );
    }
    geprueft.push(name);
  }

  return { ok: true, checked: geprueft, revision: pins.revision ?? null, commit: pins.commit ?? null };
}
