import assert from "node:assert/strict";
import { test } from "node:test";

import { VoteError, mapVotes } from "../src/votes.js";

test("A ist die linke Seite: bei Eye links bedeutet A „Eye besser“", () => {
  const ergebnis = mapVotes({
    choices: Object.fromEntries([11, 12, 13, 14].map((id) => [String(id), "a"])),
    assignments: [11, 12, 13, 14].map((photoId) => ({ photoId, left: "second" })),
  });
  assert.equal(ergebnis.better, 4);
  assert.equal(ergebnis.worse, 0);
  assert.equal(ergebnis.decided, 4);
});

test("gemischte Seiten mitteln sich nicht heraus", () => {
  const ergebnis = mapVotes({
    choices: { 11: "a", 12: "a", 13: "b", 14: "b" },
    assignments: [
      { photoId: 11, left: "first" },
      { photoId: 12, left: "second" },
      { photoId: 13, left: "first" },
      { photoId: 14, left: "second" },
    ],
  });
  assert.equal(ergebnis.better, 2, "12 (Eye links) und 13 (Eye rechts, B) sind Eye-besser");
  assert.equal(ergebnis.worse, 2);
});

test("gleich bleibt gleich, unabhängig von der Seite", () => {
  const ergebnis = mapVotes({
    choices: { 11: "same", 12: "same" },
    assignments: [
      { photoId: 11, left: "first" },
      { photoId: 12, left: "second" },
    ],
  });
  assert.deepEqual(ergebnis, { better: 0, same: 2, worse: 0, decided: 2 });
});

test("eine Stimme ohne A/B-Zuordnung bricht ab statt geraten zu werden", () => {
  assert.throws(
    () => mapVotes({ choices: { 11: "a" }, assignments: [{ photoId: 12, left: "first" }] }),
    (error) => {
      assert.ok(error instanceof VoteError);
      assert.match(error.message, /11/);
      assert.match(error.message, /ab-map\.json/);
      return true;
    },
  );
});
