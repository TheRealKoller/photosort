import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CATEGORY_SET } from '../test/categorySetFixture'
import { CategorySelect } from './CategorySelect'

// specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 9. Bewusst KEINE Wiederholung
// der Faelle aus CriterionDetailsList.test.tsx (alle 13 Eintraege angeboten, Registry-Reihenfolge,
// Auswahl-Callback, "Nicht erkannt" waehlbar samt Erklaertext, Deaktivierung waehrend Laden/
// Mutation, Inline-Alert mit "Erneut versuchen") - specs/architecture/0002-testkonzept.md verbietet
// Doppelabdeckung derselben Aussage auf zwei Ebenen. Hier stehen nur die Eigenschaften, die die
// Komponente ALLEIN traegt und ueber die Liste nicht erreichbar sind: die Vorauswahl-Regeln und der
// Platzhalter.

function renderSelect(props: Partial<Parameters<typeof CategorySelect>[0]> = {}) {
  return render(
    <CategorySelect categories={CATEGORY_SET} value={null} onSelect={vi.fn()} {...props} />
  )
}

describe('CategorySelect: Vorauswahl', () => {
  it('preselects the currently effective category of the photo', () => {
    renderSelect({ value: 'gebaeude_bauwerk' })

    expect(screen.getByLabelText('Alle Kategorien')).toHaveValue('gebaeude_bauwerk')
  })

  it('preselects nothing for a legacy key that is not part of the set', () => {
    // Die Laufhistorie wird nicht migriert - ein Altwert wie "landscape" darf keine falsche
    // Kategorie des neuen Sets suggerieren, sondern laesst den Platzhalter stehen.
    renderSelect({ value: 'landscape' })

    expect(screen.getByLabelText('Alle Kategorien')).toHaveValue('')
  })

  it('preselects nothing when the photo has no category yet', () => {
    renderSelect({ value: null })

    expect(screen.getByLabelText('Alle Kategorien')).toHaveValue('')
  })
})

describe('CategorySelect: Platzhalter und leeres Set', () => {
  it('offers the placeholder as a non-selectable entry', () => {
    renderSelect()

    const placeholder = within(screen.getByLabelText('Alle Kategorien')).getByRole('option', {
      name: 'Kategorie wählen…',
    })
    expect(placeholder).toBeDisabled()
  })

  it('names the loading state in the placeholder itself', () => {
    renderSelect({ categories: [], isLoading: true })

    expect(
      within(screen.getByLabelText('Alle Kategorien')).getByRole('option', {
        name: 'wird geladen…',
      })
    ).toBeInTheDocument()
  })

  it('stays disabled for an empty set even when nothing is loading', () => {
    // Kein Bypass: ein leeres Set ohne Lade- und ohne Fehlerzustand (etwa ein Server, der eine
    // leere Liste liefert) darf keine scheinbar bedienbare, tatsaechlich leere Auswahl zeigen.
    renderSelect({ categories: [], isLoading: false, isError: false })

    expect(screen.getByLabelText('Alle Kategorien')).toBeDisabled()
  })
})
