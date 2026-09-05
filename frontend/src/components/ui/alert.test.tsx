import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Alert } from './alert'

describe('Alert', () => {
  it('renders the message with role alert', () => {
    render(<Alert>Fehler beim Laden der Fotos.</Alert>)

    expect(screen.getByRole('alert')).toHaveTextContent('Fehler beim Laden der Fotos.')
  })

  // Einheitliche Fehlerbanner-Komponente mit "Erneut versuchen" (specs/architecture/0004-design-
  // system.md, "Wiederkehrende Muster" -> "Fehlerzustand mit Retry") - zentralisiert das Muster,
  // das zuvor in jeder View einzeln als <button onClick={() => query.refetch()}> nachgebaut wurde.
  it('renders a retry button that calls onRetry when provided', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    render(<Alert onRetry={onRetry}>Fehler beim Laden der Fotos.</Alert>)

    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders no retry button when onRetry is not provided', () => {
    render(<Alert>Fehler beim Laden der Fotos.</Alert>)

    expect(screen.queryByRole('button', { name: /erneut versuchen/i })).not.toBeInTheDocument()
  })

  /*
   * Board-Grundelement "Hinweis- und Meldungselemente" in drei Auspraegungen
   * (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6). Uebernommen wird die
   * OPTIK des Board-Toasts, NICHT sein Verhalten: Meldungen bleiben inline und kontextnah, ein
   * schwebendes, selbst verschwindendes Toast-System waere neues Verhalten und damit eine
   * funktionale Aenderung, die Spec 0320 ausschliesst.
   */
  it.each([
    ['success', 'check'],
    ['warning', 'info'],
    ['error', 'x-circle'],
  ] as const)('renders the %s variant with its own board symbol', (variant, icon) => {
    render(<Alert variant={variant}>Meldungstext.</Alert>)

    // `info` statt des Board-`star` fuer die Warnung: `star` ist im Produkt das Favorit-Symbol,
    // dieselbe Form fuer "Warnung" zu verwenden braeche die Unterscheidbarkeit der
    // Bewertungsstufen (ADR 0055 Punkt 7e).
    expect(screen.getByRole('alert').querySelector(`[data-icon="${icon}"]`)).not.toBeNull()
  })

  // Die Meldung traegt ihre Bedeutung nie allein ueber die Umrissfarbe - Symbol UND Titeltext
  // sind Pflicht. Ohne Titel-Vorgabe greift der kuratierte Standardtitel der Auspraegung.
  it.each([
    ['success', 'Erfolg'],
    ['warning', 'Hinweis'],
    ['error', 'Fehler'],
  ] as const)('always carries a title for the %s variant', (variant, defaultTitle) => {
    render(<Alert variant={variant}>Meldungstext.</Alert>)

    expect(screen.getByRole('alert')).toHaveTextContent(defaultTitle)
  })

  it('lets the caller override the curated title', () => {
    render(<Alert title="Scan fehlgeschlagen">Meldungstext.</Alert>)

    expect(screen.getByRole('alert')).toHaveTextContent('Scan fehlgeschlagen')
  })

  it('renders every variant pairwise distinguishable without colour perception', () => {
    const icons = (['success', 'warning', 'error'] as const).map((variant) => {
      const { unmount } = render(<Alert variant={variant}>Meldungstext.</Alert>)
      const name = screen.getByRole('alert').querySelector('[data-icon]')!.getAttribute('data-icon')
      unmount()
      return name
    })

    expect(new Set(icons).size).toBe(icons.length)
  })

  /*
   * Sicherheits-Muss-Kriterium aus specs/features/0058-cloud-vision-status-transparenz.md, in der
   * neuen Einkleidung unveraendert gueltig: Fremdtext (der `detail`-Text des Servers) steht
   * ausschliesslich als regulaerer React-Textknoten im BEITEXT, nie im kuratierten Titel und nie
   * als Markup. Der Risikopunkt der neuen Form ist die Versuchung, den Beitext "schoener" zu
   * machen - `detail` kann roher Exception-Text sein.
   */
  it('renders foreign detail text as a plain text node, never as markup', () => {
    render(<Alert>{'<img src=x onerror="alert(1)">'}</Alert>)

    const alert = screen.getByRole('alert')
    expect(alert.querySelector('img')).toBeNull()
    expect(alert).toHaveTextContent('<img src=x onerror="alert(1)">')
  })
})
