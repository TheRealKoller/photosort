import type { PhotoOut, ProjectOut } from '../api/types'

/**
 * Gemeinsame Testfabriken des Frontends - die EINE Fundstelle (specs/architecture/
 * 0002-testkonzept.md).
 *
 * Abweichungen einer Testdatei sind ein Teilobjekt in `overrides`, nie eine zweite Fassung der
 * Fabrik. Die Vorgaben entsprechen dem haeufigsten Aufrufer; was ein Test ausdruecklich anders
 * braucht (Kennung, Pfad, Rangzeile, Personen), steht im Test selbst.
 */

/** Das Projekt-Testobjekt: alle Pflichtfelder von `ProjectOut` mit den Vorgaben der API. */
export function makeProject(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    last_export_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    model_choice: {
      category_method: 'cloud',
      category_provider: 'mistral',
      category_model: 'ministral-3b-2512',
      landmark_provider: 'anthropic',
      landmark_model: 'claude-haiku-4-5',
    },
    selection_target: null,
    effective_selection_target: 1,
    has_selection_proposal: false,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

/** Das Foto-Testobjekt: alle Pflichtfelder von `PhotoOut`, ohne Rangzeile, Ort und Motive. */
export function makePhoto(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    motifs: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: [],
    ...overrides,
  }
}

/** Foto einer Duplikat-Serie: Pfad `Reise/serie-<id>.jpg`, sonst die Vorgaben von `makePhoto`. */
export function makeSeriesPhoto(id: number, overrides: Partial<PhotoOut> = {}): PhotoOut {
  return makePhoto({ id, relative_path: `Reise/serie-${id}.jpg`, ...overrides })
}
