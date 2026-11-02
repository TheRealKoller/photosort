import { EYE_PURPOSE_MAPPING } from "./mapping.js";

/**
 * Reine Funktion über die bereits ermittelte Analyse: hier entstehen die Signale und die beiden
 * Textzeilen je Zweck. Kein SDK, keine Bilddaten — deshalb im Unit-Test prüfbar.
 *
 * Keine Zahlen in den Texten: die Seite soll die Herkunft nicht verraten, und Konfidenzzahlen sind
 * genau der Hinweis, den der Paarvergleich ausschließen will.
 */
export const MOTIF_LABELS = {
  menschen: "Menschen",
  landschaft: "Landschaft",
  bauwerk_sehenswuerdigkeit: "Bauwerk",
  stadt_strasse: "Stadt und Straße",
  tiere: "Tiere",
  essen_trinken: "Essen und Trinken",
  aktivitaet: "Aktivität",
  detail_stimmung: "Detail und Stimmung",
};

const AUSSCHLUSS_TAGS = EYE_PURPOSE_MAPPING.purposes.ausschluss.excludedTypes;

function konfidenz(tags, name) {
  const wert = tags?.[name];
  return typeof wert === "number" && Number.isFinite(wert) ? wert : 0;
}

function zahlOderNull(wert) {
  return typeof wert === "number" && Number.isFinite(wert) ? wert : null;
}

function flaeche(box) {
  if (!box) return null;
  const breite = Math.max(0, (box.x1 ?? 0) - (box.x0 ?? 0));
  const hoehe = Math.max(0, (box.y1 ?? 0) - (box.y0 ?? 0));
  return breite * hoehe;
}

function staerkster(scores) {
  if (!scores || typeof scores !== "object") return null;
  let bestes = null;
  for (const [name, wert] of Object.entries(scores)) {
    if (typeof wert !== "number" || !Number.isFinite(wert)) continue;
    if (bestes === null || wert > bestes.wert) bestes = { name, wert };
  }
  return bestes && bestes.wert >= 0.5 ? bestes.name : null;
}

export function extractSignals(analysis = {}) {
  const tags = analysis.confidences ?? {};
  const faces = (analysis.faces ?? []).map((face) => ({
    confidences: face.confidences ?? {},
    area: flaeche(face.box),
  }));
  const pets = (analysis.pets ?? []).map((pet) => pet.label).filter(Boolean);
  const scores = analysis.scores ?? {};

  return {
    model: typeof analysis.model === "string" ? analysis.model : null,
    kind: typeof analysis.kind === "string" ? analysis.kind : null,
    tags,
    scores: {
      aesthetic: zahlOderNull(scores.aesthetic),
      keeper: zahlOderNull(scores.keeper),
      cover: zahlOderNull(scores.cover),
    },
    faces,
    faceCount: faces.length,
    faceArea: faces.reduce((groesste, face) => Math.max(groesste, face.area ?? 0), 0),
    pets,
    petCount: pets.length,
    shot: staerkster(analysis.details?.layout?.shot),
  };
}

export function motifMatches(signals, motifKey, thresholds = EYE_PURPOSE_MAPPING.thresholds) {
  const motiv = EYE_PURPOSE_MAPPING.purposes.motivstaerken.motifs[motifKey];
  if (!motiv) throw new Error(`Unbekanntes Motiv „${motifKey}“.`);

  if ((motiv.tags ?? []).some((tag) => konfidenz(signals.tags, tag) >= thresholds.tagConfidence)) {
    return true;
  }
  if (
    motiv.faces &&
    signals.faceCount >= motiv.faces.minCount &&
    signals.faceArea >= motiv.faces.minArea
  ) {
    return true;
  }
  if (motiv.pets && signals.petCount >= motiv.pets.minCount) {
    return true;
  }
  if (motiv.shot && signals.shot && motiv.shot.includes(signals.shot)) {
    if (motifKey === "aktivitaet") {
      return konfidenz(signals.tags, "peak_moment") >= thresholds.motifPresent;
    }
    return true;
  }
  return false;
}

