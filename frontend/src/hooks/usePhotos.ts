import type { QueryClient } from '@tanstack/react-query'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  exchangeDraftPhoto,
  getAlbumDraft,
  listDraftAlternatives,
  listPhotos,
  undoDraftExchange,
} from '../api/photos'
import { deleteRating, setFavorite, setRating } from '../api/ratings'
import type {
  AlbumDraftOut,
  DraftAlternativesOut,
  DraftExchangeUndoIn,
  PhotoListOut,
  PhotoOut,
  RatingFilter,
  RatingStatus,
  RatingWriteOut,
} from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { draftMembership, insertDraftPhoto } from '../utils/albumDraft'
import { ownRatingStatus } from '../utils/ownRating'

/**
 * Batch-Groesse fuer das Foto-Listing: Fotos werden paginiert geladen (Batches statt Gesamt-Reload
 * bei tausenden Fotos). Grid- und Einzelbild-/Swipe-Ansicht teilen sich denselben Query-Key (siehe
 * unten) und damit dieselben bereits geladenen Batches - "Navigation/Shortcuts operieren auf der
 * zuletzt geladenen, gefilterten Foto-ID-Liste", kein separater "naechstes Foto"-Endpunkt noetig.
 */
export const PHOTOS_PAGE_SIZE = 60

function photosQueryKey(
  projectId: number,
  ratingStatus?: RatingFilter,
  personIds: readonly number[] = [],
) {
  return ['photos', projectId, ratingStatus ?? null, ...personIds] as const
}

/**
 * Der Album-Entwurf: bewusst unter demselben ['photos', projectId, ...]-Praefix wie
 * photosQueryKey oben - die breite Invalidierung der Bewertungsmutationen trifft ihn damit mit,
 * wenn anderswo bewertet wird (Raster, Einzelbild, Endauswahl).
 *
 * Die Entwurfsansicht selbst benutzt genau deshalb NICHT jene Mutationen, sondern die eigenen
 * unten: Sie schreiben den Serverzustand in den geladenen Entwurf, statt ihn neu zu laden - das
 * hielte weder Scrollposition noch Fokus.
 */
const DRAFT_QUERY_SEGMENT = 'draft'

/**
 * SICHERHEIT (S4): Entwurfs- und Alternativen-Schlüssel tragen die angemeldete Identität HINTER
 * dem Präfix `['photos', projectId]` (Muster `projectStatsQueryKey`). Der `QueryClient` überlebt
 * die Anmeldung eines zweiten Nutzers im selben Tab; ohne die Identität sähe dieser bis zum
 * Abschluss des Neuladens den Entwurf des ersten, samt „Deine Eingriffe". Hinter dem Präfix, damit
 * die breite Invalidierung beide weiter trifft und die Ausnahme des Entwurfsschlüssels über das
 * dritte Glied greift. `decodeUsername` dient nur der Cache-Unterscheidung, nie einer
 * Zugriffsentscheidung.
 */
function currentIdentity(): string | null {
  const token = getToken()
  return token ? decodeUsername(token) : null
}

export function draftQueryKey(projectId: number) {
  return ['photos', projectId, DRAFT_QUERY_SEGMENT, currentIdentity()] as const
}

/** Der eigene Entwurfsschlüssel bleibt von der breiten Invalidierung ausgenommen - sein Stand ist
 * bereits der, den der Server jetzt gäbe. */
function invalidateAllButTheDraft(queryClient: QueryClient, projectId: number) {
  void queryClient.invalidateQueries({
    queryKey: ['photos', projectId],
    predicate: (query) => query.queryKey[2] !== DRAFT_QUERY_SEGMENT,
  })
}

/**
 * Der Album-Entwurf DIESES Nutzers samt Eventliste. KEIN Leseparameter im Schluessel: welche
 * Fotos er umfasst, ist eine Eigenschaft des Laufs und der eigenen Entscheidungen. Geladen wird er
 * beim Öffnen genau einmal; jeder Handgriff schreibt danach in den Cache.
 */
export function useDraftQuery(projectId: number) {
  return useQuery({
    queryKey: draftQueryKey(projectId),
    queryFn: () => getAlbumDraft(projectId),
  })
}

