/**
 * Ersparnis-Arithmetik aus den Paarurteilen. Die Regel ist absichtlich grob und vor dem Lauf
 * festgelegt: „gleichwertig genügt“ heißt „gleich oder besser“ muss die Mehrheit der entschiedenen
 * Fotos stellen. Ein Teilersatz spart keinen Aufruf, nur Ausgabe-Tokens — deshalb zählt der
 * Kategorie-Aufruf erst bei 4/4, der Landmark-Aufruf unabhängig davon.
 */
export const CATEGORY_PURPOSES = [
  "motivstaerken",
  "ausschluss",
  "albumtauglichkeit",
  "feinlabels",
];

function zahl(wert) {
  return Number.isFinite(wert) ? wert : 0;
}

export function isReplaced(verdicts = {}) {
  const better = zahl(verdicts.better);
  const same = zahl(verdicts.same);
  const worse = zahl(verdicts.worse);
  const skipped = zahl(verdicts.skipped);
  const decided = better + same + worse;
  const replaced = decided > 0 && better + same > worse;

  return {
    better,
    same,
    worse,
    skipped,
    decided,
    replaced,
    reason: replaced
      ? "„gleich oder besser“ hat die Mehrheit der entschiedenen Fotos."
      : decided === 0
        ? "Keine Entscheidung; ohne Urteil wird nichts ersetzt."
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
  const photosWithCall = zahl(categories?.photosWithCall);
  const photosWithoutCall = zahl(categories?.photosWithoutCall);
  const candidates = zahl(landmark?.candidates);

  const categoryCallSaved = replacedCategoryPurposes === CATEGORY_PURPOSES.length;
  const categoryCallsSaved = categoryCallSaved ? photosWithCall : 0;
  const landmarkCallSaved = landmarkUrteil.replaced;
  const landmarkCallsSaved = landmarkCallSaved ? candidates : 0;

  return {
    purposes: zwecke,
    landmark: landmarkUrteil,
    replacedCategoryPurposes,
    missingPurposes,
    photosWithCall,
    photosWithoutCall,
    categoryCallSaved,
    categoryCallsSaved,
    landmarkCallSaved,
    landmarkCallsSaved,
    totalCallsSaved: categoryCallsSaved + landmarkCallsSaved,
    note: categoryCallSaved
      ? "Alle vier Zwecke ersetzt: ein Aufruf je Foto mit Cloud-Aufruf entfällt."
      : "Ein Teilersatz spart höchstens Ausgabe-Tokens, keinen Aufruf.",
  };
}
