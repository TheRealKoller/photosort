import { describe, expect, it } from 'vitest'

import type { ClassificationReviewPurpose } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import {
  caseSideValueText,
  CLASSIFICATION_REVIEW_TEXTS,
  CLASSIFICATION_REVIEW_TITLE,
  NO_DEVIATION_TEXT,
  NO_SHARED_STATEMENT_TEXT,
  NO_STATEMENT_TEXT,
  noPhotosComparedText,
  notComparedText,
  PHASE_LABELS,
  PROVIDER_BLOCKED_TEXT,
  PURPOSE_LABELS,
  PURPOSE_UNIT_LABELS,
  REVIEW_DETAIL_TEXTS,
  reviewCaseTitle,
  reviewListStand,
  silentSide,
  SIDE_COST_LABELS,
  SIDE_LABELS,
  SIDE_MARKS,
  sideOriginText,
  TERMS,
  UNAVAILABLE_REASON_TEXTS,
  UNIT_GROUP_LABELS,
  VERDICT_KEYS,
  VERDICT_LABELS,
  VERDICT_ORDER,
} from './classificationReviewLabels'
import { PROJECT_NAV_SECONDARY_TARGETS } from './projectRoutes'

/*
 * Die eine Begriffsquelle der Pruefseiten (Spec 0616, Abschnitt UI/UX). Geprueft wird hier die
 * GESCHLOSSENE Menge: vier Urteile, vier Zwecke, zwei Seiten. Fehlt ein Wert, faellt es auf, bevor
 * eine Aufrufstelle ein Literal erfindet.
 */

describe('classificationReviewLabels - Urteile', () => {
  it('nennt genau die vier Urteile in der Reihenfolge der Schaltflaechen', () => {
    expect(VERDICT_ORDER).toEqual(['a_better', 'b_better', 'both_ok', 'both_wrong'])
    expect(VERDICT_ORDER.map((verdict) => VERDICT_LABELS[verdict])).toEqual([
      'A besser',
      'B besser',
      'beide ok',
      'beide falsch',
    ])
  })

  it('deckt jedes Urteil des Backends ab und kein weiteres', () => {
    expect(Object.keys(VERDICT_LABELS).sort()).toEqual(
      ['a_better', 'b_better', 'both_ok', 'both_wrong'].sort(),
    )
  })
})

describe('classificationReviewLabels - Zwecke', () => {
  it('nennt genau die vier Pruefzwecke', () => {
    expect(PURPOSE_LABELS).toEqual({
      motifs: 'Motive',
      motif_feature: 'Merkmale',
      excluded_document: 'Dokument-Ausschluss',
      album_level: 'Albumtauglichkeit',
    })
    expect(Object.keys(PURPOSE_LABELS).sort()).toEqual(
      ['motifs', 'motif_feature', 'excluded_document', 'album_level'].sort(),
    )
  })

  // Die Einheit steht im Spaltenkopf der Uebersicht, nicht an jeder Zahl (Spec 0616, UI/UX).
  it('nennt die Einheiten der beiden Zaehlweisen', () => {
    expect(PURPOSE_UNIT_LABELS).toEqual({ photo: 'Fotos', pair: 'Paare' })
  })
})

describe('classificationReviewLabels - Begriffe und Seiten', () => {
  it('fuehrt die drei Begriffe der Pruefseiten', () => {
    expect(TERMS).toEqual({ review: 'Prüfung', case: 'Fall', verdict: 'Urteil' })
  })

  it('benennt die beiden Seiten mit Buchstabenmarke', () => {
    expect(SIDE_LABELS).toEqual({ a: 'Seite A', b: 'Seite B' })
    expect(SIDE_MARKS).toEqual({ a: 'A', b: 'B' })
  })

  it('formuliert die fehlende Aussage als Wort, nie als false oder 0', () => {
    expect(NO_STATEMENT_TEXT).toBe('keine Aussage')
  })
})

