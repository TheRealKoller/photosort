/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Ansicht "Pipeline & Kuratierung".
 *
 * Bildet den heutigen realen Inhalt von Stepper + KuratierungStepPage/CurateCategoriesPage ab:
 * klebende Fuenf-Schritt-Leiste in allen vier Zustaenden (mit Skip-Link davor), Top-N-Eingabe,
 * Tages- und Cluster-Ueberschrift, Kategorie-Abschnitte inklusive "Nicht erkannt" am Ende samt
 * Erklaertext und die gestrichelte Platzhalterkachel. Statisches Mockup.
 *
 * Der Auffangkorb-Abschnitt traegt bewusst KEINE Fehler-Optik (kein Alert-Rahmen, keine
 * Fehlerfarbe, kein Warnicon) - ein fehlendes Erkennungsergebnis ist kein Fehler. Das gilt in
 * jeder Richtung, auch in "dunkelkammer".
 */
import {
  CATCH_ALL_CATEGORY_KEY,
  CATCH_ALL_EXPLANATION,
  categoryAbbreviation,
  categoryName,
  CURATION_CLUSTER_HEADING,
  CURATION_DAY_HEADING,
  CURATION_PLACEHOLDER_LABEL,
  CURATION_SECTIONS,
  CURATION_TOP_N,
  PHOTOS,
  PIPELINE_STEPS,
  photoById,
  QUALITY_LEVEL_DOTS,
  QUALITY_LEVEL_LABELS,
  qualityLevel,
} from '../fixtures'
import { PhotoTile } from './PhotoTile'

const STEP_STATE_LABELS: Record<string, string> = {
  done: 'erledigt',
  current: 'aktuell',
  pending: 'ausstehend',
  blocked: 'blockiert',
}

/*
 * Schloss als Inline-SVG statt als Zeichen: das Unicode-Schloss (U+1F512) hat Emoji-Praesentation
 * und wuerde in "minimal"/"linie" als einziges buntes Element im Bild stehen. Ein JSX-SVG-
 * Element ist kein aus einer Zeichenkette zusammengesetztes SVG (Auflage D1 bleibt gewahrt) und
 * erbt ueber `currentColor` die Farbe der jeweiligen Richtung.
 */
function LockGlyph() {
  return (
    <svg viewBox="0 0 16 16" className="dl-step__lock" aria-hidden="true" fill="none">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth={1.5} />
      <path d="M5 7V5a3 3 0 0 1 6 0v2" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" />
    </svg>
  )
}

/** Symbol je Schrittzustand - der Zustand ist damit nie allein ueber Farbe codiert. */
function stepSymbol(state: string, index: number) {
  if (state === 'done') {
    return '✓'
  }
  if (state === 'blocked') {
    return <LockGlyph />
  }
  return String(index + 1)
}

function fixtureIndexOf(photoId: number): number {
  return PHOTOS.findIndex((entry) => entry.id === photoId)
}

export function PipelineView() {
  return (
    <div className="dl-view dl-view--pipeline">
      <a className="dl-skiplink" href="#dl-pipeline-content">
        Zum Seiteninhalt springen
      </a>

      <nav className="dl-stepper" aria-label="Fortschritt der Pipeline">
        <ol className="dl-steps">
          {PIPELINE_STEPS.map((step, index) => (
            <li className="dl-step" data-state={step.state} key={step.id}>
              <span
                className="dl-step__marker"
                aria-label={`Schritt ${index + 1} von 5: ${step.label}, ${STEP_STATE_LABELS[step.state]}`}
                aria-current={step.state === 'current' ? 'step' : undefined}
              >
                <span className="dl-step__symbol" aria-hidden="true">
                  {stepSymbol(step.state, index)}
                </span>
              </span>
              {step.state === 'blocked' && (
                <button
                  type="button"
                  className="dl-step__info"
                  aria-label={`Grund für Sperrung von ${step.label} anzeigen`}
                >
                  <span aria-hidden="true">i</span>
                </button>
              )}
              <span className="dl-step__label" aria-hidden="true">
                {step.label}
              </span>
              {index < PIPELINE_STEPS.length - 1 && (
                <span className="dl-step__line" aria-hidden="true" />
              )}
            </li>
          ))}
        </ol>
      </nav>

      <div className="dl-curate" id="dl-pipeline-content">
        <header className="dl-curate__header">
          <h1 className="dl-title">Kategorie-Kuratierung</h1>
          <p className="dl-subtitle">Deine Auswahl</p>
        </header>

        <label className="dl-field" htmlFor="dl-top-n">
          <span className="dl-field__label">Top-Fotos pro Kategorie</span>
          <input
            className="dl-input"
            id="dl-top-n"
            type="number"
            min={1}
            max={10}
            defaultValue={CURATION_TOP_N}
          />
        </label>

        <h2 className="dl-day">{CURATION_DAY_HEADING}</h2>
        <h3 className="dl-cluster">{CURATION_CLUSTER_HEADING}</h3>

        {CURATION_SECTIONS.map((section) => (
          <section className="dl-category" key={section.categoryKey}>
            <h4 className="dl-category__title">
              <span className="dl-chip dl-chip--category" title={categoryName(section.categoryKey)}>
                {categoryAbbreviation(section.categoryKey)}
              </span>
              {categoryName(section.categoryKey)}
            </h4>
            {section.categoryKey === CATCH_ALL_CATEGORY_KEY && (
              <p className="dl-category__hint">{CATCH_ALL_EXPLANATION}</p>
            )}
            <ul className="dl-grid">
              {section.photoIds.map((photoId) => {
                const photo = photoById(photoId)
                const level = qualityLevel(photo.ranking.rankScore)
                return (
                  <PhotoTile
                    key={photo.id}
                    photo={photo}
                    index={fixtureIndexOf(photo.id)}
                    footer={
                      <>
                        <span className="dl-quality">
                          <span className="dl-quality__dots" aria-hidden="true">
                            {QUALITY_LEVEL_DOTS[level]}
                          </span>{' '}
                          {QUALITY_LEVEL_LABELS[level]}
                        </span>
                        <button
                          type="button"
                          className="dl-btn dl-btn--outline dl-tile__action"
                          aria-label={`Verwerfen: ${photo.fileName}`}
                        >
                          Verwerfen
                        </button>
                      </>
                    }
                  />
                )
              })}
              {section.photoIds.length < CURATION_TOP_N &&
                Array.from({ length: CURATION_TOP_N - section.photoIds.length }, (_, index) => (
                  <li className="dl-tile dl-tile--placeholder" key={`placeholder-${index}`}>
                    {CURATION_PLACEHOLDER_LABEL}
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
