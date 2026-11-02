/**
 * Formprüfung der selbst erzeugten `run.json`. Kein Schema: geprüft wird nur, was `pages`,
 * `serve` und `summary` zwingend lesen — fehlt eines, bricht der Lauf mit dem Feldnamen ab,
 * statt an einer `TypeError`-Meldung aus dem Nirgendwo zu scheitern.
 */
export class RunFileError extends Error {
  constructor(pfad, was) {
    super(`${pfad} ist beschädigt: ${was}. Ein neues \`prepare\` erzeugt die Datei aus der Datenbank.`);
    this.name = "RunFileError";
    this.pfad = pfad;
    this.was = was;
  }
}

function istObjekt(wert) {
  return typeof wert === "object" && wert !== null && !Array.isArray(wert);
}

function brauche(bedingung, pfad, was) {
  if (!bedingung) throw new RunFileError(pfad, was);
}

export function validateRun(run, pfad) {
  brauche(istObjekt(run), pfad, "der Inhalt ist kein Objekt");
  brauche(Number.isFinite(run.version), pfad, "„version“ fehlt");
  brauche(Number.isFinite(run.seed), pfad, "„seed“ fehlt");
  brauche(typeof run.mappingHash === "string" && run.mappingHash.length > 0, pfad, "„mappingHash“ fehlt");
  brauche(istObjekt(run.sample) && Array.isArray(run.sample.projects), pfad, "„sample.projects“ fehlt");
  run.sample.projects.forEach((projekt, i) => {
    brauche(istObjekt(projekt), pfad, `„sample.projects[${i}]“ ist kein Objekt`);
    brauche(Array.isArray(projekt.photos), pfad, `„sample.projects[${i}].photos“ fehlt`);
    projekt.photos.forEach((foto, j) => {
      brauche(istObjekt(foto), pfad, `„sample.projects[${i}].photos[${j}]“ ist kein Objekt`);
      brauche(Number.isFinite(foto.photoId), pfad, `„sample.projects[${i}].photos[${j}].photoId“ fehlt`);
    });
  });
  brauche(istObjekt(run.baseline) && istObjekt(run.baseline.purposes), pfad, "„baseline.purposes“ fehlt");
  brauche(
    istObjekt(run.baseline.runs) && Array.isArray(run.baseline.runs.projects),
    pfad,
    "„baseline.runs.projects“ fehlt",
  );
  brauche(
    istObjekt(run.baseline.runs.models) &&
      Array.isArray(run.baseline.runs.models.category) &&
      Array.isArray(run.baseline.runs.models.landmark),
    pfad,
    "„baseline.runs.models“ fehlt",
  );
  return run;
}

export function parseRun(text, pfad) {
  let run;
  try {
    run = JSON.parse(text);
  } catch {
    throw new RunFileError(pfad, "kein gültiges JSON");
  }
  return validateRun(run, pfad);
}
