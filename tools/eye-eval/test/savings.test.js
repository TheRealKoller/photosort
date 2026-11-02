import assert from "node:assert/strict";
import { test } from "node:test";

import { computeSavings, isReplaced } from "../src/savings.js";

const VIER = ["motivstaerken", "ausschluss", "albumtauglichkeit", "feinlabels"];

function urteil(better, same, worse, skipped = 0) {
  return { better, same, worse, skipped };
}

function voll(better = 20, same = 60, worse = 20) {
  return Object.fromEntries(VIER.map((zweck) => [zweck, urteil(better, same, worse)]));
}

test("ein Zweck gilt als ersetzt, wenn „gleich oder besser“ die Mehrheit hat", () => {
  assert.equal(isReplaced(urteil(10, 40, 10)).replaced, true);
  assert.equal(isReplaced(urteil(10, 40, 55)).replaced, false);
  assert.equal(isReplaced(urteil(0, 40, 40)).replaced, false, "Gleichstand ersetzt nicht");
  assert.equal(isReplaced(urteil(0, 0, 0, 12)).replaced, false, "nichts entschieden, nichts ersetzt");
});

test("vier ersetzte Zwecke sparen einen Kategorie-Aufruf je Foto mit Cloud-Aufruf", () => {
  const ergebnis = computeSavings({
    categories: { photosWithCall: 240, purposes: voll() },
    landmark: { candidates: 30, verdicts: urteil(0, 0, 0, 30) },
  });

  assert.equal(ergebnis.categoryCallSaved, true);
  assert.equal(ergebnis.categoryCallsSaved, 240);
  assert.equal(ergebnis.landmarkCallSaved, false);
  assert.equal(ergebnis.landmarkCallsSaved, 0);
  assert.equal(ergebnis.totalCallsSaved, 240);
});

test("drei von vier ersetzten Zwecken sparen keinen Aufruf", () => {
  const zwecke = voll();
  zwecke.feinlabels = urteil(2, 8, 30);
  const ergebnis = computeSavings({
    categories: { photosWithCall: 240, purposes: zwecke },
    landmark: { candidates: 30, verdicts: urteil(0, 0, 30) },
  });

  assert.equal(ergebnis.categoryCallSaved, false);
  assert.equal(ergebnis.categoryCallsSaved, 0);
  assert.equal(ergebnis.replacedCategoryPurposes, 3);
  assert.match(ergebnis.note, /Ausgabe-Tokens/);
});

test("der Landmark-Aufruf fällt unabhängig von den vier Zwecken weg", () => {
  const zwecke = voll();
  for (const zweck of VIER) zwecke[zweck] = urteil(1, 2, 40);
  const ergebnis = computeSavings({
    categories: { photosWithCall: 240, purposes: zwecke },
    landmark: { candidates: 30, verdicts: urteil(0, 20, 2) },
  });

  assert.equal(ergebnis.categoryCallSaved, false);
  assert.equal(ergebnis.landmarkCallSaved, true);
  assert.equal(ergebnis.landmarkCallsSaved, 30);
  assert.equal(ergebnis.totalCallsSaved, 30);
});

test("Fotos ohne Cloud-Aufruf zählen null", () => {
  const ergebnis = computeSavings({
    categories: { photosWithCall: 120, photosWithoutCall: 880, purposes: voll() },
    landmark: { candidates: 0, verdicts: urteil(0, 0, 0, 0) },
  });

  assert.equal(ergebnis.categoryCallsSaved, 120);
  assert.equal(ergebnis.photosWithoutCall, 880);
  assert.equal(ergebnis.totalCallsSaved, 120);
});

test("fehlende Zwecke zählen nicht als ersetzt", () => {
  const ergebnis = computeSavings({
    categories: { photosWithCall: 100, purposes: { motivstaerken: urteil(5, 90, 5) } },
    landmark: { candidates: 10, verdicts: urteil(0, 0, 0, 10) },
  });

  assert.equal(ergebnis.categoryCallSaved, false);
  assert.equal(ergebnis.replacedCategoryPurposes, 1);
  assert.equal(ergebnis.missingPurposes.length, 3);
});

