import { useId, useRef, useState } from 'react'
import type { PointerEvent } from 'react'

import type { PhotoOut } from '../api/types'
import { useModalDialog } from '../lib/useModalDialog'
import { cn } from '../lib/utils'
import { fittedImageBoxStyle } from '../utils/imageFit'
import { eventPlaceName } from '../utils/timeOfDay'
import { CriterionScoreGrid } from './CriterionScoreGrid'
import { FineLabelList } from './FineLabelList'
import { MotifStrengthRow } from './MotifStrengthRow'
import { PhotoCaptureFacts } from './PhotoCaptureFacts'
import { IMAGE_UNAVAILABLE_TEXT, PhotoImage } from './PhotoImage'
import type { PhotoImageStatus } from './PhotoImage'
import { Button } from './ui/button'
import { Icon } from './ui/icon'

interface CurationLightboxProps {
  photo: PhotoOut
  /** Schliesswunsch aus „Schließen", Esc, nativer Schliessanfrage und Klick neben das Bild. */
  onClose: () => void
}

/**
 * Die Grossansicht eines Fotos aus der Kuratierung: hinsehen, schliessen, weiterkuratieren. Sie
 * zeigt genau dieses eine Foto, bewertet nichts und fuehrt nirgendwohin - kein Link, keine
 * Entscheidung, kein Blaettern.
 *
 * Natives `<dialog>` ueber `useModalDialog` (Fokusfalle, Esc, Scroll-Sperre). Erstfokus auf
 * „Schließen". Der Aufrufer montiert die Komponente mit `key={photo.id}`, damit die Details bei
 * jedem Oeffnen zugeklappt beginnen.
 *
 * BEWUSSTE ABWEICHUNG VOM `Dialog`: Ein Klick auf den Hintergrund oder auf die freie Buehne neben
 * dem Bild schliesst - hier geht nichts verloren. Der Klick auf `::backdrop` trifft das
 * `<dialog>`-Element selbst; der Innenabstand liegt deshalb auf einem inneren Container, damit ihn
 * keine Schliesspruefung mit dem Hintergrund verwechselt. Geschlossen wird nur, wenn `pointerdown`
 * UND `click` auf einer schliessenden Flaeche liegen: Ein auf dem Bild oder der Kopfzeile
 * begonnener Zug (etwa das Markieren des Dateinamens) schliesst nicht.
 *
 * Beide Kuratierungsschritte montieren sie: Sie liest keines der drei Endauswahl-Felder und leitet
 * keine Zugehoerigkeit ueber `isInAlbum` her.
 *
 * Dateiname, Pfad, Feinlabels, Orts- und Kameratext stehen ausschliesslich als React-Textknoten;
 * `relative_path` sonst nur in `alt` (Sicherheitsauflage S3 der Spec 0531).
 */
