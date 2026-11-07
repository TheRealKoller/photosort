import { describe, expect, it } from 'vitest'

import { MOTIF_SET } from '../test/motifSetFixture'
import {
  CLASSIFICATION_REVIEW_TEXTS,
  CLASSIFICATION_REVIEW_TITLE,
  NO_STATEMENT_TEXT,
  PURPOSE_LABELS,
  PURPOSE_UNIT_LABELS,
  reviewCaseTitle,
  SIDE_LABELS,
  SIDE_MARKS,
  TERMS,
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
      ...Object.values(TERMS),
      ...Object.values(SIDE_LABELS),
      ...Object.values(VERDICT_LABELS),
      ...Object.values(PURPOSE_LABELS),
      ...Object.values(PURPOSE_UNIT_LABELS),
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
