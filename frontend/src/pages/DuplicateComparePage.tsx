import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { DuplicateDecision } from '../api/types'
import { DuplicatePhotoTile } from '../components/DuplicatePhotoTile'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import {
  useDuplicateDecisionMutation,
  useDuplicateGroupDecisionMutation,
  useDuplicateGroupQuery,
} from '../hooks/useDuplicates'

const SKELETON_TILE_COUNT = 4

/**
 * Die unveränderliche Hinweiszeile (AK4).
 *
 * Sie benennt einen BESTEHENDEN Zustand, keine ausstehende Entscheidung: Jede Aufnahme trägt beim
 * Öffnen bereits das, was ohne weiteres Zutun eintritt. Die Zeile darf deshalb weder behaupten, es
 * liege noch keine Entscheidung vor, noch zusichern, dass „unentschiedene" Aufnahmen erhalten
 * bleiben — ein unentschiedener Duplikat-Verlierer fällt am Gate heraus, und ein Satz wie „ohne
 * Entscheidung bleibt alles" wäre eine Zusage, die die Ansicht nicht halten kann.
 */
export const DUPLICATE_HINT_TEXT =
  'Der angezeigte Zustand jeder Aufnahme gilt, falls du ihn nicht änderst.'

/**
 * Die Folge von „behalten", an der Handlung selbst (Auflage S4).
 *
 * „Behalten" ist keine ansichtsinterne Buchführung: Die Aufnahme läuft danach in die
 * Kriterien-Bewertung und, bei erteilter Einwilligung, in die Cloud-Klassifizierung. Steht das
 * nicht hier, trifft der Nutzer eine Entscheidung über einen Datenabfluss, von dem er nichts
 * weiß.
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

/**
 * Alle Aufnahmen einer Duplikat-Gruppe nebeneinander — je Aufnahme einzeln entscheidbar.
 *
 * DAS RASTER BRICHT UM, STATT DIE BILDER ZU VERKLEINERN: zwei Spalten schmal, drei breit. Die
 * Kachelbreite hängt damit an der Fensterbreite, nicht an der Mitgliederzahl — eine Serie mit
 * sieben Aufnahmen zeigt dieselben Kacheln wie eine mit dreien, nur in mehr Zeilen. jsdom kennt
 * keine Layout-Engine; gemessen wird das im Prüfstack (`e2e/tests/grid-columns.spec.ts`).
 *
 * DIE VERGRÖSSERUNG IST KEIN DIALOG: Die gewählte Kachel spannt die Rasterbreite, die übrigen
 * bleiben darüber und darunter stehen. Genau das ist der Zweck — man vergleicht, man betrachtet
 * nicht einzeln. Ein Dialog nähme die Gruppe aus dem Blick, und ein Dialog fängt den Fokus, was
 * das Blättern innerhalb der Gruppe zu einer zweiten Bedienebene machte.
 */
