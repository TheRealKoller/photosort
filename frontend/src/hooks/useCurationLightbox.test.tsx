import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import type { InitialEntry } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { useCurationLightbox } from './useCurationLightbox'

/*
 * specs/features/0531-kuratierung-grossansicht.md - der Oeffnungszustand der Grossansicht IST der
 * Verlaufseintrag. Geprueft wird am beobachtbaren Verlauf: Eine Stub-Route liegt vor der Seite,
 * und ein Zurueck muss dort ankommen. Nur so fallen verwaiste oder ueberzaehlige Eintraege auf -
 * es gibt keinen Spion auf `navigate`.
 */

const PAGE = { pathname: '/projects/1/album', search: '?x=1' }
const ITEMS = [{ id: 5 }, { id: 7 }]

function wrapperFor(entries: InitialEntry[]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
        {children}
      </MemoryRouter>
    )
  }
}

function renderLightboxHook(
  pageEntry: InitialEntry = `${PAGE.pathname}${PAGE.search}`,
  items: readonly { id: number }[] | 'loading' = ITEMS,
) {
  const heading = document.createElement('h1')
  heading.tabIndex = -1
  document.body.append(heading)
  const headingRef = { current: heading }
  const view = renderHook(
    ({ list }: { list: readonly { id: number }[] | undefined }) => ({
      lightbox: useCurationLightbox({ items: list, headingRef }),
      location: useLocation(),
      navigate: useNavigate(),
    }),
    {
      wrapper: wrapperFor(['/stub', pageEntry]),
      initialProps: { list: items === 'loading' ? undefined : items },
    },
  )
  return { ...view, heading }
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('useCurationLightbox', () => {
  it.each([
    [{ grossansicht: 5 }, 5],
    [{ grossansicht: '5' }, null],
    [{ grossansicht: 5.5 }, null],
    [{ grossansicht: Number.NaN }, null],
    [{ grossansicht: Number.POSITIVE_INFINITY }, null],
    [{ grossansicht: 2 ** 53 }, null],
    [{ grossansicht: null }, null],
    [{}, null],
    [{ andere: 1 }, null],
    ['grossansicht', null],
    [null, null],
  ])('reads the open photo from the history state %j as %j', (state, expected) => {
    const { result } = renderLightboxHook({ ...PAGE, state }, [{ id: 5 }])

    expect(result.current.lightbox.openPhotoId).toBe(expected)
  })

  it('looks the photo up in the loaded list only', () => {
    const { result } = renderLightboxHook({ ...PAGE, state: { grossansicht: 7 } })

    expect(result.current.lightbox.photo).toBe(ITEMS[1])
  })

  it('opens with exactly one new entry on the same pathname and search', () => {
    const { result } = renderLightboxHook()

    act(() => result.current.lightbox.open(7))

    expect(result.current.location).toMatchObject({ ...PAGE, state: { grossansicht: 7 } })
    expect(result.current.lightbox.openPhotoId).toBe(7)
    act(() => result.current.navigate(-1))
    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
    act(() => result.current.navigate(-1))
    expect(result.current.location.pathname).toBe('/stub')
  })

  it('closes an own opening by going exactly one step back', () => {
    const { result } = renderLightboxHook()
    act(() => result.current.lightbox.open(7))

    act(() => result.current.lightbox.close())

    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
    act(() => result.current.navigate(-1))
    expect(result.current.location.pathname).toBe('/stub')
  })

  it('replaces an entry it did not create (reload) instead of going back', () => {
    const { result } = renderLightboxHook({ ...PAGE, state: { grossansicht: 5 } })

    act(() => result.current.lightbox.close())

    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
    expect(result.current.lightbox.openPhotoId).toBeNull()
    act(() => result.current.navigate(-1))
    expect(result.current.location.pathname).toBe('/stub')
  })

  /* „Vor popstate" deterministisch: MemoryRouter navigiert synchron, zwei Aufrufe in EINEM act
     gingen ohne Riegel zwei Eintraege zurueck und verliessen die Seite. */
  it('goes back only once for two closes before the navigation settles', () => {
    const { result } = renderLightboxHook()
    act(() => result.current.lightbox.open(7))

    act(() => {
      result.current.lightbox.close()
      result.current.lightbox.close()
    })

    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
  })

  it('releases the latch for the next opening', () => {
    const { result } = renderLightboxHook()
    act(() => result.current.lightbox.open(7))
    act(() => result.current.lightbox.close())
    act(() => result.current.lightbox.open(5))

    act(() => result.current.lightbox.close())

    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
    act(() => result.current.navigate(-1))
    expect(result.current.location.pathname).toBe('/stub')
  })

  it('does not navigate when nothing is open', () => {
    const { result } = renderLightboxHook()
    const before = result.current.location.key

    act(() => result.current.lightbox.close())

    expect(result.current.location.key).toBe(before)
    expect(result.current.location.pathname).toBe(PAGE.pathname)
  })

  it('focuses the registered trigger without scrolling when the photo closes', () => {
    const { result } = renderLightboxHook()
    const trigger = document.createElement('button')
    document.body.append(trigger)
    let preventScroll: boolean | undefined
    trigger.focus = (options?: FocusOptions) => {
      preventScroll = options?.preventScroll
      HTMLElement.prototype.focus.call(trigger, options)
    }
    act(() => result.current.lightbox.triggerRef(7)(trigger))
    act(() => result.current.lightbox.open(7))

    act(() => result.current.lightbox.close())

    expect(trigger).toHaveFocus()
    expect(preventScroll).toBe(true)
  })

  it('also returns the focus on browser back', () => {
    const { result } = renderLightboxHook()
    const trigger = document.createElement('button')
    document.body.append(trigger)
    act(() => result.current.lightbox.triggerRef(7)(trigger))
    act(() => result.current.lightbox.open(7))

    act(() => result.current.navigate(-1))

    expect(trigger).toHaveFocus()
  })

  it('keeps no dead trigger and falls back to the page heading', () => {
    const { result, heading } = renderLightboxHook()
    const trigger = document.createElement('button')
    document.body.append(trigger)
    act(() => result.current.lightbox.triggerRef(7)(trigger))
    act(() => result.current.lightbox.triggerRef(7)(null))
    act(() => result.current.lightbox.open(7))

    act(() => result.current.lightbox.close())

    expect(heading).toHaveFocus()
  })

  it('never focuses a detached trigger', () => {
    const { result, heading } = renderLightboxHook()
    const trigger = document.createElement('button')
    document.body.append(trigger)
    act(() => result.current.lightbox.triggerRef(7)(trigger))
    act(() => result.current.lightbox.open(7))
    trigger.remove()

    act(() => result.current.lightbox.close())

    expect(heading).toHaveFocus()
  })

  /* „Noch nicht geladen" ist nicht „verschwunden": Waehrend die Liste laedt, bleibt der Eintrag. */
  it('waits while the list loads and closes once the loaded list lacks the photo', () => {
    const { result, rerender } = renderLightboxHook(
      { ...PAGE, state: { grossansicht: 9 } },
      'loading',
    )

    expect(result.current.location.state).toEqual({ grossansicht: 9 })
    expect(result.current.lightbox.photo).toBeUndefined()

    rerender({ list: ITEMS })

    expect(result.current.location).toMatchObject({ ...PAGE, state: null })
    act(() => result.current.navigate(-1))
    expect(result.current.location.pathname).toBe('/stub')
  })
})
