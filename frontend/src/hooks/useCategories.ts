import { useQuery } from '@tanstack/react-query'

import { listCategories } from '../api/categories'

/**
 * Laedt das feste Kategorien-Set einmal und cacht es langlebig (UI/UX-Abschnitt der Spec 0289).
 *
 * `staleTime: Infinity` + `gcTime: Infinity`: das Set aendert sich ausschliesslich durch ein
 * Server-Deployment, nicht zur Laufzeit - ein Refetch beim Fenster-Fokus oder beim Mount einer
 * zweiten Komponente waere reine Netzlast. Die Invalidierung erfolgt implizit beim Login-Wechsel,
 * weil dabei der gesamte QueryClient neu aufgebaut wird.
 *
 * Mehrere gleichzeitige Konsumenten teilen sich denselben Cache-Eintrag (`queryKey`) und loesen
 * deshalb genau EINEN Request aus - dafuer gibt es einen eigenen Hook-Test mit Aufrufzaehler.
 */
export function useCategoriesQuery() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
