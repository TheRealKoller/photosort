import type { PhotoOut } from '../api/types'

/**
 * Der Personenfilter als reine Funktionen: `?person=<id>`, einmal oder zweimal für
 * "Beide". Im Bildbestand geht die Auswahl an den Server; im Album-Entwurf blendet sie
 * clientseitig über `PhotoOut.persons` aus, damit die Zählung des Entwurfs unverändert bleibt.
 */
export const PERSON_PARAM = 'person'

/** Höchstens zwei positive, ganzzahlige, verschiedene Ids in der Reihenfolge der Adresse. Alles
 * andere fällt weg - ein dritter Wert wird verworfen, statt eine `422` zu provozieren. */
export function parsePersonIds(params: URLSearchParams): number[] {
  const ids: number[] = []
  for (const raw of params.getAll(PERSON_PARAM)) {
    if (!/^[1-9][0-9]{0,9}$/.test(raw)) {
      continue
    }
    const id = Number(raw)
    if (!ids.includes(id)) {
      ids.push(id)
    }
  }
  return ids.slice(0, 2)
}

/** Setzt die Auswahl in eine Kopie der Adressparameter; eine leere Auswahl entfernt sie. */
export function withPersonIds(params: URLSearchParams, ids: readonly number[]): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete(PERSON_PARAM)
  for (const id of ids) {
    next.append(PERSON_PARAM, String(id))
  }
  return next
}

/** Trägt das Foto JEDE gewählte Person wirksam? Ein von Hand entfernter Name fehlt in `persons`. */
export function carriesPersons(photo: PhotoOut, ids: readonly number[]): boolean {
  return ids.every((id) => photo.persons.some((entry) => entry.person_id === id))
}

export function filterByPersons(photos: readonly PhotoOut[], ids: readonly number[]): PhotoOut[] {
  return ids.length === 0 ? [...photos] : photos.filter((photo) => carriesPersons(photo, ids))
}
