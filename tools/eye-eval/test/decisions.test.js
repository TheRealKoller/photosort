import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  DecisionStoreError,
  countChoices,
  createState,
  recordChoice,
  saveState,
  serializeState,
  loadState,
} from "../src/decisions.js";

const ZWECKE = ["motivstaerken", "albumtauglichkeit"];

function mitVerzeichnis(rumpf) {
  const verzeichnis = mkdtempSync(join(tmpdir(), "eye-eval-decisions-"));
  try {
    return rumpf(verzeichnis, join(verzeichnis, "decisions.json"));
  } finally {
    rmSync(verzeichnis, { recursive: true, force: true });
  }
}

test("Zustand hin und zurück ist verlustfrei", () =>
  mitVerzeichnis((_, pfad) => {
    let state = createState({ seed: 7, purposes: ZWECKE });
    state = recordChoice(state, {
      purpose: "albumtauglichkeit",
      photoId: 42,
      choice: "a",
      index: 1,
    });
    saveState(pfad, state);

    const wieder = loadState(pfad, { seed: 7, purposes: ZWECKE, resume: true });
    assert.deepEqual(wieder, state);
    assert.equal(wieder.purposes.albumtauglichkeit.choices["42"], "a");
    assert.equal(wieder.purposes.albumtauglichkeit.index, 1);
    assert.equal(wieder.purposes.motivstaerken.index, 0);
  }));

test("die Fortsetzung beginnt an der letzten Wahl", () =>
  mitVerzeichnis((_, pfad) => {
    let state = createState({ seed: 7, purposes: ZWECKE });
    for (let index = 0; index < 37; index += 1) {
      state = recordChoice(state, {
        purpose: "albumtauglichkeit",
        photoId: 1000 + index,
        choice: index % 3 === 0 ? "same" : "b",
        index: index + 1,
      });
    }
    saveState(pfad, state);

    const wieder = loadState(pfad, { seed: 7, purposes: ZWECKE, resume: true });
    assert.equal(wieder.purposes.albumtauglichkeit.index, 37);
    assert.equal(Object.keys(wieder.purposes.albumtauglichkeit.choices).length, 37);
  }));

test("eine fehlende Datei bei Fortsetzung bricht statt still neu zu beginnen", () =>
  mitVerzeichnis((_, pfad) => {
    assert.throws(
      () => loadState(pfad, { seed: 7, purposes: ZWECKE, resume: true }),
      (error) => {
        assert.ok(error instanceof DecisionStoreError);
        assert.match(error.message, /Fortsetzung/);
        assert.match(error.message, /decisions\.json/);
        return true;
      },
    );
  }));

test("eine beschädigte Datei bricht mit Meldung ab", () =>
  mitVerzeichnis((_, pfad) => {
    writeFileSync(pfad, '{"version": 1, "purposes": ');
    assert.throws(
      () => loadState(pfad, { seed: 7, purposes: ZWECKE, resume: false }),
      /beschädigt|nicht lesbar/,
    );
    writeFileSync(pfad, JSON.stringify({ version: 99 }));
    assert.throws(
      () => loadState(pfad, { seed: 7, purposes: ZWECKE, resume: false }),
      /Version/,
    );
  }));

test("eine vorhandene Datei ohne --resume wird nicht stillschweigend überschrieben", () =>
  mitVerzeichnis((_, pfad) => {
    saveState(pfad, createState({ seed: 7, purposes: ZWECKE }));
    assert.throws(
      () => loadState(pfad, { seed: 7, purposes: ZWECKE, resume: false }),
      /Fortsetzung|resume/i,
    );
  }));

test("eine abweichende Saat bricht die Fortsetzung ab", () =>
  mitVerzeichnis((_, pfad) => {
    saveState(pfad, createState({ seed: 7, purposes: ZWECKE }));
    assert.throws(
      () => loadState(pfad, { seed: 8, purposes: ZWECKE, resume: true }),
      /Saat/,
    );
  }));

test("eine unbekannte Wahl oder ein unbekannter Zweck wird abgewiesen", () => {
  const state = createState({ seed: 7, purposes: ZWECKE });
  assert.throws(
    () => recordChoice(state, { purpose: "feinlabels", photoId: 1, choice: "a", index: 1 }),
    /Zweck/,
  );
  assert.throws(
    () => recordChoice(state, { purpose: "feinlabels", photoId: 1, choice: "x", index: 1 }),
    /Zweck/,
  );
  assert.throws(
    () => recordChoice(state, { purpose: "motivstaerken", photoId: 1, choice: "x", index: 1 }),
    /Wahl/,
  );
});

test("eine Wahl ändert den Zustand nicht an Ort und Stelle", () => {
  const vorher = createState({ seed: 7, purposes: ZWECKE });
  const kopie = JSON.parse(JSON.stringify(vorher));
  const nachher = recordChoice(vorher, {
    purpose: "motivstaerken",
    photoId: 5,
    choice: "same",
    index: 1,
  });

  assert.deepEqual(vorher, kopie);
  assert.equal(nachher.purposes.motivstaerken.choices["5"], "same");
  assert.equal(nachher.purposes.motivstaerken.index, 1);
});

test("der Index läuft nur vorwärts", () => {
  let state = createState({ seed: 7, purposes: ZWECKE });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 1, choice: "a", index: 3 });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 2, choice: "b", index: 1 });
  assert.equal(state.purposes.motivstaerken.index, 3);
});

test("Zählungen je Zweck kommen aus den Wahlen", () => {
  let state = createState({ seed: 7, purposes: ZWECKE });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 1, choice: "a", index: 1 });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 2, choice: "a", index: 2 });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 3, choice: "same", index: 3 });
  state = recordChoice(state, { purpose: "motivstaerken", photoId: 4, choice: "b", index: 4 });

  assert.deepEqual(countChoices(state, "motivstaerken"), {
    a: 2,
    same: 1,
    b: 1,
    decided: 4,
  });
  assert.deepEqual(countChoices(state, "albumtauglichkeit"), {
    a: 0,
    same: 0,
    b: 0,
    decided: 0,
  });
});

test("das Schreiben ist atomar und hinterlässt keine Zwischendatei", () =>
  mitVerzeichnis((verzeichnis, pfad) => {
    const state = recordChoice(createState({ seed: 7, purposes: ZWECKE }), {
      purpose: "albumtauglichkeit",
      photoId: 9,
      choice: "b",
      index: 1,
    });
    saveState(pfad, state);

    assert.deepEqual(readdirSync(verzeichnis), ["decisions.json"]);
    assert.deepEqual(JSON.parse(readFileSync(pfad, "utf8")), JSON.parse(serializeState(state)));
  }));

test("die Serialisierung ist stabil", () => {
  const state = createState({ seed: 7, purposes: ZWECKE });
  assert.equal(serializeState(state), serializeState(JSON.parse(serializeState(state))));
  assert.ok(serializeState(state).endsWith("\n"));
});
