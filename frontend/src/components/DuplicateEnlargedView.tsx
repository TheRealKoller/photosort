import { useEffect, useId, useRef } from 'react'

import type { DuplicateDecision, DuplicateGroupItem } from '../api/types'
import { useEdgeFocusHandoff } from '../hooks/useEdgeFocusHandoff'
import { cn } from '../lib/utils'
import {
  DUPLICATE_ZUSTAENDE,
  DuplicateChoice,
  DuplicateMetrics,
  DuplicateStateLabel,
} from './DuplicatePhotoTile'
import { PhotoImage } from './PhotoImage'
import { Button } from './ui/button'
import { Icon } from './ui/icon'

export interface DuplicateEnlargedViewProps {
  items: DuplicateGroupItem[]
  /** Die gezeigte Aufnahme als FOTO-ID — die Seite stellt sicher, dass sie in `items` liegt. */
  currentId: number
  /** Indizes in `items` mit der besten angezeigten Schärfe bzw. Belichtung. */
  bestSharpness: ReadonlySet<number>
  bestExposure: ReadonlySet<number>
  decidingIds: ReadonlySet<number>
  onSelect: (photoId: number) => void
  onClose: () => void
  onDecide: (photoId: number, decision: DuplicateDecision) => void
}

/**
 * Die Großansicht der Vergleichsansicht (A11): Bühne, Seitenspalte und Streifen aller Mitglieder.
 *
 * KEIN DIALOG: Sie ersetzt das Raster an derselben Stelle, und Kopf, Hinweise, Gruppenaktionen
 * und Abschluss der Seite bleiben stehen. Ein Dialog finge den Fokus und nähme genau das aus dem
 * Blick, was hier entschieden wird — die Folge von „Behalten" steht an der Handlung.
 *
 * DIE BÜHNE IST UNVERFÄLSCHT: keine Deckkraft, kein Filter, keine Überlagerung und kein
 * Zustandsrahmen am Bild — hier wird die Bildqualität beurteilt. Den Zustand trägt die
 * Seitenspalte mit Rahmen, Symbol und Wort.
 *
 * Blättern ohne Rundlauf: Am ersten und letzten Mitglied bleibt die Ansicht stehen, die
 * Schaltfläche ist `disabled`, und ein Fokus darauf geht an die Gegenschaltfläche. Esc schließt,
 * ← und → blättern; die Tasten wirken nur, solange diese Ansicht montiert ist.
 */
export function DuplicateEnlargedView({
  items,
  currentId,
  bestSharpness,
  bestExposure,
  decidingIds,
  onSelect,
  onClose,
  onDecide,
}: DuplicateEnlargedViewProps) {
  const index = items.findIndex((item) => item.photo.id === currentId)
  const aktuell = items[index]
  const n = items.length
  const ueberschriftId = useId()
  const ueberschriftRef = useRef<HTMLHeadingElement>(null)
  const { previousRef, nextRef, remember } = useEdgeFocusHandoff(index === 0, index === n - 1)

  useEffect(() => {
    ueberschriftRef.current?.focus()
  }, [])

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      const ziel =
        event.key === 'ArrowLeft' ? index - 1 : event.key === 'ArrowRight' ? index + 1 : null
      const zielItem = ziel === null ? undefined : items[ziel]
      if (zielItem !== undefined) {
        remember()
        onSelect(zielItem.photo.id)
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [index, items, onClose, onSelect, remember])

  if (aktuell === undefined) {
    return null
  }

  function blaettern(schritt: -1 | 1): void {
    const zielItem = items[index + schritt]
    if (zielItem !== undefined) {
      remember()
      onSelect(zielItem.photo.id)
    }
  }

  return (
    <section aria-labelledby={ueberschriftId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-4 lg:flex-row">
        {/* Feste Höhe, damit nichts springt, wenn das authentifiziert geladene Bild eintrifft. */}
        <div
          data-testid="duplicate-stage"
          className="h-96 min-w-0 overflow-hidden rounded-md bg-surface lg:h-144 lg:flex-1"
        >
          <PhotoImage
            key={aktuell.photo.id}
            photoId={aktuell.photo.id}
            variant="display"
            alt={aktuell.photo.relative_path}
            className="size-full object-contain"
          />
        </div>

        <div
          data-testid="duplicate-sidebar"
          data-duplicate-decision={aktuell.effective_decision}
          className={cn(
            'flex flex-col gap-3 rounded-lg bg-elevated p-4 lg:w-72 lg:shrink-0',
            DUPLICATE_ZUSTAENDE[aktuell.effective_decision].rahmen,
          )}
        >
          <h2 id={ueberschriftId} ref={ueberschriftRef} tabIndex={-1} className="text-lg">
            Aufnahme {index + 1} von {n}
          </h2>
          {/* Extern entstandener Text, ausschließlich als React-Textknoten. */}
          <p className="font-mono text-xs break-all text-text-muted">
            {aktuell.photo.relative_path}
          </p>
          <DuplicateStateLabel decision={aktuell.effective_decision} />
          <DuplicateMetrics
            sharpness={aktuell.sharpness}
            exposure={aktuell.exposure}
            bestSharpness={bestSharpness.has(index)}
            bestExposure={bestExposure.has(index)}
          />
          <DuplicateChoice
            photo={aktuell.photo}
            effectiveDecision={aktuell.effective_decision}
            keepPossible={aktuell.keep_possible}
            deciding={decidingIds.has(aktuell.photo.id)}
            onDecide={(decision) => onDecide(aktuell.photo.id, decision)}
          />
          <div className="flex flex-wrap gap-3">
            <Button
              ref={previousRef}
              type="button"
              variant="outline"
              size="sm"
              className="h-11 sm:h-8"
              disabled={index === 0}
              onClick={() => blaettern(-1)}
            >
              Vorherige Aufnahme
            </Button>
            <Button
              ref={nextRef}
              type="button"
              variant="outline"
              size="sm"
              className="h-11 sm:h-8"
              disabled={index === n - 1}
              onClick={() => blaettern(1)}
            >
              Nächste Aufnahme
            </Button>
          </div>
          <Button type="button" variant="ghost" size="sm" className="self-start" onClick={onClose}>
            Vergrößerung schließen
          </Button>
        </div>
      </div>

      {/* Der Streifen bricht um und scrollt nie waagerecht. Die aktuelle Aufnahme trägt `--text-h`
          statt Akzent: Akzent heißt in dieser Ansicht „Behalten". */}
      <ul aria-label="Alle Aufnahmen der Gruppe" className="flex flex-wrap gap-3">
        {items.map((item, position) => {
          const zustand = DUPLICATE_ZUSTAENDE[item.effective_decision]
          const istAktuell = position === index
          return (
            <li key={item.photo.id} className="relative">
              <button
                type="button"
                aria-label={`Aufnahme ${position + 1} von ${n}: ${item.photo.relative_path}, ${zustand.text}`}
                aria-current={istAktuell ? 'true' : undefined}
                onClick={() => {
                  remember()
                  onSelect(item.photo.id)
                }}
                className={cn(
                  'block size-16 overflow-hidden rounded-md border-2 sm:size-20',
                  istAktuell ? 'border-text-h' : 'border-transparent',
                )}
              >
                <PhotoImage
                  photoId={item.photo.id}
                  variant="thumbnail"
                  alt=""
                  className="size-full object-cover"
                />
              </button>
              <span
                className={cn(
                  'pointer-events-none absolute bottom-1 left-1 rounded-sm bg-overlay p-1',
                  zustand.schrift,
                )}
              >
                <Icon name={zustand.icon} size={14} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
