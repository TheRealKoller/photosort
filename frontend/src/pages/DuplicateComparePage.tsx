import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { DuplicateDecision } from '../api/types'
import { DuplicateGroupActions } from '../components/DuplicateGroupActions'
import { DuplicateGroupGrid } from '../components/DuplicateGroupGrid'
import { DuplicateGroupHeader } from '../components/DuplicateGroupHeader'
import { DuplicateGroupNotices } from '../components/DuplicateGroupNotices'
import { Button } from '../components/ui/button'
import {
  useDuplicateDecisionMutation,
  useDuplicateGroupConfirmMutation,
  useDuplicateGroupDecisionMutation,
  useDuplicateGroupQuery,
} from '../hooks/useDuplicates'
import { useEdgeFocusHandoff } from '../hooks/useEdgeFocusHandoff'
import { ausschussStepPath, duplicateComparePath } from '../utils/projectRoutes'

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
 * SICHERHEIT: Der Rückweg-Parameter `from` wählt eine Variante und nennt kein Ziel. Es
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

  const items = query.data?.items ?? []

  const [enlargedId, setEnlargedId] = useState<number | null>(null)
  /** Die Aufnahme, deren Bildfläche nach dem Schließen der Großansicht den Fokus bekommt. */
  const [returnFocusId, setReturnFocusId] = useState<number | null>(null)
  const imageRefs = useRef(new Map<number, HTMLButtonElement>())

  /** Die laufenden Entscheidungen als MENGE von Foto-Ids: Verschiedene Aufnahmen entscheiden
   * unabhängig voneinander, eine seitenweite Sperre blockierte den zügigen Durchlauf. */
  const [decidingIds, setDecidingIds] = useState<ReadonlySet<number>>(new Set())
  const [lastGroupSaved, setLastGroupSaved] = useState(false)
  /** Lokal gemerkt: Nach einem erfolgreichen `keep` liefert die Antwort `auto_decided: false`,
   *  und die Rücknahme wird angesagt, statt nur sichtbar zu verschwinden. Beim Gruppenwechsel
   *  zurückgesetzt wie die übrigen Seitenzustände. */
  const [autoUndone, setAutoUndone] = useState(false)
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
    setAutoUndone(false)
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
        onSuccess: () => {
          // Nur eine AUTOMATISCH entschiedene Gruppe wird zurückgenommen; in einer offenen
          // Gruppe ist „Behalten“ eine gewöhnliche Entscheidung ohne Ansage.
          if (decision === 'keep' && query.data?.auto_decided === true) {
            setAutoUndone(true)
          }
        },
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

  const autoDecided = query.data?.auto_decided === true && !autoUndone
  const autoUndoneAndOpen = query.data?.auto_decided === false && autoUndone

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

      <DuplicateGroupHeader
        group={istGefuellt ? query.data : null}
        previousRef={groupNav.previousRef}
        nextRef={groupNav.nextRef}
        onPrevious={() => goToGroup(previousGroupId)}
        onNext={() => goToGroup(nextGroupId)}
      />

      <DuplicateGroupNotices
        filled={istGefuellt}
        autoDecided={autoDecided}
        autoUndoneAndOpen={autoUndoneAndOpen}
        empty={istLeer}
        loadError={query.isError && !istLeer ? query.error : null}
        onRetry={() => void query.refetch()}
      />

      <DuplicateGroupActions
        filled={istGefuellt}
        groupPending={groupMutation.isPending}
        groupError={groupMutation.isError ? groupMutation.error : null}
        autoDecided={autoDecided}
        confirmBlocked={confirmBlocked}
        confirmPending={confirmMutation.isPending}
        confirmLabel={confirmLabel}
        lastGroupSaved={lastGroupSaved}
        confirmError={confirmMutation.isError ? confirmMutation.error : null}
        onGroupDecision={(decision) => groupMutation.mutate(decision)}
        onConfirm={handleConfirm}
      >
        <DuplicateGroupGrid
          loading={query.isLoading}
          items={items}
          enlargedItem={enlargedItem}
          decidingIds={decidingIds}
          onOpen={setEnlargedId}
          onClose={closeEnlarged}
          onSelect={setEnlargedId}
          onDecide={handleDecide}
          imageRef={(photoIdWert, element) => {
            if (element === null) {
              imageRefs.current.delete(photoIdWert)
            } else {
              imageRefs.current.set(photoIdWert, element)
            }
          }}
        />
      </DuplicateGroupActions>
    </div>
  )
}
