import { loadPins, verifyPins } from "./pins.js";

/**
 * Die dünne Grenze zum SDK. Hier wird NICHTS gerechnet: die Analyse geht unverändert an das
 * Backend, die Abbildung auf Motive, Ausschluss, Albumstufe und Feinlabels steht in
 * `backend/src/photosort/eye_mapping.py` (Spec 0609, „Abbildung in Python, nicht im Dienst").
 *
 * Die Lizenz des Fremdpakets bleibt unangetastet (S2): gesetzt wird ausschließlich `DAL_APP_ID`.
 * Ein gesetztes `DAL_LICENSE_ENDPOINT`, ein `HF_TOKEN` oder eine Proxy-Variable bricht den Start
 * ab, weil jede davon den Lizenzweg umleiten würde. Der Egress selbst ist Betreiberpflicht
 * (`docs/setup.md`) - dieser Code täuscht keine Filterung vor.
 */
export const APP_ID = "photosort";

export function assertLicenseEnvironment(env = process.env) {
  if (env.DAL_LICENSE_ENDPOINT) {
    throw new Error("Eine Umleitung der Lizenzprüfung ist gesetzt; der Start bricht ab.");
  }
  if (env.HF_TOKEN) {
    throw new Error("Ein Token für den Modelldownload ist gesetzt; im Betrieb wird nichts geladen.");
  }
  const proxies = Object.keys(env).filter(
    (name) => name.endsWith("_PROXY") && typeof env[name] === "string" && env[name] !== "",
  );
  if (proxies.length > 0) {
    throw new Error("Eine Proxy-Variable ist gesetzt; der Lizenzweg darf nicht umgeleitet werden.");
  }
  if (env.DAL_APP_ID !== APP_ID) {
    throw new Error("DAL_APP_ID fehlt oder ist falsch; der Start bricht ab.");
  }
}

/**
 * Prüft die Pins und lädt erst dann das SDK. Reihenfolge ist Zusage: eine fehlende oder fremde
 * Gewichtsdatei endet, bevor Modellcode läuft, und `/health` bleibt bis dahin ohne 200.
 */
export async function openModel({ directory, pins }) {
  const gepinnt = pins ?? (await loadPins());
  const geprueft = await verifyPins({ directory, pins: gepinnt });
  const { Eye } = await import("@desert-ant-labs/eye/native");
  const eye = await Eye.load({ directory });
  return { eye, pins: geprueft };
}

/** JPEG-Bytes hinein, die rohe SDK-Analyse als JSON-Objekt heraus. */
export async function analyzeBytes(eye, bytes) {
  const { default: sharp } = await import("sharp");
  const { data, info } = await sharp(bytes)
    .rotate()
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const analysis = await eye.analyze({ data, width: info.width, height: info.height });
  return typeof analysis.toJSON === "function"
    ? analysis.toJSON()
    : JSON.parse(JSON.stringify(analysis));
}
