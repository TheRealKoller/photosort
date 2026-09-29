import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StaticFaceCropTile } from './FaceCropTile'

// Ein erzeugtes, einfarbiges Stück JPEG-Anfang ohne Gesicht (S11) - base64 genügt hier.
const CROP = btoa('\xff\xd8\xff\xe0einfarbig')

let created = 0

beforeEach(() => {
  created = 0
  Object.assign(URL, {
    createObjectURL: vi.fn(() => `blob:crop-${++created}`),
    revokeObjectURL: vi.fn(),
  })
})

describe('StaticFaceCropTile', () => {
  it('zeigt den Ausschnitt nur als Blob-URL mit festem Typ und gibt sie beim Aushängen frei', () => {
    const { unmount } = render(<StaticFaceCropTile source={CROP} alt="Gesicht ohne Namen" />)

    const image = screen.getByRole('img', { name: 'Gesicht ohne Namen' })
    expect(image).toHaveAttribute('src', 'blob:crop-1')
    const blob = vi.mocked(URL.createObjectURL).mock.calls[0]?.[0] as Blob
    expect(blob.type).toBe('image/jpeg')
    unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:crop-1')
  })

  it('gibt beim Wechsel der Quelle die alte URL genau einmal frei', () => {
    const { rerender } = render(<StaticFaceCropTile source={CROP} alt="Gesicht ohne Namen" />)

    rerender(<StaticFaceCropTile source={btoa('anders')} alt="Gesicht ohne Namen" />)

    expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:crop-1')
    expect(screen.getByRole('img', { name: 'Gesicht ohne Namen' })).toHaveAttribute(
      'src',
      'blob:crop-2',
    )
  })

  it('lässt bei einem nicht darstellbaren Ausschnitt eine Platzhalterfläche stehen', () => {
    render(<StaticFaceCropTile source="%%% kein base64 %%%" alt="Gesicht ohne Namen" />)

    expect(screen.getByRole('img', { name: 'Ausschnitt nicht verfügbar' })).toHaveClass(
      'bg-overlay',
    )
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