describe('classificationReviewLabels - Falltitel', () => {
  it('nennt fotozaehlende Zwecke mit ihrem Zwecknamen', () => {
    for (const purpose of ['motifs', 'excluded_document', 'album_level'] as const) {
      expect(reviewCaseTitle(purpose, null, MOTIF_SET.items)).toBe(PURPOSE_LABELS[purpose])
    }
  })

  it('nennt einen feinen Merkmal-Fall "Merkmal: {Motivname}" aus formatMotifKey', () => {
    expect(reviewCaseTitle('motif_feature', 'landschaft', MOTIF_SET.items)).toBe(
      'Merkmal: Landschaft',
    )
  })

  // Der Motivname kommt aus dem geladenen Set, nie aus einem Literal: ein unbekannter Schluessel
  // faellt auf denselben generischen Namen zurueck wie die uebrigen Motivanzeigen.
  it('faellt bei unbekanntem Motivschluessel auf den generischen Namen zurueck', () => {
    expect(reviewCaseTitle('motif_feature', 'unbekanntes_motiv', MOTIF_SET.items)).toBe(
      'Merkmal: Unbekanntes_motiv',
    )
  })
})

describe('classificationReviewLabels - Abgrenzung zur Bewertung', () => {
  it('fuehrt nirgends "Vergleich" oder "Bewertung" als sichtbares Wort allein', () => {
    const visible = [
      CLASSIFICATION_REVIEW_TITLE,
      ...Object.values(CLASSIFICATION_REVIEW_TEXTS),
      ...Object.values(REVIEW_DETAIL_TEXTS),
      ...Object.values(TERMS),
      ...Object.values(SIDE_LABELS),
      ...Object.values(VERDICT_LABELS),
      ...Object.values(PURPOSE_LABELS),
      ...Object.values(PURPOSE_UNIT_LABELS),
      ...Object.values(UNIT_GROUP_LABELS),
      ...Object.values(PHASE_LABELS),
      NO_STATEMENT_TEXT,
    ]
    expect(visible).not.toContain('Vergleich')
    expect(visible).not.toContain('Bewertung')
  })

  it('nennt den Seitentitel wortgleich mit dem Nebenziel der Projektnavigation', () => {
    const navTarget = PROJECT_NAV_SECONDARY_TARGETS.find(
      (target) => target.id === 'classificationReviews',
    )
    expect(navTarget?.label).toBe(CLASSIFICATION_REVIEW_TITLE)
  })
})

describe('classificationReviewLabels - Herkunft einer Seite', () => {
  // Die Herkunft wird beim Anlegen eingefroren und beim Lesen nur noch angezeigt; ihre drei
  // Formen stehen deshalb hier und nicht an jeder Aufrufstelle neu.
  it('nennt eine Cloud-Seite mit Anbieter und Modell', () => {
    expect(
      sideOriginText({
        kind: 'cloud',
        provider: 'anthropic',
        model: 'claude-sonnet-4-5',
        eye_model_revision: null,
        eye_mapping_version: null,
      }),
    ).toBe('Cloud · Anthropic · Modell claude-sonnet-4-5')
  })

  it('nennt eine Eye-Seite mit Modellrevision und Uebersetzungsfassung', () => {
    expect(
      sideOriginText({
        kind: 'eye',
        provider: null,
        model: null,
        eye_model_revision: 'eye-4.2.3',
        eye_mapping_version: 'v1',
      }),
    ).toBe('Eye · eye-4.2.3 · Übersetzung v1')
  })

  // Zwei Fassungen desselben Modells unterscheiden sich oft nur am Ende - die Zeile darf deshalb
  // nicht gekuerzt werden. Das ist eine Klassen-Zusage an der Aufrufstelle (break-words).
  it('nennt eine lokale Seite als ohne Sehenswuerdigkeits-Beitrag', () => {
    expect(
      sideOriginText({
        kind: 'local',
        provider: null,
        model: null,
        eye_model_revision: null,
        eye_mapping_version: null,
      }),
    ).toBe('Lokal · ohne Sehenswürdigkeits-Beitrag')
  })
})

