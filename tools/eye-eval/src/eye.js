import { loadPins, verifyPins } from "./pins.js";

/**
 * Die dünne Adaptergrenze zum SDK. Nichts hier wird im Unit-Test geladen: `@desert-ant-labs/eye`
 * und `sharp` kommen erst zur Laufzeit ins Spiel (`await import`), die Tests prüfen die reinen
 * Funktionen davor.
 *
 * Die Lizenzprüfung des SDK bleibt unangetastet (S1/S2). Gesetzt wird ausschließlich
 * `DAL_APP_ID`; ein gesetztes `DAL_LICENSE_ENDPOINT` oder ein API-Key bricht ab, weil beides die
 * Lizenz verletzt (S3).
 */
export const APP_ID = "photosort-eye-eval";

export function assertLicenseEnvironment(env = process.env) {
  if (env.DAL_LICENSE_ENDPOINT) {
    throw new Error(
      "DAL_LICENSE_ENDPOINT ist gesetzt. Umleiten oder Blockieren der Lizenzprüfung verletzt die Lizenz (S2); der Lauf bricht ab.",
    );
  }
  if (env.HF_TOKEN) {
    throw new Error("HF_TOKEN ist gesetzt; im Lauf findet kein Download statt und kein Token gehört in den Container (S20).");
  }
  if (env.DAL_APP_ID !== APP_ID) {
    throw new Error(
      `DAL_APP_ID muss ${APP_ID} sein (S3), war ${env.DAL_APP_ID ? "ein anderer Wert" : "nicht gesetzt"}.`,
    );
  }
}

export async function openModel({ directory }) {
  const pins = await loadPins(directory);
  const geprueft = await verifyPins({ directory, pins });
  const { Eye } = await import("@desert-ant-labs/eye/native");
  const eye = await Eye.load({ directory });
  return { eye, pins: geprueft };
}

export async function analyzeDisplayFile(eye, pfad) {
  const { default: sharp } = await import("sharp");
  const { data, info } = await sharp(pfad).rotate().removeAlpha().raw().toBuffer({
    resolveWithObject: true,
  });
  const analysis = await eye.analyze({ data, width: info.width, height: info.height });
  return typeof analysis.toJSON === "function" ? analysis.toJSON() : JSON.parse(JSON.stringify(analysis));
}
