import assert from "node:assert/strict";
import { test } from "node:test";

import { EYE_PURPOSE_MAPPING } from "../src/mapping.js";
import { describeEye, extractSignals, motifMatches } from "../src/signals.js";

function analyse(extra = {}) {
  return {
    model: "eye@v1.0.0",
    width: 2048,
    height: 1536,
    kind: "photo",
    confidences: {},
    scores: { aesthetic: 0.72, keeper: 0.6, cover: 0.4 },
    people: [],
    pets: [],
    faces: [],
    details: { layout: { shot: { medium: 0.8, wide: 0.2 } } },
    ...extra,
  };
}

function gesicht(eyesOpen, occlusion = {}, box = { x0: 0.2, y0: 0.2, x1: 0.5, y1: 0.6 }) {
  return {
    box,
    confidences: { eyes_open: eyesOpen, sharp: 0.9, ...occlusion },
  };
}

test("Signale werden aus der Analyse gezogen, ohne SDK-Objekt", () => {
  const signale = extractSignals(
    analyse({
      confidences: { beach: 0.81, mountain: 0.4 },
      faces: [gesicht(0.9), gesicht(0.2)],
      pets: [{ label: "dog", confidence: 0.9, box: { x0: 0, y0: 0, x1: 1, y1: 1 } }],
    }),
  );

  assert.equal(signale.kind, "photo");
  assert.equal(signale.tags.beach, 0.81);
  assert.equal(signale.faceCount, 2);
  assert.equal(signale.petCount, 1);
  assert.equal(signale.shot, "medium");
  assert.ok(signale.faceArea > 0.1);
  assert.equal(signale.scores.aesthetic, 0.72);
});

test("fehlende Teile sind null, nicht erfunden", () => {
  const signale = extractSignals({ model: "eye@v1.0.0", kind: null, confidences: {} });
  assert.equal(signale.kind, null);
  assert.equal(signale.shot, null);
  assert.equal(signale.scores.aesthetic, null);
  assert.equal(signale.faceCount, 0);
});

test("ein Motiv trifft über Tag, Gesicht, Tier oder Bildausschnitt", () => {
  const schwelle = EYE_PURPOSE_MAPPING.thresholds;

  assert.equal(motifMatches(extractSignals(analyse({ confidences: { beach: 0.6 } })), "landschaft", schwelle), true);
  assert.equal(motifMatches(extractSignals(analyse({ confidences: { beach: 0.3 } })), "landschaft", schwelle), false);

  const mitGesicht = extractSignals(analyse({ faces: [gesicht(0.9)] }));
  assert.equal(motifMatches(mitGesicht, "menschen", schwelle), true, "Gesicht über 2 % Fläche");

  const kleinesGesicht = extractSignals(
    analyse({ faces: [gesicht(0.9, {}, { x0: 0, y0: 0, x1: 0.05, y1: 0.05 })] }),
  );
  assert.equal(motifMatches(kleinesGesicht, "menschen", schwelle), false, "Gesicht zu klein");

  const mitTier = extractSignals(analyse({ pets: [{ label: "cat", confidence: 0.8 }] }));
  assert.equal(motifMatches(mitTier, "tiere", schwelle), true);

  const nah = extractSignals(
    analyse({ details: { layout: { shot: { close_up: 0.9, medium: 0.1 } } } }),
  );
  assert.equal(motifMatches(nah, "detail_stimmung", schwelle), true);
  assert.equal(motifMatches(nah, "aktivitaet", schwelle), false, "Aktivität braucht einen Spitzenmoment");
});

