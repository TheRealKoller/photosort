import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { DuplicateDecision } from '../api/types'
import { DuplicateEnlargedView } from '../components/DuplicateEnlargedView'
import { DuplicatePhotoTile } from '../components/DuplicatePhotoTile'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Progress } from '../components/ui/progress'
import { Skeleton } from '../components/ui/skeleton'
import {
  useDuplicateDecisionMutation,
  useDuplicateGroupConfirmMutation,
  useDuplicateGroupDecisionMutation,
  useDuplicateGroupQuery,
} from '../hooks/useDuplicates'
import { useEdgeFocusHandoff } from '../hooks/useEdgeFocusHandoff'
import { bestExposureIndices, bestSharpnessIndices, formatSpan } from '../utils/duplicateMetrics'
import { ausschussStepPath, duplicateComparePath } from '../utils/projectRoutes'

const SKELETON_TILE_COUNT = 4

/**
 * Der erste Hinweis (A3): Antippen speichert sofort, und es gilt der ANGEZEIGTE Zustand.
 *
 * „Bleibt erhalten" hängt am angezeigten „Behalten" — nie an „nicht angetippt" oder
 * „unentschieden": Ein unentschiedener Duplikat-Verlierer zeigt bereits „Ausschuss" und scheidet
 * ohne weiteres Zutun aus. Eine Zusage über nicht Angetipptes wäre eine, die die Ansicht nicht
 * halten kann.
 */
export const DUPLICATE_HINT_TEXT =
  'Antippen von „Behalten“ oder „Ausschuss“ wird sofort gespeichert. Es gilt der angezeigte ' +
  'Zustand: Was „Behalten“ zeigt, bleibt erhalten; nur was „Ausschuss“ zeigt, scheidet aus der ' +
  'weiteren Bearbeitung aus.'

/**
 * Die Folge von „behalten", an der Handlung selbst (Auflage S4 der Spec 0486, S12 der Spec 0533).
 *
 * „Behalten" ist keine ansichtsinterne Buchführung: Die Aufnahme läuft danach in die
 * Kriterien-Bewertung und, bei erteilter Einwilligung, in die Cloud-Klassifizierung. Steht das
 * nicht hier — im Raster wie in der Großansicht —, trifft der Nutzer eine Entscheidung über einen
 * Datenabfluss, von dem er nichts weiß.
 */
export const DUPLICATE_CONSEQUENCE_TEXT =
  '„Behalten" heißt: Die Aufnahme läuft in die Bewertung weiter — und, solange die ' +
  'Cloud-Freigabe dieses Projekts gesetzt ist, auch an den Cloud-Anbieter.'

/** Der leere Zustand. Er deckt alle Fälle ab, in denen es zu dieser Aufnahme keine Gruppe gibt —
 * unbekanntes Foto, fremdes Projekt, kein Duplikat, oder eine Gruppe, die ein neuer Lauf
 * aufgelöst hat. Der Server unterscheidet sie nicht, und die Ansicht kann es deshalb auch
 * nicht. */
export const DUPLICATE_EMPTY_TEXT =
  'Zu dieser Aufnahme gibt es keine Duplikat-Gruppe. Möglicherweise hat ein neuer Lauf sie ' +
  'aufgelöst.'

const LAST_GROUP_TEXT = 'Gespeichert — das war die letzte Gruppe.'

/**
 * Alle Aufnahmen einer Duplikat-Gruppe — als Raster oder in der Großansicht, je Aufnahme
 * entscheidbar, und als Ganzes abschließbar.
 *
 * DAS RASTER BRICHT UM, STATT DIE BILDER ZU VERKLEINERN: zwei Spalten schmal, drei breit.
 *
 * DIE GROSSANSICHT IST KEIN DIALOG: Sie ersetzt das Raster an derselben Stelle; Kopf, Hinweise,
 * Gruppenaktionen und Abschluss bleiben stehen. Die vergrößerte Aufnahme ist eine FOTO-ID, nie
 * ein Index — eine umsortierte Antwort hält dieselbe Aufnahme, eine fehlende fällt aufs Raster
 * zurück.
 *
 * SICHERHEIT (S11): Der Rückweg-Parameter `from` wählt eine Variante und nennt kein Ziel. Es
 * zählt allein der wörtliche Wert `ausschuss`; das Ziel ist fest `ausschussStepPath` aus der
 * numerischen Projekt-Id — nie der Parameterwert, `document.referrer` oder `navigate(-1)`. Sonst
 * führte ein präparierter Link einen angemeldeten Nutzer auf eine fremde Seite (offene
 * Weiterleitung). Weitergetragen wird er nur als Bool über `duplicateComparePath`.
 */
