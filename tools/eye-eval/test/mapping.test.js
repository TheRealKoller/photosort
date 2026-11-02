import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EYE_PURPOSE_MAPPING,
  EYE_PURPOSE_MAPPING_HASH,
  MappingError,
  assertMappingHash,
  deepFreeze,
  mappingHash,
} from "../src/mapping.js";
import { MOTIF_KEYS } from "../src/motifs.js";

test("die Tabelle deckt genau die fünf Zwecke", () => {
  assert.deepEqual(Object.keys(EYE_PURPOSE_MAPPING.purposes).sort(), [
    "albumtauglichkeit",
    "ausschluss",
    "feinlabels",
    "motivstaerken",
    "sehenswuerdigkeit",
  ]);
  for (const zweck of Object.values(EYE_PURPOSE_MAPPING.purposes)) {
    assert.equal(typeof zweck.label, "string");
    assert.ok(zweck.label.length > 0);
    assert.ok(zweck.signals.length > 0);
    assert.ok(zweck.rule.length > 0);
  }
});

test("die Motivstärken nennen jedes der acht Motive mit seinen Eye-Signalen", () => {
  const motive = EYE_PURPOSE_MAPPING.purposes.motivstaerken.motifs;
  assert.deepEqual(Object.keys(motive).sort(), [...MOTIF_KEYS].sort());

  assert.ok(motive.menschen.faces, "menschen braucht faces_detect");
  assert.ok(motive.tiere.pets, "tiere braucht die Tiererkennung");
  assert.deepEqual(motive.aktivitaet.shot.length > 0, true);
  assert.deepEqual(motive.detail_stimmung.shot.length > 0, true);
  for (const key of ["landschaft", "stadt_strasse", "bauwerk_sehenswuerdigkeit", "essen_trinken"]) {
    assert.ok(motive[key].tags.length > 0, `${key} braucht Tags`);
  }
});

test("der Ausschluss nennt Dokument- und Screenshot-Typen", () => {
  const typen = EYE_PURPOSE_MAPPING.purposes.ausschluss.excludedTypes;
  for (const typ of ["document", "screenshot", "receipt"]) {
    assert.ok(typen.includes(typ), typ);
  }
});

test("die Albumtauglichkeit nennt Note, Behaltenswert, Schärfe und die beiden Mängel", () => {
  const album = EYE_PURPOSE_MAPPING.purposes.albumtauglichkeit;
  const signale = album.signals.join(" ");
  for (const signal of ["aesthetic", "keeper", "reject", "sharpness", "eyes_open", "blink", "occlusion"]) {
    assert.ok(signale.includes(signal), signal);
  }
  assert.deepEqual(album.namedFlaws, ["geschlossene Augen", "verdeckte Gesichter"]);
  assert.equal(album.levels.length, 5);
});

test("die Feinlabels werden ausdrücklich nicht automatisch verglichen", () => {
  const fein = EYE_PURPOSE_MAPPING.purposes.feinlabels;
  assert.equal(fein.automaticMatch, false);
  assert.ok(fein.signals.includes("tags"));
});

test("für die Sehenswürdigkeit steht das erwartete Urteil fest", () => {
  const landmark = EYE_PURPOSE_MAPPING.purposes.sehenswuerdigkeit;
  assert.equal(landmark.expectedVerdict, "schlechter / nicht geeignet");
  assert.ok(landmark.tags.length > 0);
});

test("die Tabelle ist tief eingefroren", () => {
  assert.equal(Object.isFrozen(EYE_PURPOSE_MAPPING), true);
  assert.equal(Object.isFrozen(EYE_PURPOSE_MAPPING.purposes), true);
  assert.equal(Object.isFrozen(EYE_PURPOSE_MAPPING.purposes.albumtauglichkeit), true);
  assert.equal(Object.isFrozen(EYE_PURPOSE_MAPPING.purposes.albumtauglichkeit.namedFlaws), true);
  assert.equal(Object.isFrozen(EYE_PURPOSE_MAPPING.purposes.motivstaerken.motifs.menschen), true);

  assert.throws(() => {
    EYE_PURPOSE_MAPPING.purposes.ausschluss.excludedTypes.push("neu");
  }, TypeError);
  assert.throws(() => {
    EYE_PURPOSE_MAPPING.purposes.motivstaerken.motifs.menschen.faces = null;
  }, TypeError);
});

test("deepFreeze friert auch verschachtelte Arrays ein", () => {
  const friert = deepFreeze({ a: [{ b: 1 }] });
  assert.equal(Object.isFrozen(friert.a), true);
  assert.equal(Object.isFrozen(friert.a[0]), true);
});

test("der festgeschriebene Hash trifft den Inhalt der Tabelle", () => {
  assert.match(EYE_PURPOSE_MAPPING_HASH, /^sha256:[0-9a-f]{64}$/);
  assert.equal(mappingHash(), EYE_PURPOSE_MAPPING_HASH);
});

test("eine geänderte Tabelle ergibt einen anderen Hash", () => {
  const kopie = JSON.parse(JSON.stringify(EYE_PURPOSE_MAPPING));
  kopie.thresholds.tagConfidence = 0.6;
  assert.notEqual(mappingHash(kopie), EYE_PURPOSE_MAPPING_HASH);
});

test("der Hash ist unabhängig von der Schlüsselreihenfolge", () => {
  const umgedreht = Object.fromEntries(
    Object.entries(JSON.parse(JSON.stringify(EYE_PURPOSE_MAPPING))).reverse(),
  );
  assert.equal(mappingHash(umgedreht), EYE_PURPOSE_MAPPING_HASH);
});

test("ein abweichender gespeicherter Hash bricht vor dem ersten SDK-Aufruf ab", () => {
  assert.equal(assertMappingHash(undefined), true, "ein erster Lauf hat keinen Vorlauf");
  assert.equal(assertMappingHash(null), true);
  assert.equal(assertMappingHash(EYE_PURPOSE_MAPPING_HASH), true);
  assert.throws(
    () => assertMappingHash("sha256:0000000000000000000000000000000000000000000000000000000000000000"),
    (error) => {
      assert.ok(error instanceof MappingError);
      assert.match(error.message, /Zuordnungstabelle/);
      return true;
    },
  );
});
