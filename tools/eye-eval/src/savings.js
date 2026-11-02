/**
 * Ersparnis-Arithmetik aus den Paarurteilen. Die Regel ist absichtlich grob und vor dem Lauf
 * festgelegt: „gleichwertig genügt“ heißt „gleich oder besser“ muss die Mehrheit der entschiedenen
 * Fotos stellen, und es muss mindestens die Hälfte der Paare des Zwecks entschieden sein — eine
 * einzelne Stimme bei überwiegend übersprungenen Paaren ersetzt nichts. Ein Teilersatz spart keinen
 * Aufruf, nur Ausgabe-Tokens — deshalb zählt der Kategorie-Aufruf erst bei 4/4, der Landmark-Aufruf
 * unabhängig davon.
 */
export const CATEGORY_PURPOSES = [
  "motivstaerken",
  "ausschluss",
  "albumtauglichkeit",
  "feinlabels",
];

export const LANDMARK_PURPOSE = "sehenswuerdigkeit";

function zahl(wert) {
  return Number.isFinite(wert) ? wert : 0;
}

export function isReplaced(verdicts = {}) {
  const better = zahl(verdicts.better);
  const same = zahl(verdicts.same);
  const worse = zahl(verdicts.worse);
  const skipped = zahl(verdicts.skipped);
  const total = Number.isFinite(verdicts.total) ? zahl(verdicts.total) : better + same + worse + skipped;
  const decided = better + same + worse;
  const genugEntschieden = total > 0 && decided * 2 >= total;
  const mehrheit = decided > 0 && better + same > worse;
  const replaced = genugEntschieden && mehrheit;

  return {
    better,
    same,
    worse,
    skipped,
    total,
    decided,
    replaced,
    underdecided: total > 0 && !genugEntschieden,
    reason: replaced
      ? "„gleich oder besser“ hat die Mehrheit der entschiedenen Fotos."
      : !genugEntschieden
        ? total > 0
          ? `Es sind zu wenige Paare entschieden (${decided} von ${total}); ersetzt wird erst ab der Hälfte.`
          : "Keine Entscheidung; ohne Urteil wird nichts ersetzt."
        : "„schlechter“ hat mindestens so viele Fotos wie „gleich oder besser“.",
  };
}

export function computeSavings({ categories, landmark }) {
  const zwecke = {};
  for (const purpose of CATEGORY_PURPOSES) {
    zwecke[purpose] = isReplaced(categories?.purposes?.[purpose]);
  }
  const landmarkUrteil = isReplaced(landmark?.verdicts);

  const replacedCategoryPurposes = Object.values(zwecke).filter((wert) => wert.replaced).length;
  const missingPurposes = CATEGORY_PURPOSES.filter(
    (purpose) => !categories?.purposes || !Object.hasOwn(categories.purposes, purpose),
  );
  const underdecidedPurposes = [
    ...CATEGORY_PURPOSES.filter((purpose) => zwecke[purpose].underdecided),
    ...(landmarkUrteil.underdecided ? [LANDMARK_PURPOSE] : []),
  ];
  const photosWithCall = zahl(categories?.photosWithCall);
  const photosWithoutCall = zahl(categories?.photosWithoutCall);
  const candidates = zahl(landmark?.candidates);

  const categoryCallSaved = replacedCategoryPurposes === CATEGORY_PURPOSES.length;
  const categoryCallsSaved = categoryCallSaved ? photosWithCall : 0;
  const landmarkCallSaved = landmarkUrteil.replaced;
  const landmarkCallsSaved = landmarkCallSaved ? candidates : 0;

  const noteTeile = [];
  const duenneKategorien = CATEGORY_PURPOSES.filter((purpose) => zwecke[purpose].underdecided);
  if (duenneKategorien.length > 0) {
    noteTeile.push(
      `Zu wenige Entscheidungen in ${duenneKategorien.join(", ")}; Aufrufe gelten dort erst ab der Hälfte entschiedener Paare als ersetzt.`,
    );
  } else if (categoryCallSaved) {
    noteTeile.push("Alle vier Zwecke ersetzt: ein Aufruf je Foto mit Cloud-Aufruf entfällt.");
  } else {
    noteTeile.push("Ein Teilersatz spart höchstens Ausgabe-Tokens, keinen Aufruf.");
  }
  if (landmarkUrteil.underdecided) {
    noteTeile.push(
      `Zu wenige Entscheidungen in ${LANDMARK_PURPOSE}; der Landmark-Aufruf entfällt erst ab der Hälfte entschiedener Paare.`,
    );
  } else if (!landmarkCallSaved && landmarkUrteil.decided > 0) {
    noteTeile.push("Die Sehenswürdigkeit ist nicht ersetzt; der Landmark-Aufruf bleibt.");
  }

  return {
    purposes: zwecke,
    landmark: landmarkUrteil,
    replacedCategoryPurposes,
    missingPurposes,
    underdecidedPurposes,
    photosWithCall,
    photosWithoutCall,
    categoryCallSaved,
    categoryCallsSaved,
    landmarkCallSaved,
    landmarkCallsSaved,
    totalCallsSaved: categoryCallsSaved + landmarkCallsSaved,
    note: noteTeile.join(" "),
  };
}
