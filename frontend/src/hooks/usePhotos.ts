import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { listDraftAlternatives, listPhotos } from '../api/photos'
import { deleteRating, setFavorite, setRating } from '../api/ratings'
import type {
  PhotoListOut,
  PhotoOut,
  RatingFilter,
  RatingStatus,
  RatingWriteOut,
} from '../api/types'
import { insertDraftPhoto } from '../utils/albumDraft'

/**
 * Batch-Groesse fuer das Foto-Listing: Fotos werden paginiert geladen (Batches statt Gesamt-Reload
 * bei tausenden Fotos). Grid- und Einzelbild-/Swipe-Ansicht teilen sich denselben Query-Key (siehe
 * unten) und damit dieselben bereits geladenen Batches - "Navigation/Shortcuts operieren auf der
 * zuletzt geladenen, gefilterten Foto-ID-Liste", kein separater "naechstes Foto"-Endpunkt noetig.
 */
export const PHOTOS_PAGE_SIZE = 60

function photosQueryKey(projectId: number, ratingStatus?: RatingFilter) {
  return ['photos', projectId, ratingStatus ?? null] as const
}

/**
 * Der Album-Entwurf: bewusst unter demselben ['photos', projectId, ...]-Praefix wie
 * photosQueryKey oben - die breite Invalidierung der Bewertungsmutationen trifft ihn damit mit,
 * wenn anderswo bewertet wird (Raster, Einzelbild, Vergleich).
 *
 * Die Entwurfsansicht selbst benutzt genau deshalb NICHT jene Mutationen, sondern
 * `useDraftDecisionMutation`: ein Neuladen der Entwurfsliste bei jeder Entscheidung risse die
 * gerade gestrichene Kachel aus der Liste.
 */
const DRAFT_QUERY_SEGMENT = 'draft'

function draftQueryKey(projectId: number) {
  return ['photos', projectId, DRAFT_QUERY_SEGMENT] as const
}

/**
 * Der Album-Entwurf DIESES Nutzers. KEIN Leseparameter im Schluessel: welche Fotos er umfasst,
 * ist eine Eigenschaft des Laufs und der eigenen Entscheidungen, keine der Anfrage - eine zweite
 * Variante desselben Projekts kann es nicht geben.
 */
export function useDraftQuery(projectId: number) {
  return useQuery({
    queryKey: draftQueryKey(projectId),
    queryFn: () => listPhotos(projectId, { draft: true }),
  })
}

/**
 * Schreibt den Zustand EINER Bewertungszeile in eine bereits geladene Fotoliste fort - rein, ohne
 * Cache und ohne Netz.
 *
 * Der betroffene Eintrag wird ueber `user_id` der SERVERANTWORT getroffen, nie geraten; der
 * `username` fuellt allein das Feld, ueber das `utils/ownRating.ts` den eigenen Zustand spaeter
 * wiederfindet. Eine geleerte Zeile (`status: null` und kein Kennzeichen) verschwindet, statt als
 * Bewertung ohne Inhalt stehenzubleiben.
 *
 * Fotos ohne Bezug behalten ihre OBJEKTREFERENZ - ihre Kacheln rendern dadurch nicht neu.
 */
export function applyWrittenRating(
  list: PhotoListOut,
  written: RatingWriteOut,
  username: string,
): PhotoListOut {
  return {
    ...list,
    items: list.items.map((item) => {
      if (item.id !== written.photo_id) {
        return item
      }
      const others = item.ratings.filter((rating) => rating.user_id !== written.user_id)
      if (written.status === null && !written.favorite) {
        return { ...item, ratings: others }
      }
      return {
        ...item,
        ratings: [
          ...others,
          {
            user_id: written.user_id,
            username,
            status: written.status,
            favorite: written.favorite,
          },
        ],
      }
    }),
  }
}

// Derselbe ['photos', projectId]-Praefix wie oben, und hier ist er nicht Bequemlichkeit, sondern
// Bedingung: die Alternativen sind eine ZWEITE Query ueber demselben Datensatz auf demselben
// Bildschirm. Dasselbe Foto kann in beiden Listen stehen; wird es in der einen bewertet, muss die
// andere denselben Zustand zeigen. Genau das leistet die bestehende breite Invalidierung - ohne den
// Praefix stuenden zwei Wahrheiten ueber dasselbe Foto nebeneinander.
//
// DAS BEZUGSBILD GEHOERT IN DEN SCHLUESSEL: An ihm haengen die Menge (sein Entwurf wird abgezogen)
// UND die Reihenfolge (seine Motive ordnen). Zwei Bilder desselben Events unter einem Schluessel
// zeigten dem zweiten Dialog die Alternativen des ersten.
function draftAlternativesQueryKey(projectId: number, eventId: number, photoId: number) {
  return ['photos', projectId, 'alternatives', eventId, photoId] as const
}

export interface DraftAlternativesQueryParams {
  eventId: number
  photoId: number
  /** Der Request laeuft ausschliesslich im GEOEFFNETEN Dialog - eine Abfrage je geoeffnetem Bild,
   * nie eine je Kachel. */
  enabled: boolean
  pageSize?: number
}

