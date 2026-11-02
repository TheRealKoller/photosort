/**
 * Report-Prüfer (S6–S11): findet im Markdown, was nicht in ein öffentliches Repository gehört.
 *
 * Die Befunde tragen Art, Zeile und Spalte — und den Fundtext, damit Daniel die Stelle im lokalen
 * Arbeitsverzeichnis findet. Das Terminal bekommt nur Art/Zeile/Spalte (`formatFindings`), sonst
 * stünde der Projektname im Sitzungstranskript (S10).
 *
 * Was ein Prüfer nicht kann, steht als `manualChecks` daneben: Personennamen im Fließtext erkennt
 * nur, wer die Familie kennt.
 */
const MUSTER = [
  {
    kind: "bildeinbettung",
    regex: /!\[[^\]]*\]\([^)]*\)|<img\b|\bdata:image|\bbase64,/gi,
    hinweis: "Bild, Vorschau oder eingebettete Daten (S6).",
  },
  {
    kind: "pfad",
    regex: /(?<=^|[\s("'`=(])(?:[A-Za-z]:\\|(?:~|\.{1,2})?\/)[^\s)"'`]+/gm,
    hinweis: "Pfad im Text (S6/S11).",
  },
  {
    kind: "dateiendung",
    regex: /\.(?:jpe?g|png|heic|heif|webp|gif|tiff?|dng|cr2|cr3|nef|arw|raf|orf|rw2)\b/gi,
    hinweis: "Dateiendung eines Bildes (S6/S11).",
  },
  {
    kind: "install-id",
    regex: /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi,
    hinweis: "Install-ID oder Kennung (S3/S8).",
  },
  {
    kind: "aufnahmezeit",
    regex: /\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?\b/g,
    hinweis: "Aufnahmedatum mit Uhrzeit (S6).",
  },
  {
    kind: "koordinaten",
    regex: /\b-?\d{1,3}\.\d{4,},\s*-?\d{1,3}\.\d{4,}\b/g,
    hinweis: "Koordinaten (S6).",
  },
  {
    kind: "blinding",
    regex: /\bA\/B(?:-Zuordnung|-JSON|-Mapping|-Datei)?\b/g,
    hinweis: "A/B-Zuordnung gehört in den Arbeitsbereich, nicht in den Bericht (S8).",
  },
];

export const MANUAL_CHECKS = [
  "Personennamen im Fließtext: nur Rollen („Erwachsener“, „Kind“) — manuelle Prüfung (S7).",
  "Ortsnamen: nur Gattung („Wahrzeichen“, „Altstadt“) — manuelle Prüfung (S7).",
  "Kombination aus Ortstyp, Zeitraum und Projekt, die auf ein Reiseziel schließen lässt — manuelle Prüfung (S7).",
  "Urteilsqualität und tatsächliche Verschiedenart der Projekte — manuelle Prüfung.",
];

function zeileUndSpalte(text, index) {
  const vorher = text.slice(0, index);
  const line = vorher.split("\n").length;
  const column = index - vorher.lastIndexOf("\n");
  return { line, column };
}

function namensMuster(name) {
  const bereinigt = String(name).trim();
  if (bereinigt.length < 3) return null;
  return new RegExp(bereinigt.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
}

export function checkReport(markdown, { projectNames = [], landmarkNames = [] } = {}) {
  const text = String(markdown);
  const treffer = [];

  const suche = (kind, hinweis, regex) => {
    regex.lastIndex = 0;
    for (const match of text.matchAll(regex)) {
      const { line, column } = zeileUndSpalte(text, match.index);
      treffer.push({ kind, hinweis, line, column, excerpt: match[0] });
    }
  };

  for (const muster of MUSTER) suche(muster.kind, muster.hinweis, muster.regex);

  for (const [kind, namen] of [
    ["projektname", projectNames],
    ["landmarkname", landmarkNames],
  ]) {
    for (const name of namen) {
      const regex = namensMuster(name);
      if (regex) {
        suche(
          kind,
          kind === "projektname" ? "Projektname im Text (S7)." : "Orts- oder Landmarkname im Text (S7).",
          regex,
        );
      }
    }
  }

  // Ein Befund je Zeile und Art: zehn Treffer derselben Endung sind eine Stelle, nicht zehn.
  const gesehen = new Set();
  const findings = [];
  for (const befund of treffer.sort((links, rechts) => links.line - rechts.line || links.column - rechts.column)) {
    const schluessel = `${befund.kind}:${befund.line}`;
    if (gesehen.has(schluessel)) continue;
    gesehen.add(schluessel);
    findings.push(befund);
  }

  return {
    ok: findings.length === 0,
    findings,
    manualChecks: [...MANUAL_CHECKS],
    checkedCharacters: text.length,
  };
}

export function formatFindings(ergebnis) {
  const zeilen = ergebnis.findings.map(
    (befund) => `- ${befund.kind} in Zeile ${befund.line}, Spalte ${befund.column}: ${befund.hinweis}`,
  );
  const kopf =
    ergebnis.findings.length === 0
      ? "Report-Prüfer: keine Befunde."
      : `Report-Prüfer: ${ergebnis.findings.length} Befund(e) — vor dem Push umformulieren, nicht nachbessern.`;
  const manuell = ergebnis.manualChecks.map((text) => `- manuelle Prüfung: ${text}`);
  return [...[kopf], ...zeilen, "", "Offen:", ...manuell].join("\n");
}
