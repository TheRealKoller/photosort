import { useQuery } from '@tanstack/react-query'

import { listMotifs } from '../api/motifs'

/**
 * Laedt das feste Motivset einmal und cacht es langlebig.
 *
 * `staleTime: Infinity` + `gcTime: Infinity`: das Set aendert sich ausschliesslich durch ein
 * Server-Deployment, nicht zur Laufzeit - ein Refetch beim Fenster-Fokus oder beim Mount einer
 * zweiten Komponente waere reine Netzlast. Geraeumt wird der Eintrag ausschliesslich ueber
 * `queryClient.clear()` an den beiden Sitzungsende-Punkten (Abmelden und 401), die den gesamten
 * Cache leeren (specs/features/0561) - eine reine Garbage Collection wuerde diesen
 * unvergaenglichen Eintrag nie entfernen.
 *
 * Mehrere gleichzeitige Konsumenten teilen sich denselben Cache-Eintrag (`queryKey`) und loesen
 * deshalb genau EINEN Request aus - dafuer gibt es einen eigenen Hook-Test mit Aufrufzaehler. Der
 * Schluessel ist bewusst ein EIGENER, nicht der der Kategorien: beide Antworten haben dieselbe
 * Form aus Schluessel und Anzeigename, und ein gemeinsamer Schluessel liesse die eine als die
 * andere gelten.
 */
export function useMotifsQuery() {
  return useQuery({
    queryKey: ['motifs'],
    queryFn: listMotifs,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
