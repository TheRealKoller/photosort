/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Ansicht "Fotogrid".
 *
 * Bildet den heutigen realen Inhalt von PhotoGridPage ab: sechs Filter-Pillen, Kachelraster,
 * Bewertungs-/Vorschlags-Badge oben rechts, Override-Marker oben links, "Übernehmen"-Knopf unter
 * Vorschlagskacheln, "Weitere laden". Statisches Mockup - kein Klick loest etwas aus.
 */
import { ACTIVE_FILTER_ID, FILTERS, PHOTOS } from '../fixtures'
import { PhotoTile } from './PhotoTile'

export function GridView() {
  return (
    <div className="dl-view dl-view--grid">
      <h1 className="dl-title">Fotos</h1>

      <div className="dl-filters" role="group" aria-label="Filter">
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            type="button"
            className="dl-filter"
            aria-pressed={filter.id === ACTIVE_FILTER_ID}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <ul className="dl-grid">
        {PHOTOS.map((photo, index) => {
          const isSuggested = photo.ownRating === null && photo.suggestion !== null
          return (
            <PhotoTile
              key={photo.id}
              photo={photo}
              index={index}
              footer={
                isSuggested ? (
                  <button
                    type="button"
                    className="dl-btn dl-btn--outline dl-tile__action"
                    aria-label={`Vorschlag übernehmen: ${photo.fileName}`}
                  >
                    Übernehmen
                  </button>
                ) : undefined
              }
            />
          )
        })}
      </ul>

      <button type="button" className="dl-btn dl-btn--outline dl-more">
        Weitere laden
      </button>
    </div>
  )
}