test("Übersprungene Fotos senken weder Wahl noch Ersparnis", () => {
  const zwecke = voll(10, 10, 10);
  zwecke.ausschluss = urteil(1, 2, 3, 94);
  const ergebnis = computeSavings({
    categories: { photosWithCall: 100, purposes: zwecke },
    landmark: { candidates: 0, verdicts: urteil(0, 0, 0, 0) },
  });

  assert.equal(ergebnis.purposes.ausschluss.decided, 6);
  assert.equal(ergebnis.purposes.ausschluss.replaced, false);
  assert.equal(ergebnis.replacedCategoryPurposes, 3);
});

test("eine einzelne Stimme ersetzt nichts, solange die Hälfte der Paare nicht entschieden ist", () => {
  const duenn = isReplaced({ better: 1, same: 0, worse: 0, skipped: 2, total: 3 });
  assert.equal(duenn.replaced, false);
  assert.match(duenn.reason, /zu wenige Paare entschieden/);
  assert.equal(duenn.total, 3);
  assert.equal(duenn.decided, 1);
});

test("genau die Hälfte entschieden genügt, ein Paar darunter nicht", () => {
  assert.equal(isReplaced({ better: 2, same: 0, worse: 0, skipped: 0, total: 3 }).replaced, true);
  assert.equal(isReplaced({ better: 2, same: 0, worse: 0, skipped: 2, total: 4 }).replaced, true);
  assert.equal(isReplaced({ better: 1, same: 0, worse: 0, skipped: 3, total: 4 }).replaced, false);
});

test("ohne total in den Zählungen wird es aus den Werten gebildet", () => {
  const ausWerten = isReplaced({ better: 1, same: 0, worse: 0, skipped: 2 });
  assert.equal(ausWerten.total, 3);
  assert.equal(ausWerten.replaced, false);
});

test("die Ersparnis nennt zu dünn entschiedene Zwecke statt „Teilersatz“", () => {
  const duenn = voll(1, 0, 0);
  for (const zweck of VIER) duenn[zweck] = { better: 1, same: 0, worse: 0, skipped: 2, total: 3 };
  const ergebnis = computeSavings({
    categories: { photosWithCall: 260, purposes: duenn },
    landmark: { candidates: 20, verdicts: { better: 1, same: 0, worse: 0, skipped: 2, total: 3 } },
  });

  assert.equal(ergebnis.categoryCallSaved, false);
  assert.equal(ergebnis.categoryCallsSaved, 0);
  assert.equal(ergebnis.landmarkCallSaved, false);
  assert.equal(ergebnis.landmarkCallsSaved, 0);
  assert.equal(ergebnis.totalCallsSaved, 0);
  assert.deepEqual(ergebnis.underdecidedPurposes.sort(), [...VIER, "sehenswuerdigkeit"].sort());
  assert.match(ergebnis.note, /zu wenige Entscheidungen/i);
  assert.equal(ergebnis.note.includes("Teilersatz"), false);
  assert.match(ergebnis.note, /ausschluss/);
});

test("der Landmark-Zweck wird bei zu wenigen Entscheidungen ebenso benannt", () => {
  const ergebnis = computeSavings({
    categories: { photosWithCall: 100, purposes: voll() },
    landmark: { candidates: 20, verdicts: { better: 1, same: 0, worse: 0, skipped: 2, total: 3 } },
  });

  assert.equal(ergebnis.landmark.replaced, false);
  assert.equal(ergebnis.landmarkCallSaved, false);
  assert.deepEqual(ergebnis.underdecidedPurposes, ["sehenswuerdigkeit"]);
  assert.match(ergebnis.note, /sehenswuerdigkeit/);
});