/**
 * Schreibt den Zustand EINER Bewertungszeile in den geladenen Entwurf fort - rein, ohne Cache und
 * ohne Netz. Danach ist der Entwurf die Antwort, die der Server jetzt gäbe.
 *
 * Der betroffene Eintrag wird ueber `user_id` der SERVERANTWORT getroffen, nie geraten; der
 * `username` fuellt allein das Feld, ueber das `utils/ownRating.ts` den eigenen Zustand spaeter
 * wiederfindet. Eine geleerte Zeile (`status: null` und kein Kennzeichen) verschwindet, statt als
 * Bewertung ohne Inhalt stehenzubleiben. Ein Foto, das damit nicht mehr zur Antwortmenge gehört
 * (`draftMembership === 'out'`), verlässt den Entwurf.
 *
 * Fotos ohne Bezug behalten ihre OBJEKTREFERENZ - ihre Kacheln rendern dadurch nicht neu.
 */
export function applyWrittenRating(
  draft: AlbumDraftOut,
  written: RatingWriteOut,
  username: string,
): AlbumDraftOut {
  const items: PhotoOut[] = []
  for (const item of draft.items) {
    if (item.id !== written.photo_id) {
      items.push(item)
      continue
    }
    const others = item.ratings.filter((rating) => rating.user_id !== written.user_id)
    const ratings =
      written.status === null && !written.favorite
        ? others
        : [
            ...others,
            {
              user_id: written.user_id,
              username,
              status: written.status,
              favorite: written.favorite,
            },
          ]
    const next = { ...item, ratings }
    if (draftMembership(next, ownRatingStatus(ratings, username)) !== 'out') {
      items.push(next)
    }
  }
  return { ...draft, items }
}

// Derselbe ['photos', projectId]-Praefix wie oben, und hier ist er nicht Bequemlichkeit, sondern
// Bedingung: die Alternativen sind eine ZWEITE Query ueber demselben Datensatz auf demselben
// Bildschirm. Wird ein Foto im Entwurf entschieden, muss die Kandidatenliste denselben Zustand
// zeigen - genau das leistet die breite Invalidierung.
//
// DAS BEZUGSBILD, DIE SEITENGROESSE UND `nearest` GEHOEREN IN DEN SCHLUESSEL: Am Bezugsbild
// haengen Menge und Reihenfolge; Band (Fenster `nearest`, mit Bezugsbild), Dialog (mit
// Bezugsbild, seitenweise) und Hinzufuegen-Feld (acht, ohne) holten unter einem gemeinsamen
// Schluessel dieselbe Cache-Zeile.
export function draftAlternativesQueryKey(
  projectId: number,
  eventId: number,
  photoId: number | null,
  pageSize: number,
  nearest: number | null = null,
) {
  return [
    'photos',
    projectId,
    'alternatives',
    currentIdentity(),
    eventId,
    photoId,
    pageSize,
    nearest,
  ] as const
}

export interface DraftAlternativesQueryParams {
  eventId: number
  /** Das Bezugsbild; `null` fuer das Hinzufuegen-Feld, das nach Qualitaet ordnet. */
  photoId: number | null
  /** Der Request laeuft ausschliesslich im GEOEFFNETEN Band, Panel oder Dialog - eine Abfrage je
   * geoeffnetem Bild, nie eine je Kachel. */
  enabled: boolean
  pageSize?: number
  /** Das Band: EIN vom Server geschnittenes Fenster der `nearest` zeitlich naechsten
   * Alternativen, ohne Folgeseiten. Nur zusammen mit `photoId`. */
  nearest?: number
}

