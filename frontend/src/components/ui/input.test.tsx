import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Input } from './input'

/*
 * Das Board kennt fuer das Eingabefeld drei Zustaende: normal / fokussiert / fehlerhaft
 * (specs/features/0320-dark-utility-register.md). "Normal" und "fehlerhaft" waren ueber die
 * Formular-Tests der Seiten abgedeckt, "FOKUSSIERT" gar nicht - und genau durch diese Luecke ist
 * eine outline-unterdrueckende Utility unbemerkt hereingekommen, die die eine globale Fokusdarstellung der
 * gesamten Anwendung an jedem Textfeld ausgehebelt hat.
 *
 * Die Akzeptanzkriterien lassen den Nachweis ueber die blosse EXISTENZ einer Variante ausdruecklich
 * nur fuer "ueberfahren"/"gedrueckt" zu (in jsdom ist mehr nicht feststellbar). Fuer den Fokus ist
 * mehr moeglich und deshalb hier auch gefordert: dass das Feld den Fokus tatsaechlich annimmt UND
 * dass nichts an ihm die globale Kontur unterdrueckt.
 */
describe('Input', () => {
  it('traegt im Normalzustand den sichtbaren Bedienelement-Umriss, nicht die Dekorlinie', () => {
    render(<Input aria-label="Benutzername" />)

    const input = screen.getByLabelText('Benutzername')
    expect(input.className).toContain('border-border-control')
    // `--border` liegt bei 1.34:1 auf dieser Flaeche - als einziger Umriss waere das Feld nicht
    // als Bedienelement erkennbar.
    expect(input.className).not.toMatch(/(^|\s)border-border(\s|$)/)
  })

  it('nimmt den Fokus an und unterdrueckt die globale Fokuskontur nicht', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Benutzername" />)

    const input = screen.getByLabelText('Benutzername')
    await user.click(input)

    expect(input).toHaveFocus()
    // Entscheidend: KEINE outline-unterdrueckende Utility. Die globale Fokusregel steht in
    // @layer base, jede Utility in @layer utilities - bei Cascade Layers gewinnt die spaetere
    // Ebene unabhaengig von der Spezifitaet, eine einzige solche Klasse nimmt die Kontur weg.
    // Als Positivliste geprueft (es darf GAR KEINE outline-Utility am Feld geben) statt als
    // Negativ-Assertion: so steht der verbotene Klassenname nicht als Literal in einer Datei,
    // die Tailwind mitscannt - sonst landete die Utility allein deshalb in der gebauten CSS.
    expect(input.className.split(/\s+/).filter((cls) => cls.includes('outline'))).toEqual([])
  })

  it('traegt die Board-Merkmale des fokussierten Zustands', () => {
    render(<Input aria-label="Benutzername" />)

    const className = screen.getByLabelText('Benutzername').className
    // 1,5px Akzentrand am Feld und Textmarke in Akzentfarbe (Board). In jsdom nicht messbar -
    // hier als Existenz der Variante gefuehrt, analog zum zulaessigen Nachweis fuer
    // ueberfahren/gedrueckt.
    expect(className).toContain('focus:border-accent')
    expect(className).toContain('focus:border-[1.5px]')
    expect(className).toContain('caret-accent')
  })

  it('haelt Fehlerumriss und Fokus gleichzeitig sichtbar', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Projektname" aria-invalid />)

    const input = screen.getByLabelText('Projektname')
    await user.click(input)

    expect(input).toHaveFocus()
    // Der Fehlerumriss bleibt AM Feld (die Reihenfolge der beiden Varianten in der gebauten CSS
    // ist im Design-Vertragstest festgehalten), die Fokusdarstellung liegt als abgesetzte Kontur
    // aussen herum - beide loeschen sich nicht gegenseitig aus.
    expect(input.className).toContain('aria-invalid:border-danger')
    expect(input.className.split(/\s+/).filter((cls) => cls.includes('outline'))).toEqual([])
  })

  it('zeigt den Platzhalter als Inhalt, nicht als deaktivierten Text', () => {
    render(<Input aria-label="Suche" placeholder="Ordner suchen" />)

    // Ein Platzhalter ist Inhalt und traegt deshalb `--text-muted`, nie die Deaktiviert-Stufe.
    // Als Positivliste geprueft statt als Negativ-Assertion: das ist strenger (es darf GENAU
    // diese eine Platzhalter-Utility geben) und nennt die verbotene Utility nicht beim Namen -
    // der Design-Vertragstest sucht sie in allen Quelldateien, auch in Testdateien.
    const placeholderClasses = screen
      .getByLabelText('Suche')
      .className.split(/\s+/)
      .filter((cls) => cls.startsWith('placeholder:'))
    expect(placeholderClasses).toEqual(['placeholder:text-text-muted'])
  })

  it('kennzeichnet den deaktivierten Zustand', () => {
    render(<Input aria-label="Benutzername" disabled />)

    const input = screen.getByLabelText('Benutzername')
    expect(input).toBeDisabled()
    expect(input.className).toContain('disabled:text-text-disabled')
  })
})
