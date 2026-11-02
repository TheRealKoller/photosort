/**
 * Zählt die Cloud-Aufrufe aus den gespeicherten Laufzeilen (Spec 0606, Architektur). Maßgeblich ist
 * `remote_category_classification_runs.api_calls` — die Fotozahl unterschätzt die Ersparnis, sobald
 * ein Lauf wiederholt wurde oder Fotos ausgesetzt sind. `photos_processed` dient nur als Rückfall,
 * wenn eine Zeile keine Aufrufzahl trägt; `categorySource` hält fest, worauf die Zahl beruht.
 */
export function countCalls(runs) {
  let category = 0;
  let landmark = 0;
  let fallbackProjects = 0;

  for (const projekt of runs?.projects ?? []) {
    if (Number.isFinite(projekt?.category?.apiCalls)) {
      category += projekt.category.apiCalls;
    } else if (Number.isFinite(projekt?.category?.photosProcessed)) {
      category += projekt.category.photosProcessed;
      fallbackProjects += 1;
    }
    if (Number.isFinite(projekt?.landmark?.apiCalls)) {
      landmark += projekt.landmark.apiCalls;
    }
  }

  return {
    category,
    landmark,
    categorySource: fallbackProjects > 0 ? "photosProcessed" : "apiCalls",
    fallbackProjects,
  };
}
