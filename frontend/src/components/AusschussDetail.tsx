import { useEffect } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { AusschussPhotoEntry } from '../api/types'
import { DUPLICATE_IMMUTABLE_TEXT, DUPLICATE_ZUSTAENDE } from './DuplicatePhotoTile'
import { useAusschussEntryQuery } from '../hooks/useAusschuss'
import { useDuplicateDecisionMutation } from '../hooks/useDuplicates'
import { duplicateComparePath } from '../utils/projectRoutes'
import { AUSSCHUSS_MISSING_ENTRY_TEXT } from '../utils/ausschussTexts'
import {
  ENTSCHEIDUNG_SCHRIFT,
  Entscheidungshinweise,
  entscheidungswort,
} from './AusschussDecisionLine'
import { GrundKennzeichen } from './AusschussGrund'
import { PhotoImage } from './PhotoImage'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

/**
 * Die Detailansicht: Grossbild und Entscheidungszeile, beim Gruppenmitglied dazu der Weg in die
 * Vergleichsansicht. Die Gruppe selbst wird hier nicht geladen - sie wird dort entschieden.
 *
 * `Esc` schliesst nur, solange diese Ansicht ueberhaupt offen ist - das erledigt die Komponente
 * selbst statt der Seite, weil sie genau dann montiert ist.
 */
export function AusschussDetail({
  projectId,
  photoId,
  onClose,
}: {
  projectId: number
  photoId: number
  onClose: () => void
}) {
  const query = useAusschussEntryQuery(projectId, photoId)
  const eintrag: AusschussPhotoEntry | null = query.data ?? null

  /* Der Schreibweg ist der EINZELNE: Er trifft genau diese Aufnahme. Der Anker der Gruppe ist
     dabei nur der Ort, an dem die Antwort im Zwischenspeicher landet - die Menge der betroffenen
     Fotos bestimmt der Server, die Oberflaeche schickt keine Id-Liste mit. */
  const decisionMutation = useDuplicateDecisionMutation(
    projectId,
    eintrag?.group_anchor_photo_id ?? photoId,
  )

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Aufnahme wird geladen…
      </p>
    )
  }

  if (query.isError) {
    return (
      <Alert onRetry={() => void query.refetch()}>
        {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Aufnahme.'}
      </Alert>
    )
  }

  if (eintrag === null) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-text">{AUSSCHUSS_MISSING_ENTRY_TEXT}</p>
        <Button type="button" variant="outline" onClick={onClose}>
          Zurück zur Übersicht
        </Button>
      </div>
    )
  }

  /* „Aufheben" gibt es nur, wo es etwas bewirkt: Bei einer Ablehnung wegen geringer Bildqualitaet
    gibt es keine Gruppe, und kein Wert der Entscheidungszeile aendert den Zustand dieser
    Aufnahme. Die Anzeige bietet „Behalten" nur, wo der Serverwert es erlaubt — keinen
    deaktivierten Ersatz. */
  const keepPossible = eintrag.keep_possible
  return (
    <div className="flex w-full flex-col items-start gap-3">
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg">Aufnahme im Ausschuss</h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Detailansicht schließen"
          onClick={onClose}
        >
          Schließen
        </Button>
      </div>

      <div className="flex w-full flex-col gap-4">
        <div className="flex flex-col items-start gap-3">
          {/* Grossbild in der Variante `display`: Hier wird beurteilt, und ein hochskaliertes
              Vorschaubild entschiede die Frage nach der Schaerfe falsch. `object-contain`, damit
              nichts beschnitten wird. */}
          <div className="w-full overflow-hidden rounded-md bg-surface">
            <PhotoImage
              photoId={eintrag.photo.id}
              variant="display"
              alt={eintrag.photo.relative_path}
              className="max-h-96 w-full object-contain"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            {eintrag.reason !== 'earlier_decision' && <GrundKennzeichen reason={eintrag.reason} />}
            <span
              data-testid="detail-decision"
              className={ENTSCHEIDUNG_SCHRIFT[eintrag.decision ?? 'offen']}
            >
              {entscheidungswort(eintrag.decision)}
            </span>
            <Entscheidungshinweise
              reason={eintrag.reason}
              decision={eintrag.decision}
              decisionEffective={eintrag.decision_effective}
              keepPossible={eintrag.keep_possible}
            />
            <span className="font-mono text-xs text-text-muted">{eintrag.photo.relative_path}</span>
          </div>

          <div
            role="group"
            aria-label="Entscheidung über diese Aufnahme"
            className="flex flex-wrap gap-3"
          >
            {keepPossible && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label={`${DUPLICATE_ZUSTAENDE.keep.text} (Detailansicht): ${eintrag.photo.relative_path}`}
                aria-pressed={eintrag.decision === 'keep'}
                disabled={decisionMutation.isPending}
                busy={decisionMutation.isPending && eintrag.decision !== 'keep'}
                onClick={() =>
                  decisionMutation.mutate({ photoId: eintrag.photo.id, decision: 'keep' })
                }
              >
                {DUPLICATE_ZUSTAENDE.keep.text}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={`${DUPLICATE_ZUSTAENDE.discard.text} (Detailansicht): ${eintrag.photo.relative_path}`}
              aria-pressed={eintrag.decision === 'discard'}
              disabled={decisionMutation.isPending}
              busy={decisionMutation.isPending && eintrag.decision !== 'discard'}
              onClick={() =>
                decisionMutation.mutate({ photoId: eintrag.photo.id, decision: 'discard' })
              }
            >
              {DUPLICATE_ZUSTAENDE.discard.text}
            </Button>
          </div>

          {!keepPossible && <p className="text-xs text-text-muted">{DUPLICATE_IMMUTABLE_TEXT}</p>}

          {/* Am Anker, nicht am Grund: Auch der Gewinner mit Schaerfe-Ablehnung (`low_quality`)
              liegt in einer Gruppe. Ohne Anker gibt es keinen Weg ins Leere. */}
          {eintrag.group_anchor_photo_id !== null && (
            <Button asChild variant="outline" size="sm">
              <Link
                to={duplicateComparePath(projectId, eintrag.group_anchor_photo_id, {
                  fromAusschuss: true,
                })}
              >
                Duplikat-Gruppe vergleichen
              </Link>
            </Button>
          )}

          {decisionMutation.isError && (
            <Alert>
              {decisionMutation.error instanceof ApiError
                ? decisionMutation.error.detail
                : 'Die Entscheidung konnte nicht gespeichert werden.'}
            </Alert>
          )}
        </div>
      </div>
    </div>
  )
}
