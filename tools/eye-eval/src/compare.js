import { EYE_PURPOSE_MAPPING } from "./mapping.js";
import { describeEye, extractSignals, MOTIF_LABELS } from "./signals.js";

/**
 * Baut aus Stichprobe, Basis und Analysen je Zweck die Paare. Beide Seiten bleiben anonym: die
 * Texte nennen weder Anbieter noch Modell, damit die Seite sie gefahrlos links oder rechts
 * anzeigen kann. Fotos ohne Basis oder ohne Analyse fallen je Zweck heraus und werden gezählt —
 * eine fehlende Landmark- oder Feinlabel-Zeile ist „keine Basis“, kein Laufabbruch.
 */
export const PURPOSE_ORDER = [
  "motivstaerken",
  "ausschluss",
  "albumtauglichkeit",
  "feinlabels",
  "sehenswuerdigkeit",
];

const KEINE_ANGABE = "ohne Angabe";

function text(verdict, reason) {
  return { verdict, reason: reason || KEINE_ANGABE };
}

export function describeCloud(row, purpose) {
  switch (purpose) {
    case "motivstaerken": {
      const staerken = row.strengths ?? {};
      const treffer = Object.keys(MOTIF_LABELS).filter(
        (motifKey) => (staerken[motifKey] ?? 0) >= EYE_PURPOSE_MAPPING.thresholds.motifPresent,
      );
      return text(
        treffer.length
          ? `Motive: ${treffer.map((key) => MOTIF_LABELS[key]).join(", ")}`
          : "Kein Motiv über der Schwelle",
        row.complete ? "Bewertung vollständig" : "Bewertung unvollständig",
      );
    }
    case "ausschluss":
      return text(
        row.excludedDocument ? "Ausschluss: ja" : "Ausschluss: nein",
        row.excludedDocument
          ? "Als Dokument oder Bildschirmfoto erkannt"
          : "Nicht als Dokument oder Bildschirmfoto erkannt",
      );
    case "albumtauglichkeit":
      return text(
        typeof row.level === "number" ? `Stufe ${row.level}` : "Keine Stufe",
        row.reason ? `Benannter Mangel: ${row.reason}` : "Kein benannter Mangel",
      );
    case "feinlabels": {
      const labels = (row.labels ?? []).map((label) => label.rawLabel).filter(Boolean);
      return text(
        labels.length ? "Szene erkannt" : "Keine Szene erkannt",
        labels.length ? `Erkannt: ${labels.slice(0, 3).join(", ")}` : "Nicht beurteilbar: keine Szene",
      );
    }
    case "sehenswuerdigkeit":
      return text(
        row.name ? "Bauwerk oder Wahrzeichen erkannt" : "Kein Bauwerk erkannt",
        row.name ? `Erkannt: ${row.name}` : "Nicht beurteilbar: keine Angabe",
      );
    default:
      throw new Error(`Unbekannter Zweck „${purpose}“.`);
  }
}

export function buildItems({ sample, baseline, analyses }) {
  const analyseProFoto =
    analyses instanceof Map ? analyses : new Map(Object.entries(analyses ?? {}).map(([id, wert]) => [Number(id), wert]));
  const fotos = sample.projects.flatMap((project) => project.photos);
  const ohneAnalyse = fotos.filter((foto) => !analyseProFoto.has(foto.photoId));

  const items = {};
  const fehlendeBasis = {};
  for (const purpose of PURPOSE_ORDER) {
    const basisProFoto = new Map(
      (baseline.purposes[purpose]?.photos ?? []).map((row) => [row.photoId, row]),
    );
    const liste = [];
    let ohneBasis = 0;

    for (const foto of fotos) {
      const row = basisProFoto.get(foto.photoId);
      if (!row) {
        ohneBasis += 1;
        continue;
      }
      const analysis = analyseProFoto.get(foto.photoId);
      if (!analysis) continue;
      liste.push({
        photoId: foto.photoId,
        projectId: foto.projectId,
        image: `images/${foto.photoId}.jpg`,
        first: describeCloud(row, purpose),
        second: describeEye(extractSignals(analysis), purpose),
      });
    }

    items[purpose] = liste;
    fehlendeBasis[purpose] = ohneBasis;
  }

  return {
    items,
    missing: { withoutAnalysis: ohneAnalyse.length, withoutBaseline: fehlendeBasis },
    purposes: PURPOSE_ORDER,
  };
}