test("jedes Motiv lässt sich einzeln auslösen", () => {
  const schwelle = EYE_PURPOSE_MAPPING.thresholds;
  const faelle = {
    menschen: analyse({ confidences: { portrait: 0.8 } }),
    landschaft: analyse({ confidences: { mountain: 0.8 } }),
    bauwerk_sehenswuerdigkeit: analyse({ confidences: { castle: 0.8 } }),
    stadt_strasse: analyse({ confidences: { street: 0.8 } }),
    tiere: analyse({ confidences: { dog: 0.8 } }),
    essen_trinken: analyse({ confidences: { food: 0.8 } }),
    aktivitaet: analyse({
      details: { layout: { shot: { wide: 0.9 } } },
      confidences: { peak_moment: 0.8 },
    }),
    detail_stimmung: analyse({ confidences: { flower: 0.8 } }),
  };

  for (const [motiv, analyseWert] of Object.entries(faelle)) {
    assert.equal(motifMatches(extractSignals(analyseWert), motiv, schwelle), true, motiv);
  }
});

test("Motivtexte nennen die Quelle nicht", () => {
  const signale = extractSignals(analyse({ confidences: { beach: 0.9, mountain: 0.8 } }));
  const text = describeEye(signale, "motivstaerken");

  assert.match(text.verdict, /Landschaft/);
  assert.match(text.reason, /Ausschnitt/);
  for (const verraeter of ["eye", "cloud", "modell", "anbieter"]) {
    assert.equal(`${text.verdict} ${text.reason}`.toLowerCase().includes(verraeter), false, verraeter);
  }
});

test("der Ausschluss folgt dem erkannten Typ", () => {
  const dokument = describeEye(extractSignals(analyse({ kind: "document" })), "ausschluss");
  assert.match(dokument.verdict, /Ausschluss: ja/);

  const foto = describeEye(extractSignals(analyse({ kind: "photo" })), "ausschluss");
  assert.match(foto.verdict, /Ausschluss: nein/);
});

test("die Albumstufe kommt aus der Note, die Mängel aus den Gesichtern", () => {
  const gut = describeEye(
    extractSignals(
      analyse({ confidences: { sharp: 0.9 }, scores: { aesthetic: 0.85, keeper: 0.8, cover: 0.5 } }),
    ),
    "albumtauglichkeit",
  );
  assert.match(gut.verdict, /Stufe 5/);
  assert.match(gut.reason, /scharf/i);

  const blinzelnd = describeEye(
    extractSignals(
      analyse({
        faces: [gesicht(0.1)],
        scores: { aesthetic: 0.5, keeper: 0.5, cover: 0.5 },
      }),
    ),
    "albumtauglichkeit",
  );
  assert.match(blinzelnd.reason, /Geschlossene Augen/);

  const verdeckt = describeEye(
    extractSignals(
      analyse({
        faces: [gesicht(0.9, { hand_or_object_covering: 0.8 })],
        scores: { aesthetic: 0.5, keeper: 0.5, cover: 0.5 },
      }),
    ),
    "albumtauglichkeit",
  );
  assert.match(verdeckt.reason, /Verdecktes Gesicht/);
});

test("Feinlabels und Wahrzeichen nennen Szenen, keine Zahlen", () => {
  const fein = describeEye(
    extractSignals(analyse({ confidences: { beach: 0.9, mountain: 0.8, dog: 0.7 } })),
    "feinlabels",
  );
  assert.match(fein.verdict, /Szene/);
  assert.equal(/\d/.test(`${fein.verdict} ${fein.reason}`), false);

  const bauwerk = describeEye(
    extractSignals(analyse({ confidences: { castle: 0.9 } })),
    "sehenswuerdigkeit",
  );
  assert.match(bauwerk.verdict, /Bauwerk/);
  assert.match(bauwerk.reason, /Burg|Schloss|castle/i);
});

test("ohne Signale bleibt der Text ehrlich leer statt erfunden", () => {
  const leer = extractSignals({});
  for (const zweck of Object.keys(EYE_PURPOSE_MAPPING.purposes)) {
    const text = describeEye(leer, zweck);
    assert.ok(text.verdict.length > 0, zweck);
    assert.ok(text.reason.length > 0, zweck);
    assert.equal(/\d/.test(text.verdict), false, `${zweck}: ${text.verdict}`);
  }
});
