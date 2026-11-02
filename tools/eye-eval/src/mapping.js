import { createHash } from "node:crypto";

/**
 * Die eingefrorene Zuordnung Eye-Signal → Zweck. Sie steht wörtlich im Ergebnis und wird VOR dem
 * ersten Vergleichslauf festgelegt.
 *
 * Der Hash daneben ist die Sperre gegen nachträgliches Anpassen an die Ergebnisse: ein Vorlauf
 * schreibt ihn in den Arbeitsbereich, jeder weitere Lauf prüft ihn und bricht bei Abweichung vor
 * dem ersten SDK-Aufruf ab. `Object.freeze` allein hielte nur den laufenden Prozess ab, nicht eine
 * bearbeitete Datei zwischen zwei Läufen.
 */
export function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const inner of Object.values(value)) deepFreeze(inner);
    Object.freeze(value);
  }
  return value;
}

export class MappingError extends Error {
  constructor(message) {
    super(message);
    this.name = "MappingError";
  }
}

export const EYE_PURPOSE_MAPPING = deepFreeze({
  version: "eye-4.2.3/v1",
  sdk: "@desert-ant-labs/eye/native",
  modelRevision: "v1.0.0",
  thresholds: {
    tagConfidence: 0.5,
    strictConfidence: 0.9,
    faceArea: 0.02,
    motifPresent: 0.5,
  },
  purposes: {
    motivstaerken: {
      label: "Motivstärken",
      signals: ["tags", "kind", "faces.count", "faces.area", "pets", "shot", "peak"],
      rule: "Je Motiv eine Schwelle „trifft zu / trifft nicht zu“ und eine Rangkorrelation über die acht Motive. Ein Tag zählt ab 0,5 Konfidenz.",
      motifs: {
        menschen: {
          tags: ["people", "portrait", "group_shot", "selfie"],
          faces: { minCount: 1, minArea: 0.02 },
          rule: "Menschen: mindestens ein erkanntes Gesicht, dessen Fläche mindestens 2 % des Bildes bedeckt, oder eine Personenszene ab Schwelle.",
        },
        landschaft: {
          tags: [
            "beach",
            "mountain",
            "sky",
            "forest",
            "lake",
            "river",
            "desert",
            "valley",
            "coast",
            "cloud",
            "sunset",
            "sunrise",
            "water",
            "sea",
            "field",
          ],
          rule: "Landschaft: eine der Natur- und Weitszenen ab Schwelle.",
        },
        bauwerk_sehenswuerdigkeit: {
          tags: [
            "building",
            "tower",
            "skyscraper",
            "bridge",
            "castle",
            "church",
            "mosque",
            "temple",
            "monument",
            "fountain",
            "arch",
            "lighthouse",
            "ruins",
            "stadium",
            "museum",
            "palace",
          ],
          rule: "Bauwerk/Sehenswürdigkeit: eine der Bauwerkszenen ab Schwelle.",
        },
        stadt_strasse: {
          tags: [
            "street",
            "road",
            "city",
            "town",
            "sidewalk",
            "traffic_light",
            "car",
            "bus",
            "building",
          ],
          rule: "Stadt/Straße: eine der Stadt- und Verkehrsszenen ab Schwelle.",
        },
        tiere: {
          tags: ["dog", "cat", "bird", "horse"],
          pets: { minCount: 1 },
          rule: "Tiere: eine Tierszene ab Schwelle oder mindestens ein erkanntes Tier.",
        },
        essen_trinken: {
          tags: [
            "food",
            "dish",
            "tableware",
            "drink",
            "coffee",
            "cake",
            "bread",
            "fruit",
            "plate",
            "restaurant",
            "cocktail",
          ],
          rule: "Essen/Trinken: eine der Speisen- und Getränkszenen ab Schwelle.",
        },
        aktivitaet: {
          tags: [
            "bicycle",
            "football",
            "soccer",
            "swimming",
            "ski",
            "surfing",
            "dancing",
            "skateboard",
            "basketball",
            "tennis",
          ],
          shot: ["wide", "medium"],
          rule: "Aktivität: eine Sportszene ab Schwelle oder ein weiter bis mittlerer Bildausschnitt zusammen mit einem Bewegungs- oder Spitzenmoment-Signal.",
        },
        detail_stimmung: {
          tags: ["flower", "leaf", "furniture", "interior"],
          shot: ["close_up", "extreme_close_up"],
          rule: "Detail/Stimmung: eine Detail- oder Interieurszene ab Schwelle bei nahem Bildausschnitt.",
        },
      },
    },
    ausschluss: {
      label: "Ausschluss als Dokument oder Screenshot",
      signals: ["type"],
      excludedTypes: [
        "document",
        "screenshot",
        "receipt",
        "id_card",
        "whiteboard",
        "chart_or_slide",
        "map",
        "photo_of_screen",
        "medical_reference",
        "repair_reference",
        "shopping_reference",
        "meme_or_graphic",
      ],
      rule: "Eye-Typ in dieser Liste heißt „Eye schließt aus“. Falsch Ausgeschlossene und übersehene Dokumente werden getrennt gezählt.",
    },
    albumtauglichkeit: {
      label: "Albumtauglichkeit",
      signals: [
        "aesthetic",
        "keeper",
        "reject",
        "sharpness",
        "faces_analyze.eyes_open",
        "faces_analyze.blink",
        "faces_analyze.occlusion",
      ],
      levels: [
        { level: 1, min: 0, max: 0.2 },
        { level: 2, min: 0.2, max: 0.4 },
        { level: 3, min: 0.4, max: 0.6 },
        { level: 4, min: 0.6, max: 0.8 },
        { level: 5, min: 0.8, max: 1 },
      ],
      namedFlaws: ["geschlossene Augen", "verdeckte Gesichter"],
      defects: {
        closedEyes: { signal: "faces_analyze.eyes_open", maxEyesOpen: 0.5 },
        coveredFaces: {
          signal: "faces_analyze.occlusion",
          types: ["hand_or_object_covering", "face_mask", "sunglasses", "cut_off_by_frame"],
          minConfidence: 0.5,
        },
      },
      rule: "Eine Stufe 1–5 aus Note, Behaltenswert, Ablehnungsgründen und Schärfe; Rangkorrelation gegen die Cloud-Stufe. Geschlossene Augen und verdeckte Gesichter werden zusätzlich in beide Richtungen gezählt.",
    },
    feinlabels: {
      label: "Feinlabels",
      signals: ["tags"],
      automaticMatch: false,
      rule: "Die stärksten Szenen und Tags stehen gegen den Rohlabel-Text. Die Vokabulare sind verschieden, ein automatischer Treffervergleich entfällt — das Urteil kommt aus dem Paarvergleich.",
    },
    sehenswuerdigkeit: {
      label: "Sehenswürdigkeitsnamen",
      signals: ["tags"],
      tags: [
        "building",
        "tower",
        "skyscraper",
        "bridge",
        "castle",
        "church",
        "mosque",
        "temple",
        "monument",
        "fountain",
        "arch",
        "lighthouse",
        "ruins",
        "stadium",
        "museum",
        "palace",
      ],
      expectedVerdict: "schlechter / nicht geeignet",
      rule: "Eye liefert nur Szenenkategorien, keine Eigennamen. Auf den Landmark-Kandidaten wird gemessen, wie oft eine Bauwerk- oder Wahrzeichen-Szene erkannt wird.",
    },
  },
});

function kanonisch(value) {
  if (Array.isArray(value)) return `[${value.map(kanonisch).join(",")}]`;
  if (value && typeof value === "object") {
    const felder = Object.keys(value)
      .sort()
      .map((schluessel) => `${JSON.stringify(schluessel)}:${kanonisch(value[schluessel])}`);
    return `{${felder.join(",")}}`;
  }
  return JSON.stringify(value);
}

export function mappingHash(table = EYE_PURPOSE_MAPPING) {
  return `sha256:${createHash("sha256").update(kanonisch(table)).digest("hex")}`;
}

/** Sperre gegen eine nachträglich bearbeitete Tabelle: `undefined`/`null` heißt „kein Vorlauf“. */
export function assertMappingHash(stored) {
  if (stored === undefined || stored === null) return true;
  if (stored !== EYE_PURPOSE_MAPPING_HASH) {
    throw new MappingError(
      `Die Zuordnungstabelle weicht vom Vorlauf ab (gespeichert ${stored}, aktuell ${EYE_PURPOSE_MAPPING_HASH}). Der Lauf bricht ab, bevor ein SDK-Aufruf stattfindet.`,
    );
  }
  return true;
}

export const EYE_PURPOSE_MAPPING_HASH = mappingHash();
