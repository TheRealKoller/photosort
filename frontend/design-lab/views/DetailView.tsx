/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Ansicht "Foto-Detail".
 *
 * Bildet den heutigen realen Inhalt von PhotoDetailPage ab: Shortcut-Zeile, Positionszaehler,
 * grosses Bild, Cloud-Vision-Status, permanenter Bewertungsdetail-Block (Kriterien mit
 * Qualitaetsbalken, Kategorie-Kandidaten, Feinlabels), Zurueck/Weiter, Vorschlagskasten, die drei
 * Bewertungsknoepfe und "Zurück zum Grid". Statisches Mockup.
 *
 * `dl-meter` ist der schmale Wertbalken je Kriterienzeile - REDUNDANT zum daneben stehenden
 * Prozentwert und deshalb die einzige Stelle neben `dl-tile__decor`, die eine Richtung ausblenden
 * darf ("minimal" tut das). Beschriftung und Prozentwert duerfen nie entfallen.
 */
import {
  categoryName,
  DETAIL_CATEGORY_CANDIDATES,
  DETAIL_CLOUD_VISION,
  DETAIL_PHOTO,
  DETAIL_PHOTO_POSITION,
  formatPercent,
  PHOTOS,
  RATING_BUTTONS,
  RATING_LABELS,
  RATING_SYMBOLS,
  SHORTCUT_HINT,
} from '../fixtures'
import { photoSrc } from '../photoSvg'

const photo = DETAIL_PHOTO
const qualityScores = photo.criterionScores.filter((score) => !score.categoryEligible)
const categoryScores = photo.criterionScores.filter((score) => score.categoryEligible)

export function DetailView() {
  return (
    <div className="dl-view dl-view--detail">
      <p className="dl-shortcuts">{SHORTCUT_HINT}</p>
      <p className="dl-position">
        <span className="dl-position__current">{DETAIL_PHOTO_POSITION}</span>
        <span className="dl-position__total">/{PHOTOS.length}</span>
      </p>

      <div className="dl-photo">
        <img
          className="dl-photo__img"
          src={photoSrc(DETAIL_PHOTO_POSITION - 1, photo.motif, photo.aspect)}
          alt={photo.fileName}
        />
      </div>

      <div className="dl-block dl-block--cloud">
        <dl className="dl-list">
          {DETAIL_CLOUD_VISION.map((entry) => (
            <div className="dl-row" key={entry.phaseLabel}>
              <dt className="dl-row__label">{entry.phaseLabel}</dt>
              <dd className="dl-row__value">
                <span className="dl-statusicon" data-tone={entry.tone} aria-hidden="true">
                  {entry.tone === 'failed' ? '⚠' : entry.tone === 'success' ? '✓' : '○'}
                </span>
                <span className="dl-row__text">{entry.statusLabel}</span>
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="dl-block dl-block--details">
        <div className="dl-group">
          <h3 className="dl-group__title">Qualität</h3>
          <dl className="dl-list">
            {qualityScores.map((score) => (
              <div className="dl-row" key={score.key}>
                <dt className="dl-row__label">{score.displayName}</dt>
                <dd className="dl-row__value">
                  <span className="dl-meter" aria-hidden="true">
                    <span className="dl-meter__fill" style={{ width: formatPercent(score.value) }} />
                  </span>
                  <span className="dl-row__num">{formatPercent(score.value)}</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="dl-group">
          <h3 className="dl-group__title">Kategorien</h3>
          <dl className="dl-list">
            {categoryScores.map((score) => (
              <div className="dl-row" key={score.key}>
                <dt className="dl-row__label">{score.displayName}</dt>
                <dd className="dl-row__value">
                  <span className="dl-meter" aria-hidden="true">
                    <span className="dl-meter__fill" style={{ width: formatPercent(score.value) }} />
                  </span>
                  <span className="dl-row__num">{formatPercent(score.value)}</span>
                </dd>
              </div>
            ))}
            <div className="dl-candidates">
              <dt className="dl-row__label">Kategorie-Kandidaten</dt>
              <dd>
                <ul className="dl-candidates__list">
                  {DETAIL_CATEGORY_CANDIDATES.map((candidate) => (
                    <li className="dl-candidate" key={candidate.categoryKey}>
                      <span className="dl-candidate__name">{categoryName(candidate.categoryKey)}</span>
                      <span className="dl-chip dl-chip--neutral">{candidate.originLabel}</span>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
            <div className="dl-row">
              <dt className="dl-row__label">Rang</dt>
              <dd className="dl-row__value">
                <span className="dl-row__num">
                  Rang {photo.ranking.rankPosition} von {photo.ranking.partitionSize}
                </span>
              </dd>
            </div>
          </dl>

          <div className="dl-finelabels">
            <h4 className="dl-finelabels__title">Feinlabels</h4>
            <ul className="dl-finelabels__list" aria-label="Feinlabels">
              {photo.fineLabels.map((label) => (
                <li key={label}>
                  <span className="dl-chip dl-chip--fine">{label}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="dl-nav">
        <button type="button" className="dl-btn dl-btn--outline" aria-label="Vorheriges Foto">
          Zurück
        </button>
        <button type="button" className="dl-btn dl-btn--outline" aria-label="Nächstes Foto">
          Weiter
        </button>
      </div>

      {photo.suggestion !== null && (
        <div className="dl-suggestion">
          <p className="dl-suggestion__title">
            Automatischer Vorschlag: {RATING_LABELS[photo.suggestion.status]}
          </p>
          <p className="dl-suggestion__reason">{photo.suggestion.reason}</p>
          <button type="button" className="dl-btn dl-btn--outline">
            Vorschlag übernehmen
          </button>
        </div>
      )}

      <div className="dl-ratings" role="group" aria-label="Bewertung">
        {RATING_BUTTONS.map((option) => (
          <button
            key={option.status}
            type="button"
            className="dl-btn dl-rating-btn"
            data-rating={option.status}
            aria-pressed={photo.ownRating === option.status}
          >
            <span className="dl-rating-btn__symbol" aria-hidden="true">
              {RATING_SYMBOLS[option.status]}
            </span>
            {option.label}
          </button>
        ))}
      </div>

      <button type="button" className="dl-btn dl-btn--ghost dl-back">
        Zurück zum Grid
      </button>
    </div>
  )
}
