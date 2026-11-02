import assert from "node:assert/strict";
import { test } from "node:test";

import { checkReport, formatFindings } from "../src/report.js";

const SAUBER = `# Vergleichsergebnis

Eye 4.2.3 lief lokal auf dem Heimserver. Von 240 Fotos aus zwei Projekten wurden 120 je Projekt
verglichen; 96 Fotos fielen wegen abweichendem Etag und Cache-Datei aus der Stichprobe.

## Motivstärken

In 72 von 120 Fällen urteilte ich „gleich oder besser“, in 38 „schlechter“. Auffällig: Nahaufnahmen
von Speisen wurden häufiger als „Detail“ statt als „Essen“ erkannt.

## Ersparnis

Ein Kategorie-Aufruf fällt weg, der Aufruf für Wahrzeichen bleibt, solange das Urteil dort
„schlechter“ lautet.
`;

test("ein sauberer Bericht hat keinen Befund, aber offene manuelle Prüfungen", () => {
  const ergebnis = checkReport(SAUBER, { projectNames: [], landmarkNames: [] });

  assert.deepEqual(ergebnis.findings, []);
  assert.equal(ergebnis.ok, true);
  assert.ok(ergebnis.manualChecks.some((text) => /Personennamen/.test(text)));
});

test("ein Pfad ist ein Befund", () => {
  const ergebnis = checkReport(`${SAUBER}\nDie Datei lag unter /home/daniel/fotos/urlaub.`, {});
  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "pfad"));
  assert.ok(ergebnis.findings.every((befund) => Number.isInteger(befund.line)));
});

test("eine Dateiendung ist ein Befund", () => {
  const ergebnis = checkReport(`${SAUBER}\nUrsprünglich hieß das Bild IMG_4711.HEIC.`, {});
  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "dateiendung"));
});

test("Projekt- und Landmarknamen sind Befunde", () => {
  const ergebnis = checkReport(`${SAUBER}\nProjekt Gardasee 2024, Motiv Castello Scaligero.`, {
    projectNames: ["Gardasee 2024"],
    landmarkNames: ["Castello Scaligero"],
  });

  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "projektname"));
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "landmarkname"));
});

test("Namen werden unabhängig von der Schreibweise gefunden", () => {
  const ergebnis = checkReport(`${SAUBER}\nGARDASEE 2024 war der Schauplatz.`, {
    projectNames: ["gardasee 2024"],
  });
  assert.equal(ergebnis.ok, false);
  assert.equal(ergebnis.findings.filter((befund) => befund.kind === "projektname").length, 1);
});

test("Bilddaten und Einbettungen sind Befunde", () => {
  const mitBild = `${SAUBER}\n![Vorschau](bild.png)\n<img src="x">\nEin Blob als data:image/png;base64,AAAA.`;
  const ergebnis = checkReport(mitBild, {});

  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "bildeinbettung"));
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "dateiendung"));
});

test("Install-ID und Aufnahmezeitpunkt sind Befunde", () => {
  const ergebnis = checkReport(
    `${SAUBER}\nInstall-ID 8f14e45f-ceea-467a-9e4b-1c2d3e4f5a6b, aufgenommen 2024-07-14T18:22:31.`,
    {},
  );

  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "install-id"));
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "aufnahmezeit"));
});

test("die A/B-Zuordnung gehört nicht in den Bericht", () => {
  const ergebnis = checkReport(`${SAUBER}\nDie A/B-Zuordnung liegt im Arbeitsverzeichnis.`, {});
  assert.equal(ergebnis.ok, false);
  assert.ok(ergebnis.findings.some((befund) => befund.kind === "blinding"));
});

test("ein Befund je Zeile und Art, mit Spalte", () => {
  const ergebnis = checkReport(`${SAUBER}\na.jpg und b.png`, {});
  const endungen = ergebnis.findings.filter((befund) => befund.kind === "dateiendung");
  assert.equal(endungen.length, 1);
  assert.ok(endungen[0].column > 0);
});

test("die Ausgabe für das Terminal nennt Art, Zeile und Spalte, aber keinen Fundtext", () => {
  const ergebnis = checkReport(`${SAUBER}\nProjekt Gardasee 2024.`, {
    projectNames: ["Gardasee 2024"],
  });
  const text = formatFindings(ergebnis);

  assert.match(text, /projektname/);
  assert.match(text, /Zeile \d+/);
  assert.equal(text.includes("Gardasee"), false);
  assert.match(text, /manuelle Prüfung/);
});