export function useDraftAlternativesQuery(
  projectId: number,
  { eventId, photoId, enabled, pageSize = PHOTOS_PAGE_SIZE }: DraftAlternativesQueryParams,
) {
  return useInfiniteQuery({
    queryKey: draftAlternativesQueryKey(projectId, eventId, photoId),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listDraftAlternatives(projectId, {
        eventId,
        photoId,
        limit: pageSize,
        offset: pageParam,
      }),
    initialPageParam: 0,
    // Identisch zu usePhotoSequenceQuery: der naechste Offset ist die Zahl der bereits geladenen
    // Eintraege, und `total` ist die Restmenge (nicht die Seitengroesse).
    getNextPageParam: (lastPage: PhotoListOut, allPages: PhotoListOut[]) => {
      const loaded = allPages.reduce((sum, loadedPage) => sum + loadedPage.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
    enabled,
  })
}

export function usePhotoSequenceQuery(
  projectId: number,
  ratingStatus?: RatingFilter,
  pageSize: number = PHOTOS_PAGE_SIZE,
) {
  return useInfiniteQuery({
    queryKey: photosQueryKey(projectId, ratingStatus),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listPhotos(projectId, { ratingStatus, limit: pageSize, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: PhotoListOut, allPages: PhotoListOut[]) => {
      const loaded = allPages.reduce((sum, loadedPage) => sum + loadedPage.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
  })
}

/**
 * Die Albumentscheidung AUS DER ENTWURFSANSICHT - „Im Album" ⇄ „Gestrichen".
 *
 * Sie schreibt dieselbe Bewertung wie `useSetRatingMutation`, behandelt den Cache danach aber
 * anders, und das ist ihr ganzer Zweck (ADR 0098 Punkt 6): Sie schreibt den betroffenen Eintrag
 * im Entwurfs-Cache FORT und invalidiert ausschließlich die ÜBRIGEN Fotoabfragen des Projekts.
 *
 * Ohne diese Trennung träfe die breite Invalidierung den Entwurfsschlüssel mit: Ein gerade
 * gestrichenes Bild fiele beim Neuladen aus der Antwortmenge, die Kachel verschwände unter dem
 * Finger, und der nächste Druck landete auf einem anderen Bild. Ein gestrichenes Bild bleibt
 * stattdessen an seiner Stelle stehen.
 */
export function useDraftDecisionMutation(projectId: number, username: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, status }: { photoId: number; status: RatingStatus }) =>
      setRating(photoId, status),
    onSuccess: (written) => {
      if (username !== null) {
        queryClient.setQueryData<PhotoListOut>(draftQueryKey(projectId), (current) =>
          current === undefined ? current : applyWrittenRating(current, written, username),
        )
      }
      // Derselbe breite Präfix wie überall - aber der Entwurfsschlüssel ist ausgenommen, weil
      // sein Stand oben bereits geschrieben wurde.
      void queryClient.invalidateQueries({
        queryKey: ['photos', projectId],
        predicate: (query) => query.queryKey[2] !== DRAFT_QUERY_SEGMENT,
      })
    },
  })
}

/**
 * Der Austausch EINES Bildes gegen eine Alternative - ZWEI Schreibvorgänge in einer Geste.
 *
 * Reihenfolge verbindlich (ADR 0098): erst das Bezugsbild streichen, dann die Alternative
 * aufnehmen. Umgekehrt stünde zwischen den beiden Anfragen ein Bild zu viel im Album, und
 * bräche die zweite ab, wäre der Entwurf um eines gewachsen statt unverändert geblieben.
 *
 * Danach derselbe Cache-Umgang wie bei `useDraftDecisionMutation` und aus demselben Grund: Die
 * Entwurfsliste wird NICHT neu geladen. Das ersetzte Bild bleibt an seiner Stelle und trägt
 * „gestrichen"; die Alternative wird über `insertDraftPhoto` an ihren chronologischen Platz
 * geschrieben - denselben, den der Server ihr beim nächsten vollständigen Laden gäbe.
 */
export function useDraftExchangeMutation(projectId: number, username: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ replaced, chosen }: { replaced: PhotoOut; chosen: PhotoOut }) => {
      const struck = await setRating(replaced.id, 'rejected')
      const taken = await setRating(chosen.id, 'album_worthy')
      return { struck, taken }
    },
    onSuccess: ({ struck, taken }, { chosen }) => {
      if (username !== null) {
        queryClient.setQueryData<PhotoListOut>(draftQueryKey(projectId), (current) => {
          if (current === undefined) {
            return current
          }
          // Erst aufnehmen, dann beide Bewertungen fortschreiben: `applyWrittenRating` trifft nur
          // Einträge, die bereits in der Liste stehen.
          const withChosen = insertDraftPhoto(current, chosen)
          return applyWrittenRating(
            applyWrittenRating(withChosen, struck, username),
            taken,
            username,
          )
        })
      }
      void queryClient.invalidateQueries({
        queryKey: ['photos', projectId],
        predicate: (query) => query.queryKey[2] !== DRAFT_QUERY_SEGMENT,
      })
    },
  })
}

export function useSetRatingMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, status }: { photoId: number; status: RatingStatus }) =>
      setRating(photoId, status),
    onSuccess: () => {
      // Ohne Filter im Key: invalidiert alle Filtervarianten dieses Projekts, da eine
      // Bewertungsaenderung die Zugehoerigkeit zu MEHREREN Filtern gleichzeitig aendern kann
      // (z.B. raus aus "unbewertet", rein in "favorite").
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}

export function useDeleteRatingMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => deleteRating(photoId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}

/**
 * Das Favoriten-Kennzeichen - eigene Mutation auf einem eigenen Endpunkt, damit die
 * Albumentscheidung dabei unberührt bleibt.
 *
 * Dieselbe breite Invalidierung wie bei der Albumentscheidung: Das Kennzeichen entscheidet über
 * die Zugehörigkeit zum Filter "Favorit", und der Filter steckt im Query-Key.
 */
export function useSetFavoriteMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, favorite }: { photoId: number; favorite: boolean }) =>
      setFavorite(photoId, favorite),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}
