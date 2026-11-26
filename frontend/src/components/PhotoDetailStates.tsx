import { Link } from 'react-router'

import { PhotoDetailStage } from './PhotoDetailStage'
import { Button } from './ui/button'

interface PhotoDetailStatesProps {
  status: 'loading' | 'error' | 'completed' | 'not-found'
  errorText: string
  onRetry: () => void
  gridPath: string
  selectionPath: string
}

export function PhotoDetailStates({
  status,
  errorText,
  onRetry,
  gridPath,
  selectionPath,
}: PhotoDetailStatesProps) {
  if (status === 'completed') {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="status" className="text-text-h">
          Fertig! Keine weiteren unbewerteten Fotos.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="secondary">
            <Link to={gridPath}>Zurück zum Grid</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to={selectionPath}>Zur Endauswahl</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (status === 'not-found') {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Foto nicht in der aktuellen Auswahl gefunden.</p>
        <Button asChild variant="ghost">
          <Link to={gridPath}>Zurück zum Grid</Link>
        </Button>
      </div>
    )
  }

  /* Der Rahmen der Buehne steht in ALLEN DREI Zustaenden - ladend und fehler zeigen ihn mit
     Platzhalter bzw. `Alert` in der Fotoflaeche statt eines vorgezogenen Satzes. Sonst springt die
     Seite beim Eintreffen der Daten. Die Handler zeigen in diesen beiden Zustaenden ins Leere und
     sind deshalb leer: die Buehne sperrt Bewertung und Navigation ohnehin selbst. */
  return (
    <div className="flex flex-col gap-4">
      <PhotoDetailStage
        status={status}
        counter={null}
        photoId={null}
        altText=""
        errorText={errorText}
        onRetry={onRetry}
        currentStatus={null}
        favorite={false}
        onToggle={() => {}}
        onToggleFavorite={() => {}}
        ratingDisabled
        ratingBusy={false}
        onPrev={() => {}}
        onNext={() => {}}
        prevDisabled
        nextDisabled
      />
      <Button asChild variant="ghost" className="self-start">
        <Link to={gridPath}>Zurück zum Grid</Link>
      </Button>
    </div>
  )
}
