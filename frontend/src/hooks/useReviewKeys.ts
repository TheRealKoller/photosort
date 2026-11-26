import { useEffect, useRef } from 'react'

import type { ClassificationReviewCaseOut, ClassificationVerdict } from '../api/types'
import { VERDICT_KEYS, VERDICT_ORDER } from '../utils/classificationReviewLabels'
import { isTextInputFocused } from '../utils/textInputFocus'

/** Taste (klein geschrieben) → Urteil. Ziffern stehen bewusst nicht darin: 1/2/3 bleiben inert. */
const VERDICT_BY_KEY = new Map<string, ClassificationVerdict>(
  VERDICT_ORDER.map((verdict) => [VERDICT_KEYS[verdict].toLowerCase(), verdict]),
)

interface ReviewKeyHandlers {
  judge: (reviewCase: ClassificationReviewCaseOut, verdict: ClassificationVerdict) => void
  goToPosition: (target: number | undefined, focusHeading: boolean) => void
  markedCase: ClassificationReviewCaseOut | undefined
  previousPosition: number | undefined
  nextPosition: number | undefined
}

/** Der eine `keydown`-Listener der Fallansicht: ←/→ wechseln das Foto, Buchstaben urteilen. */
export function useReviewKeys(handlers: ReviewKeyHandlers): void {
  // Ref-Indirektion wie in PhotoDetailPage: EIN Listener, der bei jedem Druck die aktuellen
  // Handler liest.
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent): void {
      // Strg/Meta/Alt sind Browser- und Systemkuerzel: Strg+A markiert alles, Strg+F sucht - beides
      // darf kein Urteil schreiben.
      if (isTextInputFocused() || event.ctrlKey || event.metaKey || event.altKey) {
        return
      }
      const handlers = handlersRef.current
      if (event.key === 'ArrowLeft') {
        handlers.goToPosition(handlers.previousPosition, true)
        return
      }
      if (event.key === 'ArrowRight') {
        handlers.goToPosition(handlers.nextPosition, true)
        return
      }
      const verdict = VERDICT_BY_KEY.get(event.key.toLowerCase())
      if (verdict !== undefined && handlers.markedCase !== undefined) {
        event.preventDefault()
        handlers.judge(handlers.markedCase, verdict)
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])
}
