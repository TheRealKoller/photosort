import assert from "node:assert/strict";
import { test } from "node:test";

import { buildItems, describeCloud } from "../src/compare.js";
import { assembleBaseline } from "../src/baseline.js";

const PHOTOS = [11, 12, 13];

function stichprobe() {
  return {
    seed: 7,
    projects: [
      {
        projectId: 1,
        kind: "familie",
        photos: PHOTOS.map((photoId) => ({
          photoId,
          projectId: 1,
          etag: `etag-${photoId}`,
          cacheKey: `key-${photoId}`,
        })),
      },
    ],
  };
}

function basis(photoIds = PHOTOS) {
  return assembleBaseline({
    photoIds,
    motifStrengths: photoIds.flatMap((photoId) =>
      ["menschen", "landschaft", "bauwerk_sehenswuerdigkeit", "stadt_strasse", "tiere", "essen_trinken", "aktivitaet", "detail_stimmung"].map(
        (motifKey) => ({
          photoId,
          motifKey,
          strength: motifKey === "landschaft" ? 0.8 : 0.2,
        }),
      ),
    ),
    assessments: photoIds.map((photoId) => ({ photoId, excludedDocument: photoId === 12 })),
    albumSuitability: photoIds.map((photoId) => ({
      photoId,
      level: 3,
      reason: photoId === 13 ? "geschlossene Augen" : null,
    })),
    fineLabels: photoIds.map((photoId) => ({
      photoId,
      rawLabel: photoId === 11 ? "Strand" : "Berg",
      canonicalKey: "ort",
    })),
    landmarks: [{ photoId: 13, name: "Wahrzeichen", canonicalName: "wahrzeichen", confidence: 0.9 }],
  });
}

const ANALYSEN = {
  11: {
    model: "eye@v1.0.0",
    kind: "photo",
    confidences: { beach: 0.9, sharp: 0.9 },
    scores: { aesthetic: 0.7, keeper: 0.6, cover: 0.5 },
    faces: [],
    pets: [],
    details: { layout: { shot: { wide: 0.8 } } },
  },
  13: {
    model: "eye@v1.0.0",
    kind: "photo",
    confidences: { castle: 0.8 },
    scores: { aesthetic: 0.45, keeper: 0.5, cover: 0.4 },
    faces: [],
    pets: [],
    details: { layout: { shot: { medium: 0.7 } } },
  },
};

test("je Zweck entsteht ein Paar aus Basis und Analyse", () => {
  const { items, missing } = buildItems({
    sample: stichprobe(),
    baseline: basis(),
    analyses: ANALYSEN,
  });

  assert.deepEqual(Object.keys(items).sort(), [
    "albumtauglichkeit",
    "ausschluss",
    "feinlabels",
    "motivstaerken",
    "sehenswuerdigkeit",
  ]);
  for (const [zweck, liste] of Object.entries(items)) {
    assert.equal(liste.length, 2, zweck);
    for (const eintrag of liste) {
      assert.equal(eintrag.image, `images/${eintrag.photoId}.jpg`);
      assert.ok(eintrag.first.verdict.length > 0, zweck);
      assert.ok(eintrag.first.reason.length > 0, zweck);
      assert.ok(eintrag.second.verdict.length > 0, zweck);
      assert.ok(eintrag.second.reason.length > 0, zweck);
    }
  }
  assert.equal(missing.withoutAnalysis, 1);
});

test("fehlende Basis schließt das Foto je Zweck aus und wird gezählt", () => {
  const ohneFeinlabel = assembleBaseline({
    photoIds: [11, 12],
    assessments: [
      { photoId: 11, excludedDocument: false },
      { photoId: 12, excludedDocument: false },
    ],
    albumSuitability: [
      { photoId: 11, level: 3, reason: null },
      { photoId: 12, level: 3, reason: null },
    ],
    fineLabels: [{ photoId: 11, rawLabel: "Strand", canonicalKey: "ort" }],
  });

  const { items, missing } = buildItems({
    sample: stichprobe(),
    baseline: ohneFeinlabel,
    analyses: ANALYSEN,
  });

  assert.equal(items.feinlabels.length, 1);
  assert.equal(missing.withoutBaseline.feinlabels, 2);
  assert.equal(missing.withoutBaseline.ausschluss, 1);
});

test("die Texte nennen die Quelle nicht", () => {
  const { items } = buildItems({ sample: stichprobe(), baseline: basis(), analyses: ANALYSEN });
  for (const liste of Object.values(items)) {
    for (const eintrag of liste) {
      const text = [eintrag.first, eintrag.second]
        .map((seite) => `${seite.verdict} ${seite.reason}`)
        .join(" ")
        .toLowerCase();
      for (const verraeter of ["eye", "cloud", "modell", "anbieter", "konfidenz"]) {
        assert.equal(text.includes(verraeter), false, `${verraeter}: ${text}`);
      }
    }
  }
});

test("die Basis-Texte folgen den Tabellenwerten", () => {
  const basal = basis();

  const motive = describeCloud(basal.purposes.motivstaerken.photos[0], "motivstaerken");
  assert.match(motive.verdict, /Landschaft/);
  assert.equal(motive.verdict.includes("Tiere"), false);

  const ausschluss = describeCloud(basal.purposes.ausschluss.photos[1], "ausschluss");
  assert.match(ausschluss.verdict, /Ausschluss: ja/);

  const album = describeCloud(basal.purposes.albumtauglichkeit.photos[2], "albumtauglichkeit");
  assert.match(album.verdict, /Stufe 3/);
  assert.match(album.reason, /geschlossene Augen/);

  const labels = describeCloud(basal.purposes.feinlabels.photos[0], "feinlabels");
  assert.match(labels.reason, /Strand/);

  const landmark = describeCloud(basal.purposes.sehenswuerdigkeit.photos[2], "sehenswuerdigkeit");
  assert.match(landmark.reason, /Wahrzeichen/);
  const ohneName = describeCloud(basal.purposes.sehenswuerdigkeit.photos[0], "sehenswuerdigkeit");
  assert.match(ohneName.verdict, /kein Name/i);
});

test("unvollständige Motivbasis wird benannt statt verschwiegen", () => {
  const unvollstaendig = assembleBaseline({
    photoIds: [11],
    motifStrengths: [{ photoId: 11, motifKey: "menschen", strength: 0.9 }],
  });
  const text = describeCloud(unvollstaendig.purposes.motivstaerken.photos[0], "motivstaerken");
  assert.match(text.reason, /unvollständig/i);
});

test("ohne Analyse gibt es kein Paar", () => {
  const { items } = buildItems({ sample: stichprobe(), baseline: basis(), analyses: {} });
  for (const liste of Object.values(items)) assert.equal(liste.length, 0);
});
