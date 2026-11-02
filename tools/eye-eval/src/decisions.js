import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";

/**
 * Entscheidungsdatei im Arbeitsbereich: Paarurteile je Foto und je Zweck, dazu der Zeiger auf die
 * zuletzt bearbeitete Stelle. Nur so übersteht ein Browser-Neuladen den Halbstand; ein stiller
 * Neuanfang würde bereits geleistete Arbeit vernichten, deshalb bricht `loadState` bei fehlender
 * oder beschädigter Datei mit Meldung ab statt eine leere Datei anzulegen.
 */
export const DECISIONS_VERSION = 1;
export const CHOICES = ["a", "same", "b"];

export class DecisionStoreError extends Error {
  constructor(message) {
    super(message);
    this.name = "DecisionStoreError";
  }
}

export function createState({ seed, purposes }) {
  if (!Array.isArray(purposes) || purposes.length === 0) {
    throw new DecisionStoreError("Ohne Zweck gibt es keinen Durchlauf.");
  }
  const zwecke = {};
  for (const purpose of purposes) {
    zwecke[purpose] = { index: 0, choices: {} };
  }
  return { version: DECISIONS_VERSION, seed, purposes: zwecke };
}

export function recordChoice(state, { purpose, photoId, choice, index }) {
  if (!Object.hasOwn(state.purposes, purpose)) {
    throw new DecisionStoreError(`Unbekannter Zweck „${purpose}“; die Datei kennt nur ${Object.keys(state.purposes).join(", ")}.`);
  }
  if (!CHOICES.includes(choice)) {
    throw new DecisionStoreError(`Unbekannte Wahl „${choice}“; erlaubt sind ${CHOICES.join(", ")}.`);
  }
  const vorher = state.purposes[purpose];
  return {
    ...state,
    purposes: {
      ...state.purposes,
      [purpose]: {
        index: Math.max(vorher.index, Number(index) || 0),
        choices: { ...vorher.choices, [String(photoId)]: choice },
      },
    },
  };
}

/**
 * Überspringen ist keine Wahl: der Zeiger rückt vor, die Zählung bleibt unberührt.
 *
 * Lesart (bewusst so, keine Verhaltensänderung): Überspringen nimmt eine frühere Stimme zu
 * demselben Foto **nicht** zurück. Wer sein Urteil korrigieren will, blättert mit „zurück“ und
 * wählt erneut; wer nur weitergehen will, ohne zu urteilen, überspringt. Eine Stimme
 * verschwindet damit ausschließlich durch eine neue Wahl, nie durch einen Sprung.
 */
export function recordSkip(state, { purpose, index }) {
  if (!Object.hasOwn(state.purposes, purpose)) {
    throw new DecisionStoreError(`Unbekannter Zweck „${purpose}“; die Datei kennt nur ${Object.keys(state.purposes).join(", ")}.`);
  }
  const vorher = state.purposes[purpose];
  return {
    ...state,
    purposes: {
      ...state.purposes,
      [purpose]: { ...vorher, index: Math.max(vorher.index, Number(index) || 0) },
    },
  };
}

export function countChoices(state, purpose) {
  const choices = state.purposes[purpose]?.choices ?? {};
  const werte = Object.values(choices);
  return {
    a: werte.filter((wert) => wert === "a").length,
    same: werte.filter((wert) => wert === "same").length,
    b: werte.filter((wert) => wert === "b").length,
    decided: werte.length,
  };
}

export function serializeState(state) {
  return `${JSON.stringify(state, null, 2)}\n`;
}

export function parseState(text, pfad = "decisions.json") {
  let gelesen;
  try {
    gelesen = JSON.parse(text);
  } catch (error) {
    throw new DecisionStoreError(`${pfad} ist beschädigt und nicht lesbar: ${error.message}`);
  }
  if (!gelesen || typeof gelesen !== "object" || Array.isArray(gelesen)) {
    throw new DecisionStoreError(`${pfad} ist beschädigt: kein Objekt.`);
  }
  if (gelesen.version !== DECISIONS_VERSION) {
    throw new DecisionStoreError(
      `${pfad} trägt Version ${String(gelesen.version)}; dieses Werkzeug schreibt Version ${DECISIONS_VERSION}.`,
    );
  }
  if (!gelesen.purposes || typeof gelesen.purposes !== "object") {
    throw new DecisionStoreError(`${pfad} ist beschädigt: „purposes“ fehlt.`);
  }
  return gelesen;
}

export function loadState(pfad, { seed, purposes, resume }) {
  if (!existsSync(pfad)) {
    if (resume) {
      throw new DecisionStoreError(
        `Fortsetzung angefordert, aber ${pfad} fehlt. Ohne Datei gibt es keine letzte Wahl; ein Neuanfang löscht sie nicht stillschweigend.`,
      );
    }
    return createState({ seed, purposes });
  }

  const state = parseState(readFileSync(pfad, "utf8"), pfad);
  if (!resume) {
    throw new DecisionStoreError(
      `${pfad} existiert bereits. Für die Fortsetzung ist --resume nötig; ein Neuanfang würde die bisherigen Wahlen überschreiben.`,
    );
  }
  if (state.seed !== seed) {
    throw new DecisionStoreError(
      `Die Saat der Datei (${String(state.seed)}) weicht von der aktuellen (${seed}) ab; die A/B-Zuordnung wäre nicht mehr dieselbe.`,
    );
  }
  for (const purpose of purposes) {
    if (!Object.hasOwn(state.purposes, purpose)) {
      throw new DecisionStoreError(`${pfad} kennt den Zweck „${purpose}“ nicht.`);
    }
  }
  return state;
}

export function saveState(pfad, state) {
  const zwischendatei = `${pfad}.tmp`;
  writeFileSync(zwischendatei, serializeState(state));
  renameSync(zwischendatei, pfad);
}
