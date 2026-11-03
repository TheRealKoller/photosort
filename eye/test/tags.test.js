import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { Tag } from "@desert-ant-labs/eye";

import { PINS_PATH } from "../src/pins.js";

/**
 * Der Abgleich, der den stillen Nullen vorbeugt: jeder Tag, aus dem das Backend Motivstärken
 * bildet, muss im Vokabular des gepinnten Modells vorkommen.
 *
 * Autoritativ ist `tags.js` (erzeugt aus `eye_meta.json`, snake_case wie die SDK-Antwort) - NICHT
 * `eye_meta.json::labels.scenes`: das führt Anzeigenamen ("Human face") und hätte die frühere
 * Tabelle falsch bestätigt bzw. verworfen.
 */
const SDK_TAGS = new Set(Object.values(Tag));

test("pins.json nennt Zuordnungs-Tags", async () => {
  const pins = JSON.parse(await readFile(PINS_PATH, "utf8"));

  assert.ok(Array.isArray(pins.mappingTags));
  assert.ok(pins.mappingTags.length > 0);
});

test("jeder Zuordnungs-Tag existiert im SDK-Vokabular", async () => {
  const pins = JSON.parse(await readFile(PINS_PATH, "utf8"));

  const unbekannt = pins.mappingTags.filter((tag) => !SDK_TAGS.has(tag));

  assert.deepEqual(unbekannt, [], `Unbekannte Tags: ${unbekannt.join(", ")}`);
});

test("kein Zuordnungs-Tag steht doppelt in den Pins", async () => {
  const pins = JSON.parse(await readFile(PINS_PATH, "utf8"));

  assert.equal(new Set(pins.mappingTags).size, pins.mappingTags.length);
});

test("die Pins nennen die gepinnte Modellrevision", async () => {
  const pins = JSON.parse(await readFile(PINS_PATH, "utf8"));

  assert.equal(pins.revision, "v1.0.0");
});

test("das SDK-Vokabular ist nicht leer", () => {
  assert.ok(SDK_TAGS.size > 500);
});