export function DuplicateComparePage() {
  const { projectId, photoId } = useParams()
  const navigate = useNavigate()
  const id = Number(projectId)
  const anchorId = Number(photoId)

  const query = useDuplicateGroupQuery(id, anchorId)
  const decisionMutation = useDuplicateDecisionMutation(id, anchorId)
  const groupMutation = useDuplicateGroupDecisionMutation(id, anchorId)

  const items = query.data?.items ?? []

  /** Die vergrößerte Aufnahme als FOTO-ID, nie als Index: Ein Index zeigte nach einem Neuladen
   * der Gruppe auf eine andere Aufnahme, ohne dass etwas auffiele. `null` heißt „nichts
   * vergrößert" — es ist höchstens eine. */
  const [enlargedId, setEnlargedId] = useState<number | null>(null)

  /** Die laufenden Entscheidungen als MENGE von Foto-Ids: Verschiedene Aufnahmen entscheiden
   * unabhängig voneinander, und eine seitenweite Sperre blockierte den zügigen Durchlauf, den
   * diese Ansicht gerade ermöglichen soll. */
  const [decidingIds, setDecidingIds] = useState<ReadonlySet<number>>(new Set())

  /* DIE SEITE BLEIBT BEIM GRUPPENWECHSEL MONTIERT — gleiche Route, anderer Parameter. Beide
     Zustände zeigen auf Foto-Ids der alten Gruppe und müssen deshalb zurückgesetzt werden: Ohne
     das bliebe eine Kachel der neuen Gruppe gesperrt, deren Entscheidung nie lief, und die
     Vergrößerung zeigte auf ein Foto, das hier nicht vorkommt. */
  useEffect(() => {
    setEnlargedId(null)
    setDecidingIds(new Set())
  }, [anchorId])

  const enlargedIndex = items.findIndex((item) => item.photo.id === enlargedId)

  const moveEnlarged = useCallback(
    (schritt: -1 | 1) => {
      setEnlargedId((current) => {
        const index = items.findIndex((item) => item.photo.id === current)
        if (index === -1) {
          return current
        }
        // KEIN Rundlauf: Am ersten bzw. letzten Mitglied bleibt die Vergrößerung stehen. Ein
        // Sprung ans andere Ende wäre in einer Vergleichsansicht ein verlorener Überblick.
        const ziel = index + schritt
        return ziel < 0 || ziel >= items.length ? current : (items[ziel]?.photo.id ?? current)
      })
    },
    [items],
  )

  // Esc verkleinert, Pfeil links/rechts blättert. Das ersetzt KEINEN nativen Tastatur-Handler:
  // Enter und Leertaste wirken weiterhin über das `<button>` der Kachel selbst. Der Effekt läuft
  // nur, solange etwas vergrößert ist - sonst hörte die Seite dauerhaft auf Tasten mit, die sie
  // nichts angehen.
  useEffect(() => {
    if (enlargedId === null) {
      return
    }
    function handleKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        setEnlargedId(null)
      } else if (event.key === 'ArrowLeft') {
        moveEnlarged(-1)
      } else if (event.key === 'ArrowRight') {
        moveEnlarged(1)
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [enlargedId, moveEnlarged])

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

  // Ein `404` ist keine Störung, sondern die Aussage „zu dieser Aufnahme gibt es keine Gruppe".
  // Ein Fehler-Alert behauptete einen Vorfall und böte „Erneut versuchen" für etwas an, das beim
  // nächsten Versuch genauso ausgeht.
  const istLeer = query.isError && query.error instanceof ApiError && query.error.status === 404

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        {/* DIE GRUPPENNAVIGATION LIEGT IM SEITENKOPF UND IST IMMER SICHTBAR — ausdrücklich nicht
            an die Bildvergrößerung gekoppelt: Der Durchgang ist eine Aussage über die ANSICHT,
            nicht über eine vergrößerte Aufnahme, und an die Vergrößerungssteuerung gehängt wäre
            er ohne Vergrößerung unerreichbar.

            Am Rand `disabled` statt abwesend: Ein verschwindender Knopf verschöbe die übrigen
            unter dem Finger. Die zugänglichen Namen unterscheiden sich bewusst von den
            `Vorherige/Nächste Aufnahme der Gruppe` der Vergrößerung, die gleichzeitig im Dokument
            stehen können. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl sm:text-2xl">
            {query.isSuccess
              ? `Duplikat-Gruppe ${query.data.position} von ${query.data.total}`
              : 'Duplikate vergleichen'}
          </h1>
          {query.isSuccess && (
            <div role="group" aria-label="Duplikat-Gruppen" className="flex gap-3">
              {(
                [
                  ['Zur vorherigen Gruppe', 'Zurück', query.data.previous_photo_id],
                  ['Zur nächsten Gruppe', 'Vor', query.data.next_photo_id],
                ] as const
              ).map(([name, beschriftung, ziel]) => (
                <Button
                  key={name}
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={ziel === null}
                  aria-label={name}
                  // Push, kein `replace`: Der Zurück-Knopf des Browsers ist damit „vorherige
                  // Gruppe" statt „raus aus dem Durchgang".
                  onClick={() =>
                    ziel !== null && navigate(`/projects/${id}/photos/${ziel}/duplicates`)
                  }
                >
                  {beschriftung}
                </Button>
              ))}
            </div>
          )}
        </div>
        <p className="text-sm text-text">{DUPLICATE_HINT_TEXT}</p>
        <p data-testid="duplicate-consequence" className="text-sm text-text">
          {DUPLICATE_CONSEQUENCE_TEXT}
        </p>
      </div>

      {query.isLoading && (
        <ul
          role="status"
          aria-label="Duplikat-Gruppe wird geladen…"
          className="grid grid-cols-2 gap-3 sm:grid-cols-3"
        >
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
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

      {query.isSuccess && items.length === 0 && (
        <p className="text-sm text-text">{DUPLICATE_EMPTY_TEXT}</p>
      )}

      {query.isSuccess && items.length > 0 && (
        <>
          {/* Beschriftete Schaltflächen, keine Symbole: Beide setzen in EINEM Aufruf den Zustand
              jeder Aufnahme der Gruppe, und eine Glyphe sagte nicht, welche Richtung. */}
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

          <ul className="grid grid-cols-2 items-start gap-3 sm:grid-cols-3">
            {items.map((item) => (
              <DuplicatePhotoTile
                key={item.photo.id}
                photo={item.photo}
                effectiveDecision={item.effective_decision}
                keepPossible={item.keep_possible}
                enlarged={item.photo.id === enlargedId}
                deciding={decidingIds.has(item.photo.id)}
                onToggle={() =>
                  setEnlargedId((current) => (current === item.photo.id ? null : item.photo.id))
                }
                onDecide={(decision) => handleDecide(item.photo.id, decision)}
                controls={
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={enlargedIndex <= 0}
                      aria-label="Vorherige Aufnahme der Gruppe"
                      onClick={() => moveEnlarged(-1)}
                    >
                      Zurück
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={enlargedIndex === items.length - 1}
                      aria-label="Nächste Aufnahme der Gruppe"
                      onClick={() => moveEnlarged(1)}
                    >
                      Vor
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label="Vergrößerung schließen"
                      onClick={() => setEnlargedId(null)}
                    >
                      Schließen
                    </Button>
                  </div>
                }
              />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