export function DuplicateComparePage() {
  const { projectId, photoId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const id = Number(projectId)
  const anchorId = Number(photoId)
  const fromAusschuss = searchParams.get('from') === 'ausschuss'

  const query = useDuplicateGroupQuery(id, anchorId)
  const decisionMutation = useDuplicateDecisionMutation(id, anchorId)
  const groupMutation = useDuplicateGroupDecisionMutation(id, anchorId)
  const confirmMutation = useDuplicateGroupConfirmMutation(id, anchorId)

  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const bestSharpness = useMemo(
    () => bestSharpnessIndices(items.map((item) => item.sharpness)),
    [items],
  )
  const bestExposure = useMemo(
    () => bestExposureIndices(items.map((item) => item.exposure)),
    [items],
  )

  const [enlargedId, setEnlargedId] = useState<number | null>(null)
  /** Die Aufnahme, deren Bildfläche nach dem Schließen der Großansicht den Fokus bekommt. */
  const [returnFocusId, setReturnFocusId] = useState<number | null>(null)
  const imageRefs = useRef(new Map<number, HTMLButtonElement>())

  /** Die laufenden Entscheidungen als MENGE von Foto-Ids: Verschiedene Aufnahmen entscheiden
   * unabhängig voneinander, eine seitenweite Sperre blockierte den zügigen Durchlauf. */
  const [decidingIds, setDecidingIds] = useState<ReadonlySet<number>>(new Set())
  const [lastGroupSaved, setLastGroupSaved] = useState(false)
  const confirmRunning = useRef(false)

  /* DIE SEITE BLEIBT BEIM GRUPPENWECHSEL MONTIERT — gleiche Route, anderer Parameter. Alle diese
     Zustände gehören zur alten Gruppe: Ohne Rücksetzung bliebe eine Kachel der neuen Gruppe
     gesperrt, deren Entscheidung nie lief, die Vergrößerung zeigte auf ein fremdes Foto, und
     Abschlussmeldung oder Fehler sprächen über eine andere Gruppe. */
  const resetConfirm = confirmMutation.reset
  const resetGroupDecision = groupMutation.reset
  useEffect(() => {
    setEnlargedId(null)
    setReturnFocusId(null)
    setDecidingIds(new Set())
    setLastGroupSaved(false)
    resetConfirm()
    resetGroupDecision()
  }, [anchorId, resetConfirm, resetGroupDecision])

  const enlargedItem = items.find((item) => item.photo.id === enlargedId)

  useEffect(() => {
    if (enlargedItem !== undefined || returnFocusId === null) {
      return
    }
    const bildflaeche = imageRefs.current.get(returnFocusId)
    bildflaeche?.focus()
    bildflaeche?.scrollIntoView?.({ block: 'nearest' })
    setReturnFocusId(null)
  }, [enlargedItem, returnFocusId])

  // Fehlt die vergrößerte Aufnahme in einer neuen Antwort, gilt das Raster - und zwar dauerhaft,
  // nicht bis sie in einer späteren Antwort zufällig wieder auftaucht.
  useEffect(() => {
    if (enlargedId !== null && enlargedItem === undefined) {
      setEnlargedId(null)
    }
  }, [enlargedId, enlargedItem])

  const previousGroupId = query.data?.previous_photo_id ?? null
  const nextGroupId = query.data?.next_photo_id ?? null
  const groupNav = useEdgeFocusHandoff(previousGroupId === null, nextGroupId === null)

  function closeEnlarged(): void {
    setReturnFocusId(enlargedId)
    setEnlargedId(null)
  }

  function handleDecide(decidedPhotoId: number, decision: DuplicateDecision): void {
    setDecidingIds((current) => new Set(current).add(decidedPhotoId))
    decisionMutation.mutate(
      { photoId: decidedPhotoId, decision },
      {
        onSettled: () => {
          setDecidingIds((current) => {
            const next = new Set(current)
            next.delete(decidedPhotoId)
            return next
          })
        },
      },
    )
  }

  function goToGroup(zielId: number | null): void {
    if (zielId === null) {
      return
    }
    groupNav.remember()
    // Push, kein `replace`: Der Zurück-Knopf des Browsers ist damit „vorherige Gruppe".
    navigate(duplicateComparePath(id, zielId, { fromAusschuss }))
  }

  const confirmBlocked =
    confirmMutation.isPending || groupMutation.isPending || decidingIds.size > 0

  function handleConfirm(): void {
    // Ein Doppelklick kommt schneller als das `disabled` des ersten: EIN Aufruf, nie zwei.
    if (confirmBlocked || confirmRunning.current) {
      return
    }
    confirmRunning.current = true
    confirmMutation.mutate(undefined, {
      onSettled: () => {
        confirmRunning.current = false
      },
      onSuccess: () => {
        if (nextGroupId !== null) {
          navigate(duplicateComparePath(id, nextGroupId, { fromAusschuss }))
        } else if (fromAusschuss) {
          navigate(ausschussStepPath(id))
        } else {
          setLastGroupSaved(true)
        }
      },
    })
  }

  // Ein `404` ist keine Störung, sondern die Aussage „zu dieser Aufnahme gibt es keine Gruppe".
  const istLeer =
    (query.isError && query.error instanceof ApiError && query.error.status === 404) ||
    (query.isSuccess && items.length === 0)
  const istGefuellt = query.isSuccess && items.length > 0

  const confirmLabel = confirmMutation.isPending
    ? 'Wird abgeschlossen…'
    : nextGroupId !== null
      ? 'Gruppe abschließen, nächste'
      : fromAusschuss
        ? 'Gruppe abschließen, zum Ausschuss'
        : 'Gruppe abschließen'

  return (
    <div className="flex flex-col gap-6">
      {fromAusschuss && (
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={ausschussStepPath(id)}>Zurück zum Ausschuss</Link>
        </Button>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        {istGefuellt ? (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-xl sm:text-2xl">
                Gruppe {query.data.position} von {query.data.total}{' '}
                <span className="text-base font-normal text-text sm:text-lg">
                  {`· ${items.length} Aufnahmen in ${formatSpan(query.data.span_seconds)}`}
                </span>
              </h1>
              {/* Nie die einzige Quelle der Zahl - beide stehen als Text im h1. */}
              <Progress
                aria-hidden="true"
                value={query.data.position}
                max={query.data.total}
                className="w-24 sm:w-40"
              />
            </div>
            {/* Am Rand `disabled` statt abwesend: Ein verschwindender Knopf verschöbe die übrigen
                unter dem Finger. Der zugängliche Name ist der sichtbare Text (WCAG 2.5.3). */}
            <div role="group" aria-label="Duplikat-Gruppen" className="flex flex-wrap gap-3">
              <Button
                ref={groupNav.previousRef}
                type="button"
                variant="outline"
                size="sm"
                className="h-11 sm:h-8"
                disabled={previousGroupId === null}
                onClick={() => goToGroup(previousGroupId)}
              >
                Vorherige Gruppe
              </Button>
              <Button
                ref={groupNav.nextRef}
                type="button"
                variant="outline"
                size="sm"
                className="h-11 sm:h-8"
                disabled={nextGroupId === null}
                onClick={() => goToGroup(nextGroupId)}
              >
                Nächste Gruppe
              </Button>
            </div>
          </>
        ) : (
          <h1 className="text-xl sm:text-2xl">Duplikate vergleichen</h1>
        )}
      </div>

      {query.isLoading && (
        <ul
          role="status"
          aria-label="Duplikat-Gruppe wird geladen…"
          className="grid grid-cols-2 items-start gap-3 sm:grid-cols-3"
        >
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li
              key={index}
              aria-hidden="true"
              className="flex flex-col gap-3 rounded-lg bg-elevated p-2 sm:p-3"
            >
              <Skeleton className="aspect-square w-full rounded-md" />
              <Skeleton className="h-3 w-full rounded-xs" />
              <Skeleton className="h-3 w-full rounded-xs" />
              <Skeleton className="h-3 w-full rounded-xs" />
              <Skeleton className="h-8 w-full rounded-sm" />
            </li>
          ))}
        </ul>
      )}

      {istLeer && <p className="text-sm text-text">{DUPLICATE_EMPTY_TEXT}</p>}

      {query.isError && !istLeer && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Fehler beim Laden der Duplikat-Gruppe.'}
        </Alert>
      )}

      {istGefuellt && (
        <>
          {/* Immer sichtbar, nie eingeklappt, kein `Alert` - und unmittelbar an der Handlung. */}
          <div className="flex max-w-3xl flex-col gap-2">
            <p className="text-sm text-text">{DUPLICATE_HINT_TEXT}</p>
            <p data-testid="duplicate-consequence" className="text-sm text-text">
              {DUPLICATE_CONSEQUENCE_TEXT}
            </p>
          </div>

          {/* Beschriftete Schaltflächen, keine Symbole: Beide setzen in EINEM Aufruf den Zustand
              jeder Aufnahme der Gruppe, und eine Glyphe sagte nicht, welche Richtung. */}
          <div className="flex flex-col gap-3">
            <div role="group" aria-label="Ganze Gruppe" className="flex flex-wrap gap-3">
              {(['keep', 'discard'] as const).map((wert) => (
                <Button
                  key={wert}
                  type="button"
                  variant="outline"
                  disabled={groupMutation.isPending}
                  busy={groupMutation.isPending}
                  onClick={() => groupMutation.mutate(wert)}
                >
                  {wert === 'keep' ? 'Alle behalten' : 'Alle in den Ausschuss'}
                </Button>
              ))}
            </div>
            {groupMutation.isError && (
              <Alert>
                {groupMutation.error instanceof ApiError
                  ? groupMutation.error.detail
                  : 'Die Entscheidung für die Gruppe konnte nicht gespeichert werden.'}
              </Alert>
            )}
          </div>

          {enlargedItem !== undefined ? (
            <DuplicateEnlargedView
              items={items}
              currentId={enlargedItem.photo.id}
              bestSharpness={bestSharpness}
              bestExposure={bestExposure}
              decidingIds={decidingIds}
              onSelect={setEnlargedId}
              onClose={closeEnlarged}
              onDecide={handleDecide}
            />
          ) : (
            <ul className="grid grid-cols-2 items-start gap-3 sm:grid-cols-3">
              {items.map((item, index) => (
                <DuplicatePhotoTile
                  key={item.photo.id}
                  photo={item.photo}
                  effectiveDecision={item.effective_decision}
                  keepPossible={item.keep_possible}
                  sharpness={item.sharpness}
                  exposure={item.exposure}
                  bestSharpness={bestSharpness.has(index)}
                  bestExposure={bestExposure.has(index)}
                  deciding={decidingIds.has(item.photo.id)}
                  onOpen={() => setEnlargedId(item.photo.id)}
                  onDecide={(decision) => handleDecide(item.photo.id, decision)}
                  imageRef={(element) => {
                    if (element === null) {
                      imageRefs.current.delete(item.photo.id)
                    } else {
                      imageRefs.current.set(item.photo.id, element)
                    }
                  }}
                />
              ))}
            </ul>
          )}

          {/* Der Abschluss schreibt den angezeigten Zustand fest, statt ihn zu ändern - es
              entsteht kein Gruppenzustand „erledigt". Gesperrt, solange eine Einzel- oder
              Gruppenentscheidung läuft: Er schriebe sonst gegen einen Stand, der gerade wechselt.
              Die Schaltfläche selbst ist die Wiederholung nach einem Fehler. */}
          <div className="flex flex-col items-start gap-3">
            <Button
              type="button"
              disabled={confirmBlocked}
              busy={confirmMutation.isPending}
              onClick={handleConfirm}
            >
              {confirmLabel}
            </Button>
            {/* Die Live-Region steht im gefüllten Zustand IMMER da, nur ihr Text wechselt: Eine
                Region, die erst zusammen mit ihrem Text erscheint, sagen Screenreader oft nicht an. */}
            <p aria-live="polite" data-testid="duplicate-last-group" className="text-sm text-text">
              {lastGroupSaved ? LAST_GROUP_TEXT : ''}
            </p>
            {confirmMutation.isError && (
              <Alert>
                {confirmMutation.error instanceof ApiError
                  ? confirmMutation.error.detail
                  : 'Die Gruppe konnte nicht abgeschlossen werden.'}
              </Alert>
            )}
          </div>
        </>
      )}
    </div>
  )
}