export function CurationLightbox({ photo, onClose }: CurationLightboxProps) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  // Den Fokus nach dem Schliessen setzt die Seite (`useCurationLightbox`) auf den Ausloeser.
  const modal = useModalDialog({
    open: true,
    onClose,
    initialFocusRef: closeRef,
    returnFocus: false,
  })
  const titleId = useId()
  const detailsId = useId()
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [imageStatus, setImageStatus] = useState<PhotoImageStatus>('loading')
  const pointerDownOnClosingAreaRef = useRef(false)

  const fileName = photo.relative_path.split('/').pop() ?? photo.relative_path
  const boxStyle = fittedImageBoxStyle(photo.aspect_ratio)
  const placeName = photo.event ? eventPlaceName(photo.event) : null
  // Auf `!== null` geprueft, nie auf Falsyness: „- von 12" waere eine Rangaussage ohne Rang.
  const rankRows =
    photo.ranking != null && photo.ranking.rank_position !== null
      ? [
          {
            label: 'Rang im Ereignis',
            value: `${photo.ranking.rank_position} von ${photo.ranking.partition_size}`,
          },
        ]
      : []
  const pathLine =
    imageStatus === 'loading'
      ? 'Bild wird geladen …'
      : imageStatus === 'error'
        ? IMAGE_UNAVAILABLE_TEXT
        : photo.relative_path

  function isClosingArea(target: EventTarget): boolean {
    return target === modal.ref.current || target === stageRef.current
  }

  return (
    <dialog
      {...modal}
      aria-modal="true"
      aria-labelledby={titleId}
      onPointerDown={(event: PointerEvent<HTMLDialogElement>) => {
        pointerDownOnClosingAreaRef.current = isClosingArea(event.target)
      }}
      onClick={(event) => {
        const closes = pointerDownOnClosingAreaRef.current && isClosingArea(event.target)
        pointerDownOnClosingAreaRef.current = false
        if (closes) {
          onClose()
        }
      }}
      // Unter `sm` fuellt das Panel den Sichtbereich randlos, darueber steht es mit 48px seitlichem
      // und 24px oberem/unterem Rand ueber der abgedunkelten Kuratierung. Die UA-Masse des
      // <dialog> sind aufgehoben; die Ausdehnung kommt allein aus `inset`.
      className={cn(
        'fixed inset-0 m-0 h-auto max-h-none w-auto max-w-none bg-elevated p-0 text-text',
        'sm:inset-x-12 sm:inset-y-6 sm:rounded-lg sm:border sm:border-border',
        'backdrop:bg-bg/72',
      )}
    >
      <div
        data-testid="lightbox-panel"
        className="relative flex size-full min-h-0 flex-col gap-4 p-4 sm:p-6"
      >
        <div data-testid="lightbox-header" className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 id={titleId} className="min-w-0 flex-1 truncate text-lg font-medium text-text-h">
            {fileName}
          </h2>
          <MotifStrengthRow
            assessment={photo.motif_assessment}
            motifs={photo.motifs}
            className="order-last w-full sm:order-none sm:w-auto"
          />
          {/* EIN Element fuer beide Breiten: am Telefon neben dem Dateinamen, ab `sm` rechts in der
              Bedienzeile - dort steht es als letzte Zeile des Panels bündig auf dessen
              Innenabstand. Zuerst im DOM, weil es den Erstfokus traegt. */}
          <Button
            ref={closeRef}
            type="button"
            size="sm"
            className="shrink-0 sm:absolute sm:right-6 sm:bottom-6"
            onClick={onClose}
          >
            Schließen
          </Button>
        </div>

        {/* Die Buehne: `container-type: size`, damit der Bildkasten sich ueber Container-Einheiten
            genau auf die eingepasste Bildgroesse setzen kann - so gross, wie die Buehne zulaesst,
            auch hochskaliert. Sie hat keine eigene Grundflaeche; ihre freie Flaeche neben dem
            Kasten schliesst. `tabIndex=-1`: Nach „Erneut versuchen" verschwindet die Schaltflaeche,
            und der Fokus geht hierher statt auf `<body>`. */}
        <div
          ref={stageRef}
          data-testid="lightbox-stage"
          tabIndex={-1}
          className="@container-size flex min-h-0 flex-1 cursor-zoom-out items-center justify-center"
        >
          <div
            data-testid="lightbox-image-box"
            style={boxStyle}
            className={cn('cursor-auto rounded-md', boxStyle === undefined && 'size-full')}
          >
            <PhotoImage
              photoId={photo.id}
              variant="display"
              alt={photo.relative_path}
              className="size-full object-contain"
              retryable
              onRetry={() => stageRef.current?.focus()}
              onStatusChange={setImageStatus}
            />
          </div>
        </div>

        {/* Steht immer im DOM, damit `aria-controls` nie ins Leere zeigt. Fokussierbar nur
            aufgeklappt - ohne Tastaturfokus waere der Bereich nicht scrollbar. Hoechstens die
            halbe Panelhoehe; die Buehne schrumpft entsprechend und das Bild passt sich neu ein.
            Ab `sm` drei Spalten: Qualitaet, Bildinhalt samt Rang, Feinlabels und Aufnahme. Der Ort
            steht in der Fusszeile, nicht hier. */}
        <section
          id={detailsId}
          aria-label="Bilddetails"
          hidden={!detailsOpen}
          tabIndex={detailsOpen ? 0 : undefined}
          className="max-h-1/2 overflow-y-auto rounded-md border border-border bg-surface p-6"
        >
          <div className="grid gap-6 sm:grid-cols-3">
            <CriterionScoreGrid
              criterionScores={photo.criterion_scores}
              titles={{ quality: 'Qualität', content: 'Bildinhalt' }}
              contentRows={rankRows}
              className="contents"
            />
            <div className="flex flex-col gap-4">
              {photo.fine_labels.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h3 className="text-xs font-semibold tracking-wide text-text-h uppercase">
                    Feinlabels
                  </h3>
                  <FineLabelList fineLabels={photo.fine_labels} />
                </div>
              )}
              <PhotoCaptureFacts
                photo={photo}
                headingLevel="h3"
                heading="Aufnahme"
                showPlace={false}
              />
            </div>
          </div>
        </section>

        <div data-testid="lightbox-footer" className="flex flex-col gap-3">
          <div className="grid gap-1 text-sm text-text sm:grid-cols-2 sm:gap-3">
            <p className="min-w-0 truncate">{pathLine}</p>
            {/* ORTSNAME - `place.landmark_name` (Modellantwort) und `place_name` (Ortsdatensatz
                Dritter) in EINEM Wert aus `eventPlaceName`. Reiner React-Textknoten, nie
                `dangerouslySetInnerHTML`, nie in `href`/`src`/`style`; ein eingeschleustes Skript
                laese das Session-Token aus `localStorage`. Bricht in `CurationLightbox.test.tsx >
                renders a hostile place name only as text`. */}
            <p className="min-w-0 truncate" data-testid="lightbox-place">
              {placeName ?? 'nicht bestimmbar'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-expanded={detailsOpen}
              aria-controls={detailsId}
              onClick={() => setDetailsOpen((open) => !open)}
            >
              <Icon
                name="chevron-down"
                size={16}
                className={detailsOpen ? 'rotate-180' : undefined}
              />
              Details
            </Button>
          </div>
        </div>
      </div>
    </dialog>
  )
}