export function useDraftAlternativesQuery(
  projectId: number,
  { eventId, photoId, enabled, pageSize = PHOTOS_PAGE_SIZE, nearest }: DraftAlternativesQueryParams,
) {
  return useInfiniteQuery({
    queryKey: draftAlternativesQueryKey(projectId, eventId, photoId, pageSize, nearest ?? null),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listDraftAlternatives(
        projectId,
        nearest !== undefined && photoId !== null
          ? { eventId, photoId, nearest }
          : {
              eventId,
              ...(photoId === null ? {} : { photoId }),
              limit: pageSize,
              offset: pageParam,
            },
      ),
    initialPageParam: 0,
    // Identisch zu usePhotoSequenceQuery: der naechste Offset ist die Zahl der bereits geladenen
    // Eintraege, und `total` ist die Restmenge (nicht die Seitengroesse). Das Band hat nie eine
    // Folgeseite - sein Fenster ist vollstaendig.
    getNextPageParam: (lastPage: DraftAlternativesOut, allPages: DraftAlternativesOut[]) => {
      if (nearest !== undefined) {
        return undefined
      }
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
  personIds: readonly number[] = [],
) {
  return useInfiniteQuery({
    queryKey: photosQueryKey(projectId, ratingStatus, personIds),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listPhotos(projectId, { ratingStatus, limit: pageSize, offset: pageParam, personIds }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: PhotoListOut, allPages: PhotoListOut[]) => {
      const loaded = allPages.reduce((sum, loadedPage) => sum + loadedPage.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
  })
}

/**
 * Ein Handgriff AUS DER ENTWURFSANSICHT an EINEM Foto: Streichen, Wieder aufnehmen, Hinzufügen und
 * Rückgängig nach dem Streichen. `status: null` nimmt die eigene Entscheidung zurück (`DELETE`).
 * `insert` ist ein Foto, das (noch oder wieder) nicht im Entwurf steht: aus dem Hinzufügen-Panel
 * oder beim Rückgängig eines Streichens, das es aus der Antwortmenge genommen hat.
 *
 * Sie schreibt dieselbe Bewertung wie `useSetRatingMutation`, behandelt den Cache danach aber
 * anders, und das ist ihr ganzer Zweck: Sie setzt den Serverzustand in den Entwurfs-Cache ein
 * (nicht optimistisch, kein Rollback-Pfad) und invalidiert ausschließlich die ÜBRIGEN Fotoabfragen
 * des Projekts. Ein Neuladen des Entwurfs hielte weder Scrollposition noch Fokus.
 */
export function useDraftDecisionMutation(projectId: number, username: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      photoId,
      status,
    }: {
      photoId: number
      status: RatingStatus | null
      insert?: PhotoOut
    }) => (status === null ? deleteRating(photoId) : setRating(photoId, status)),
    onSuccess: (written, { insert }) => {
      if (username !== null) {
        queryClient.setQueryData<AlbumDraftOut>(draftQueryKey(projectId), (current) => {
          if (current === undefined) {
            return current
          }
          // Erst einfügen, dann fortschreiben: `applyWrittenRating` trifft nur Einträge, die
          // bereits im Entwurf stehen.
          const withInsert = insert === undefined ? current : insertDraftPhoto(current, insert)
          return applyWrittenRating(withInsert, written, username)
        })
      }
      invalidateAllButTheDraft(queryClient, projectId)
    },
  })
}

/**
 * Der Tausch EINES Bildes gegen eine Alternative — EIN Aufruf, eine Transaktion, ein Ereignis.
 *
 * „B statt A" ist die Aussage; die beiden Bilder für sich tragen sie nicht. Derselbe Cache-Umgang
 * wie bei `useDraftDecisionMutation`: Das ersetzte Bild bleibt im Cache und trägt „gestrichen"
 * (die Ansicht blendet es aus); die Alternative wird über `insertDraftPhoto` an ihren
 * chronologischen Platz geschrieben — denselben, den der Server ihr beim nächsten Laden gäbe.
 */
export function useDraftExchangeMutation(projectId: number, username: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ replaced, chosen }: { replaced: PhotoOut; chosen: PhotoOut }) =>
      exchangeDraftPhoto(projectId, chosen.id, replaced.id),
    onSuccess: ({ struck, taken }, { chosen }) => {
      if (username !== null) {
        queryClient.setQueryData<AlbumDraftOut>(draftQueryKey(projectId), (current) => {
          if (current === undefined) {
            return current
          }
          const withChosen = insertDraftPhoto(current, chosen)
          return applyWrittenRating(
            applyWrittenRating(withChosen, struck, username),
            taken,
            username,
          )
        })
      }
      invalidateAllButTheDraft(queryClient, projectId)
    },
  })
}

/**
 * Das Rückgängig nach einem Tausch: EIN Aufruf stellt beide eigenen Zeilen auf ihren Vorzustand
 * zurück, alle oder keine. Bei Erfolg setzt sie beide geschriebenen Zustände in den Cache - die
 * Alternative verlässt dabei den Entwurf, wenn sie davor unberührt war. Bei einem Fehlschlag
 * (`409`, weil sich eines der beiden Fotos inzwischen geändert hat) bleibt der Cache unberührt.
 */
export function useDraftExchangeUndoMutation(projectId: number, username: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: DraftExchangeUndoIn) => undoDraftExchange(projectId, body),
    onSuccess: ({ photo, replaced }) => {
      if (username !== null) {
        queryClient.setQueryData<AlbumDraftOut>(draftQueryKey(projectId), (current) =>
          current === undefined
            ? current
            : applyWrittenRating(applyWrittenRating(current, replaced, username), photo, username),
        )
      }
      invalidateAllButTheDraft(queryClient, projectId)
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