describe('classificationReviewLabels - Stand einer Pruefung', () => {
  const base = { case_count: 4, case_open: 2 }

  it('nennt eine laufende Pruefung "läuft…" mit Laufindikator', () => {
    expect(reviewListStand({ ...base, status: 'running' })).toEqual({
      tone: 'running',
      label: 'läuft…',
    })
  })

  it('nennt eine gescheiterte Pruefung "fehlgeschlagen"', () => {
    expect(reviewListStand({ ...base, status: 'failed' })).toEqual({
      tone: 'failed',
      label: 'fehlgeschlagen',
    })
  })

  it('zaehlt die offenen Faelle gegen alle Faelle', () => {
    expect(reviewListStand({ ...base, status: 'success' })).toEqual({
      tone: 'never',
      label: '2 von 4 Fällen offen',
    })
  })

  it('nennt eine vollstaendig beurteilte Pruefung "alle beurteilt"', () => {
    expect(reviewListStand({ case_count: 4, case_open: 0, status: 'success' })).toEqual({
      tone: 'success',
      label: 'alle beurteilt',
    })
  })

  // "keine Abweichungen" ist eine Aussage ueber die Verfahren, nicht ueber die Urteile - und sie
  // steht nur, wenn es wirklich keinen Fall gibt.
  it('nennt eine Pruefung ohne Faelle "keine Abweichungen"', () => {
    expect(reviewListStand({ case_count: 0, case_open: 0, status: 'success' })).toEqual({
      tone: 'success',
      label: 'keine Abweichungen',
    })
    expect(NO_DEVIATION_TEXT).toBe('Die beiden Verfahren stimmen auf allen Fotos überein.')
  })
})

describe('classificationReviewLabels - Sperrgruende und Kostenworte', () => {
  // Die Gruende sind eine GESCHLOSSENE Menge fester Saetze; der Server nennt Tokens, die
  // Oberflaeche formuliert sie.
  it('formuliert jeden Sperrgrund als Satz', () => {
    expect(UNAVAILABLE_REASON_TEXTS).toEqual({
      no_consent: 'keine Cloud-Einwilligung im Projekt',
      no_api_key: 'für keinen Cloud-Anbieter ist ein API-Schlüssel hinterlegt',
      eye_disabled: 'Eye ist in dieser Installation abgeschaltet',
    })
    expect(PROVIDER_BLOCKED_TEXT).toBe('kein API-Schlüssel hinterlegt')
  })

  // "kostenfrei" ist ein Wort, keine 0 (Design-System).
  it('nennt den Preis einer Wahl als Wort, nie als Betrag', () => {
    expect(SIDE_COST_LABELS).toEqual({ free: 'kostenfrei', cloud: 'Cloud · kostenpflichtig' })
  })
})

describe('classificationReviewLabels - Detailseite', () => {
  // Buchstaben, keine Ziffern: 1/2/3 sind die Bewertungstasten des Bestands.
  it('belegt jedes Urteil mit genau einem Buchstaben', () => {
    expect(VERDICT_ORDER.map((verdict) => VERDICT_KEYS[verdict])).toEqual(['A', 'B', 'O', 'F'])
  })

  it('nennt die Rohwerte je Zweck - ja/nein, Albumstufe, und null als "keine Aussage"', () => {
    const empty = {
      motifs: null,
      present: null,
      strength: null,
      excluded_document: null,
      album_level: null,
    }
    const motifs = MOTIF_SET.items
    expect(caseSideValueText('motifs', { ...empty, motifs: ['menschen'] }, motifs)).toBe('Menschen')
    expect(caseSideValueText('motifs', { ...empty, motifs: [] }, motifs)).toBe('kein Motiv')
    expect(caseSideValueText('motif_feature', { ...empty, present: false }, motifs)).toBe('nein')
    expect(
      caseSideValueText('excluded_document', { ...empty, excluded_document: true }, motifs),
    ).toBe('ja')
    expect(caseSideValueText('album_level', { ...empty, album_level: 0 }, motifs)).toBe(
      'Stufe 0 von 5',
    )
    for (const purpose of Object.keys(PURPOSE_LABELS) as ClassificationReviewPurpose[]) {
      expect(caseSideValueText(purpose, empty, motifs)).toBe(NO_STATEMENT_TEXT)
    }
  })

  // Lokal kennt weder Dokument-Ausschluss noch Albumstufe; zu Motiven sagen alle Seiten etwas.
  it('nennt die strukturell schweigende Seite eines Zwecks', () => {
    expect(silentSide('album_level', { a: 'cloud', b: 'local' })).toBe('b')
    expect(silentSide('excluded_document', { a: 'local', b: 'eye' })).toBe('a')
    expect(silentSide('motifs', { a: 'local', b: 'cloud' })).toBeNull()
    expect(silentSide('album_level', { a: 'eye', b: 'cloud' })).toBeNull()
    expect(notComparedText('b')).toBe('nicht verglichen — Seite B trifft dazu keine Aussage')
    expect(NO_SHARED_STATEMENT_TEXT).toBe('nicht verglichen — keine gemeinsame Aussage')
    expect(noPhotosComparedText(1)).toBe('keine Fotos verglichen - 1 Foto fehlgeschlagen')
  })
})
