import { useQuery } from '@tanstack/react-query'

import { listMotifs } from '../api/motifs'

/**
 * Laedt das feste Motivset einmal und cacht es langlebig.
 *
 * `staleTime: Infinity` + `gcTime: Infinity`: das Set aendert sich ausschliesslich durch ein
 * Server-Deployment, nicht zur Laufzeit - ein Refetch beim Fenster-Fokus oder beim Mount einer
 * zweiten Komponente waere reine Netzlast. Die Invalidierung erfolgt implizit beim Login-Wechsel,
 * weil dabei der gesamte QueryClient neu aufgebaut wird.
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
