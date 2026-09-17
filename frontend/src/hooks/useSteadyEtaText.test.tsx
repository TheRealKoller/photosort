import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useSteadyEtaText } from './useSteadyEtaText'

/**
 * specs/features/0481-restdauer-klassifizierungslauf.md, AK3 (b): Der angezeigte Text ändert sich
 * erst, wenn derselbe neue Text in ZWEI aufeinanderfolgenden Antworten steht.
 *
 * Prüfgegenstand ist eine ANTWORTFOLGE, kein Zustand. Ein Test, der den Hook einmal mit A und
 * einmal mit B aufruft und "zeigt A" behauptet, bestünde auch gegen einen Hook, der gar nichts
 * verzögert.
 */

const A = 'noch ca. 2–5 Minuten'
const B = 'noch ca. 5–10 Minuten'
const C = 'noch ca. 10–20 Minuten'

interface Antwort {
  text: string
  stepId: string
}

/**
 * Spielt eine Antwortfolge ab und liefert den nach JEDER Antwort sichtbaren Text.
 *
 * Über `rerender` mit einer echten Komponente statt über `renderHook`: Gemessen wird, was im DOM
 * steht, und genau das ist die Zusage - nicht der Rückgabewert.
 */
function abspielen(folge: Antwort[]): string[] {
  function Probe({ text, stepId }: Antwort) {
    return <span data-testid="eta">{useSteadyEtaText(text, stepId)}</span>
  }

  const gesehen: string[] = []
  const { rerender } = render(<Probe {...folge[0]} />)
  gesehen.push(screen.getByTestId('eta').textContent ?? '')
  for (const antwort of folge.slice(1)) {
    rerender(<Probe {...antwort} />)
    gesehen.push(screen.getByTestId('eta').textContent ?? '')
  }
  return gesehen
}

function wechselZaehlen(gesehen: string[]): number {
  return gesehen.filter((text, index) => index > 0 && text !== gesehen[index - 1]).length
}

describe('useSteadyEtaText', () => {
  it('zeigt die allererste Angabe sofort, ohne sie zu verzögern', () => {
    // Sonst stünde beim ersten Poll nach der Schwelle noch der Vorgängertext - oder gar keiner.
    expect(abspielen([{ text: A, stepId: 'criteria' }])).toEqual([A])
  })

  it('erzeugt bei einer pendelnden Folge NULL sichtbare Wechsel', () => {
    // Der eigentliche Zweck: A,B,A,B,A,B ist der Fall, den die Stufenleiter allein nicht abfängt -
    // ein Wert dicht an einer Stufengrenze springt im Zwei-Sekunden-Takt hin und her.
    const gesehen = abspielen([A, B, A, B, A, B].map((text) => ({ text, stepId: 'criteria' })))

    expect(gesehen).toEqual([A, A, A, A, A, A])
    expect(wechselZaehlen(gesehen)).toBe(0)
  })

  it('übernimmt einen neuen Text beim DRITTEN Eintrag, nicht beim zweiten und nicht später', () => {
    // Die Grenze beidseitig: beim zweiten noch A (sonst verzögert der Hook gar nicht), beim
    // dritten schon B (sonst verzögert er länger als zugesagt und die Anzeige hinkt nach).
    expect(abspielen([A, B, B].map((text) => ({ text, stepId: 'criteria' })))).toEqual([A, A, B])
  })

  it('bleibt auch bei drei verschiedenen Texten hintereinander beim ersten', () => {
    expect(abspielen([A, B, C].map((text) => ({ text, stepId: 'criteria' })))).toEqual([A, A, A])
  })

  it('setzt beim Wechsel des Teilschritts sofort zurück, statt den alten Text hineinragen zu lassen', () => {
    // Mit VERSCHIEDENEN Texten geprüft: Bei zufällig gleichem Stufentext bliebe der Fehler
    // unsichtbar, und genau dann prüfte der Test nichts.
    const gesehen = abspielen([
      { text: A, stepId: 'criteria' },
      { text: A, stepId: 'criteria' },
      { text: C, stepId: 'landmark' },
    ])

    expect(gesehen).toEqual([A, A, C])
  })

  it('lässt den Rücksetzfall gegen die Verzögerung gewinnen', () => {
    // Der Teilschritt wechselt MITTEN im offenen Fenster (B steht erst einmal an). Der Text des
    // neuen Teilschritts gilt trotzdem sofort - er beschreibt etwas anderes als der alte.
    const gesehen = abspielen([
      { text: A, stepId: 'criteria' },
      { text: B, stepId: 'criteria' },
      { text: C, stepId: 'landmark' },
    ])

    expect(gesehen).toEqual([A, A, C])
  })

  it('bleibt über einen langen Lauf hinweg ruhig', () => {
    // OBERGRENZE der Textwechsel über eine fest notierte, gestreute Folge: ein ~30-Minuten-Lauf
    // im Zwei-Sekunden-Takt, dessen Schätzung um zwei Stufengrenzen herum zittert und erst spät
    // wirklich absinkt. Ohne diesen Fall ist die Zusage nur auf zwei Antworten kalibriert und
    // sagt über eine reale Anzeige nichts.
    const stufe: Record<string, string> = { A, B, C }
    const folge = [...'AABABBBABBBBBBCBCCCCCBCCCCCCCC'].map((zeichen) => ({
      text: stufe[zeichen],
      stepId: 'criteria',
    }))

    const gesehen = abspielen(folge)

    // Zwei echte Stufenwechsel (A -> B -> C) und kein einziger durch das Zittern dazwischen.
    expect(wechselZaehlen(gesehen)).toBe(2)
    expect(gesehen[0]).toBe(A)
    expect(gesehen[gesehen.length - 1]).toBe(C)
  })
})