export function eyeLevel(signals) {
  const note = signals.scores.aesthetic;
  if (note === null) return null;
  const stufe = EYE_PURPOSE_MAPPING.purposes.albumtauglichkeit.levels.find(
    (band) => note >= band.min && note < (band.max === 1 ? 1.0001 : band.max),
  );
  return stufe?.level ?? null;
}

export function albumDefects(signals) {
  const regeln = EYE_PURPOSE_MAPPING.purposes.albumtauglichkeit.defects;
  let geschlosseneAugen = false;
  let verdecktesGesicht = false;

  for (const face of signals.faces) {
    const offen = konfidenz(face.confidences, "eyes_open");
    if (face.confidences.eyes_open !== undefined && offen < regeln.closedEyes.maxEyesOpen) {
      geschlosseneAugen = true;
    }
    for (const typ of regeln.coveredFaces.types) {
      if (konfidenz(face.confidences, typ) >= regeln.coveredFaces.minConfidence) {
        verdecktesGesicht = true;
      }
    }
  }

  return { geschlosseneAugen, verdecktesGesicht };
}

function starkeTags(signals, ausschluss = new Set()) {
  return Object.entries(signals.tags)
    .filter(([name, wert]) => !ausschluss.has(name) && typeof wert === "number" && wert >= 0.5)
    .sort((links, rechts) => rechts[1] - links[1])
    .map(([name]) => name);
}

export function describeEye(signals, purpose) {
  switch (purpose) {
    case "motivstaerken": {
      const treffer = Object.keys(MOTIF_LABELS).filter((key) => motifMatches(signals, key));
      return {
        verdict: treffer.length
          ? `Motive: ${treffer.map((key) => MOTIF_LABELS[key]).join(", ")}`
          : "Kein Motiv über der Schwelle",
        reason: "Bewertung vollständig",
      };
    }
    case "ausschluss": {
      const typ = signals.kind;
      const ausgeschlossen = typ !== null && AUSSCHLUSS_TAGS.includes(typ);
      return {
        verdict: ausgeschlossen ? "Ausschluss: ja" : "Ausschluss: nein",
        reason: ausgeschlossen
          ? "Als Dokument oder Bildschirmfoto erkannt"
          : "Nicht als Dokument oder Bildschirmfoto erkannt",
      };
    }
    case "albumtauglichkeit": {
      const stufe = eyeLevel(signals);
      const maengel = albumDefects(signals);
      const gruende = [];
      if (maengel.geschlosseneAugen) gruende.push("Geschlossene Augen");
      if (maengel.verdecktesGesicht) gruende.push("Verdecktes Gesicht");
      return {
        verdict: stufe === null ? "Keine Stufe" : `Stufe ${stufe}`,
        reason: gruende.length ? `Benannter Mangel: ${gruende.join("; ")}` : "Kein benannter Mangel",
      };
    }
    case "feinlabels": {
      const tags = starkeTags(
        signals,
        new Set([...AUSSCHLUSS_TAGS, "photo", "people", "portrait", "group_shot", "kid", "adult"]),
      );
      return {
        verdict: tags.length ? "Szene erkannt" : "Keine Szene erkannt",
        reason: tags.length ? `Erkannt: ${tags.slice(0, 3).join(", ")}` : "Nicht beurteilbar: keine Szene",
      };
    }
    case "sehenswuerdigkeit": {
      const bauwerk = EYE_PURPOSE_MAPPING.purposes.sehenswuerdigkeit.tags.filter(
        (tag) => konfidenz(signals.tags, tag) >= 0.5,
      );
      return {
        verdict: bauwerk.length ? "Bauwerk oder Wahrzeichen erkannt" : "Kein Bauwerk erkannt",
        reason: bauwerk.length ? `Erkannt: ${bauwerk.join(", ")}` : "Nicht beurteilbar: keine Angabe",
      };
    }
    default:
      throw new Error(`Unbekannter Zweck „${purpose}“.`);
  }
}
