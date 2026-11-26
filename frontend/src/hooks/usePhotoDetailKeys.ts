import { useEffect, useRef } from 'react'

import type { RatingStatus } from '../api/types'
import { isTextInputFocused } from '../utils/textInputFocus'

interface PhotoDetailKeyHandlers {
  handlePrev: () => void
  handleNext: () => Promise<void>
  handleToggleRating: (status: RatingStatus) => void
  handleToggleFavorite: () => void
}

export function usePhotoDetailKeys({
  handlePrev,
  handleNext,
  handleToggleRating,
  handleToggleFavorite,
}: PhotoDetailKeyHandlers): void {
  // Ref-Indirektion: der Listener wird nur EINMAL
  // registriert, liest aber bei jedem Tastendruck die jeweils aktuellen Handler.
  const handlersRef = useRef({ handlePrev, handleNext, handleToggleRating, handleToggleFavorite })
  handlersRef.current = { handlePrev, handleNext, handleToggleRating, handleToggleFavorite }

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent): void {
      if (isTextInputFocused()) {
        return
      }
      switch (event.key) {
        case 'ArrowLeft':
          handlersRef.current.handlePrev()
          break
        case 'ArrowRight':
          void handlersRef.current.handleNext()
          break
        // Die Belegung 1 / 2 / 3 bleibt; Taste 1 schaltet das UNABHAENGIGE
        // Favoriten-Kennzeichen und laesst die Albumentscheidung unberuehrt (und umgekehrt).
        case '1':
          handlersRef.current.handleToggleFavorite()
          break
        case '2':
          handlersRef.current.handleToggleRating('album_worthy')
          break
        case '3':
          handlersRef.current.handleToggleRating('rejected')
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])
}
