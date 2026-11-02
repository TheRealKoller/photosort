import assert from "node:assert/strict";
import { test } from "node:test";

import { countCalls } from "../src/calls.js";

function lauf(projekte) {
  return { projects: projekte };
}

test("api_calls zählt, nicht die Fotozahl", () => {
  const ergebnis = countCalls(
    lauf([{ category: { apiCalls: 240, photosProcessed: 240 } }, { category: { apiCalls: 20, photosProcessed: 3 } }]),
  );
  assert.equal(ergebnis.category, 260);
  assert.equal(ergebnis.categorySource, "apiCalls");
});

test("photos_processed ist nur der Rückfall, wenn api_calls fehlt", () => {
  const ergebnis = countCalls(lauf([{ category: { photosProcessed: 240 } }, { category: { apiCalls: 20 } }]));
  assert.equal(ergebnis.category, 260);
  assert.equal(ergebnis.categorySource, "photosProcessed");
  assert.equal(ergebnis.fallbackProjects, 1);
});

test("Landmark-Aufrufe summieren sich getrennt", () => {
  const ergebnis = countCalls(lauf([{ landmark: { apiCalls: 12 } }, { landmark: { apiCalls: 8 } }, {}]));
  assert.equal(ergebnis.landmark, 20);
});

test("fehlende Läufe ergeben null, ohne zu werfen", () => {
  assert.deepEqual(countCalls(undefined), {
    category: 0,
    landmark: 0,
    categorySource: "apiCalls",
    fallbackProjects: 0,
  });
  assert.equal(countCalls(lauf([{}])).category, 0);
});
