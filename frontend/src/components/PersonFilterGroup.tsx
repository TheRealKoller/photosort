import { useId } from 'react'

import type { PersonOut } from '../api/types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

interface PersonFilterGroupProps {
  persons: PersonOut[] | undefined
  isError: boolean
  onRetry: () => void
  selected: readonly number[]
  onChange: (ids: number[]) => void
}

/**
 * Die beschriftete zweite Filterdimension (Design-System: "Beschriftete Filtergruppe"): "Alle",
 * je Person ihr Name, "Beide" nur bei zwei Personen. Genau ein Eintrag ist aktiv. Unter `sm` ein
 * eigener waagerechter Scrollbereich; Namen werden nie gekürzt und nur als Textknoten gerendert.
 */
export function PersonFilterGroup({
  persons,
  isError,
  onRetry,
  selected,
  onChange,
}: PersonFilterGroupProps) {
  const labelId = useId()
  if (isError) {
    return <Alert onRetry={onRetry}>Die Personen konnten nicht geladen werden.</Alert>
  }
  if (persons === undefined || persons.length === 0) {
    return null
  }
  const both = persons.length === 2 ? persons.map((person) => person.id) : null
  const isBoth = both !== null && selected.length === 2
  const entries: { key: string; label: string; ariaLabel?: string; ids: number[] }[] = [
    { key: 'alle', label: 'Alle', ids: [] },
    ...persons.map((person) => ({ key: `p${person.id}`, label: person.name, ids: [person.id] })),
  ]
  if (both !== null) {
    entries.push({
      key: 'beide',
      label: 'Beide',
      ariaLabel: `Beide: ${persons[0].name} und ${persons[1].name}`,
      ids: both,
    })
  }
  function isActive(ids: number[]): boolean {
    if (ids.length === 2) {
      return isBoth
    }
    if (ids.length === 0) {
      return selected.length === 0
    }
    return selected.length === 1 && selected[0] === ids[0]
  }
  return (
    <div className="flex flex-col gap-2" data-person-filter>
      <span id={labelId} className="text-xs font-semibold tracking-wide text-text-h uppercase">
        Personen
      </span>
      <div
        role="group"
        aria-labelledby={labelId}
        className="flex gap-2 overflow-x-auto sm:flex-wrap sm:overflow-x-visible"
      >
        {entries.map((entry) => (
          <Button
            key={entry.key}
            type="button"
            size="sm"
            variant={isActive(entry.ids) ? 'default' : 'outline'}
            aria-pressed={isActive(entry.ids)}
            aria-label={entry.ariaLabel}
            onClick={() => onChange(entry.ids)}
            className="shrink-0 whitespace-nowrap"
          >
            {entry.label}
          </Button>
        ))}
      </div>
    </div>
  )
}
