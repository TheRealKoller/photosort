import { useEffect, useRef, useState } from 'react'

/**
 * Hält den angezeigten Restdauer-Text ruhig: Ein geänderter Text wird erst übernommen, wenn er in
 * ZWEI aufeinanderfolgenden Antworten steht (AK3 b).
 *
 * Das ist das vierte der vier Mittel gegen eine zappelnde Anzeige - neben dem kumulierten
 * Durchsatz, den Schwellen und der Stufenleiter. Es fängt genau den Fall, den die drei anderen
 * nicht abfangen: Ein Wert dicht an einer Stufengrenze pendelt im Zwei-Sekunden-Takt zwischen zwei
 * Stufentexten hin und her.
 *
 * **Ein Wechsel des Teilschritts setzt sofort zurück**, und der Rücksetzfall gewinnt gegen die
 * Verzögerung: Der Text des vorigen Teilschritts beschreibt eine andere Arbeit und darf nie in den
 * nächsten hineinragen. Die allererste Angabe eines Teilschritts wird ebenfalls nicht verzögert -
 * sonst stünde nach dem Überschreiten der Schwelle noch eine Antwort lang "wird noch ermittelt".
 *
 * **Gezählt werden Renderdurchläufe, nicht Netzwerkantworten.** Eine Antwort ist von einem
 * Renderdurchlauf aus nicht unterscheidbar; die Fortschaltung läuft deshalb in einem Effekt ohne
 * Abhängigkeitsliste, also einmal je Commit. Rendert die Komponente aus einem anderen Grund neu,
 * zählt das als Antwort mit - die Anzeige wird dadurch höchstens früher aktuell, nie unruhiger als
 * der Poll-Takt.
 */
export function useSteadyEtaText(text: string, stepId: string): string {
  const [shown, setShown] = useState(text)
  const shownRef = useRef(text)
  const pendingRef = useRef<string | null>(null)
  const stepRef = useRef(stepId)

  // Der Rücksetzfall läuft im Render, nicht im Effekt: Ein Effekt käme einen Durchlauf zu spät,
  // und für genau diesen einen Durchlauf stünde der Text des vorigen Teilschritts noch da.
  if (stepRef.current !== stepId) {
    stepRef.current = stepId
    shownRef.current = text
    pendingRef.current = null
    if (shown !== text) {
      setShown(text)
    }
  }

  useEffect(() => {
    if (text === shownRef.current) {
      // Der gezeigte Text ist wieder bestätigt - eine angefangene Änderung verfällt.
      pendingRef.current = null
      return
    }
    if (pendingRef.current === text) {
      pendingRef.current = null
      shownRef.current = text
      setShown(text)
      return
    }
    pendingRef.current = text
  })

  return shown
}
